import asyncio
import feedparser
import yaml
import deepl
import ollama
import re
import os
import json
import torch
from datetime import datetime
from aiogram import Bot
from io import BytesIO
from dotenv import load_dotenv
from diffusers import FluxPipeline

# Flux ultra veloce su A40
pipe = FluxPipeline.from_pretrained(
    "black-forest-labs/FLUX.1-schnell",
    torch_dtype=torch.bfloat16
)
pipe.to("cuda")

load_dotenv()

with open("config.yaml") as f:
    config = yaml.safe_load(f)

bot = Bot(token=os.getenv("BOT_TOKEN"))
translator = deepl.Translator(os.getenv("DEEPL_KEY"))

SEEN_FILE = "seen.txt"
seen_ids = {line.strip() for line in open(SEEN_FILE)} if os.path.exists(SEEN_FILE) else set()

category_map = {"AI": "ai", "CYBER": "cyber", "HARDWARE": "hardware"}

async def process_entry(entry, feed_name):
    entry_id = entry.link
    if entry_id in seen_ids:
        return

    title_en = entry.title
    summary_en = entry.summary if 'summary' in entry else entry.get('description', '')
    link = entry.link

    prompt = f"""
Sei l'editor italiano di Labirinth – tono underground, professionale, cattivo.
Titolo: {title_en}
Summary: {summary_en[:3500]}

Rispondi SOLO con JSON valido:
{{
  "category": "AI" | "CYBER" | "HARDWARE" | "IGNORE",
  "title": "titolo italiano max 90 char",
  "text": "cappello 2-4 righe italiano perfetto",
  "hashtags": "#AI #Exploit"
}
"""

    try:
        response = ollama.chat(model='llama3.1:8b', messages=[{'role': 'user', 'content': prompt}])['message']['content'].strip()
        result = json.loads(response)
    except Exception as e:
        print(f"LLM error: {e}")
        return

    if result.get("category") == "IGNORE":
        return

    cat_key = category_map.get(result["category"])
    if not cat_key or cat_key not in config["channels"]:
        return

    # Traduci con DeepL
    title_it = translator.translate_text(result["title"], target_lang="IT").text
    text_it = translator.translate_text(result["text"], target_lang="IT").text
    hashtags = result.get("hashtags", "#Labirinth")

    message = f"*{title_it}*\n\n{text_it}\n\n{hashtags}\n\nFonte: {feed_name}\n→ {link}\n\nDiscuti su @LabirinthTalk"

    # Genera immagine Flux
    image_prompt = f"cyberpunk dark neon style, {title_en.lower()}, minotaur circuit labyrinth theme, acid green and deep purple glow, dramatic lighting, ultra detailed, no text, 16:9 aspect ratio"
    image = pipe(image_prompt, num_inference_steps=4, guidance_scale=0.0).images[0]

    buf = BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)

    # Post nel canale categoria
    posted = await bot.send_photo(config["channels"][cat_key], photo=buf, caption=message, parse_mode="Markdown")

    post_link = f"https://t.me/{config['channels'][cat_key][1:]}/{posted.message_id}"

    # Teaser nel main
    teaser = f"*{title_it}* #{result['category']}\n\n{text_it[:150]}...\n\n→ {post_link}\n{hashtags}"
    await bot.send_message(config["channels"]["main"], teaser, parse_mode="Markdown")

    # Salva
    seen_ids.add(entry_id)
    with open(SEEN_FILE, "a") as f:
        f.write(entry_id + "\n")

    print(f"POSTATO → {title_it} [{result['category']}]")

async def main_loop():
    while True:
        print(f"{datetime.now()} → Scan feed...")
        for feed in config["feeds"]:
            d = feedparser.parse(feed["url"])
            for entry in reversed(d.entries):  # più recenti prima
                await process_entry(entry, feed["name"])
        await asyncio.sleep(1800)

if __name__ == "__main__":
    asyncio.run(main_loop())
