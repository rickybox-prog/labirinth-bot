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

# Carica Flux una volta sola all'avvio
pipe = FluxPipeline.from_pretrained(
    "black-forest-labs/FLUX.1-schnell",
    torch_dtype=torch.bfloat16,
    variant="fp8"  # ultra veloce su A40/4090
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

def clean_html(raw):
    return re.sub('<.*?>', '', raw).strip()

async def process_entry(entry, feed_name):
    entry_id = entry.link

    if entry_id in seen_ids:
        return

    title_en = entry.title
    summary_en = entry.summary if 'summary' in entry else entry.get('description', '') 
    link = entry.link

    prompt = f"""
Sei l'editor italiano di Labirinth, tono underground ma professionale.
Titolo originale: {title_en}
Summary: {summary_en[:3500]}

Rispondi SOLO con JSON valido:
{{
  "category": "AI" or "CYBER" or "HARDWARE" or "IGNORE",
  "title": "titolo italiano accattivante (max 90 char)",
  "text": "cappello 2-4 righe italiano perfetto",
  "hashtags": "#AI #Exploit"
}}

Solo il JSON, niente altro testo.
"""

    response = ollama.chat(model='llama3.1:8b', messages=[{'role': 'user', 'content': prompt}])['message']['content'].strip()

    try:
        result = json.loads(response)
    except:
        print(f"JSON fallito: {response}")
        return

    if result.get("category") == "IGNORE":
        return

    cat_key = category_map.get(result["category"])
    if not cat_key or cat_key not in config["channels"]:
        return

    title_it = translator.translate_text(result["title"], target_lang="IT").text
    text_it = translator.translate_text(result["text"], target_lang="IT").text
    hashtags = result.get("hashtags", "#Labirinth")

    message = f"*{title_it}*\n\n{text_it}\n\n{hashtags}\n\nFonte: {feed_name}\n→ {link}\n\nDiscuti → @LabirinthTalk"

    # Genera immagine
    image_prompt = f"cyberpunk dark neon, {title_en.lower()}, minotaur circuit labyrinth, acid green and deep purple, dramatic lighting, ultra detailed, no text, 16:9"
    image = pipe(image_prompt, num_inference_steps=4, guidance_scale=0.0).images[0]

    buf = BytesIO()
    image.save(buf, format='PNG')
    buf.seek(0)

    # Post completo nel canale categoria
    posted = await bot.send_photo(
        chat_id=config["channels"][cat_key],
        photo=buf,
        caption=message,
        parse_mode="Markdown"
    )

    post_link = f"https://t.me/{config['channels'][cat_key][1:]}/{posted.message_id}"

    teaser = f"*{title_it}* #{result['category']}\n\n{text_it[:150]}...\n\n→ {post_link}\n{hashtags}"

    await bot.send_message(config["channels"]["main"], teaser, parse_mode="Markdown")

    seen_ids.add(entry_id)
    with open(SEEN_FILE, "a") as f:
        f.write(entry_id + "\n")

    print(f"Postato → {title_it} [{result['category']}]")

async def main_loop():
    while True:
        print(f"{datetime.now()} → Scan")
        for feed in config["feeds"]:
            d = feedparser.parse(feed["url"])
            for entry in reversed(d.entries):  # dal più recente
                await process_entry(entry, feed["name"])
        await asyncio.sleep(1800)  # 30 min

if __name__ == "__main__":
    asyncio.run(main_loop())
