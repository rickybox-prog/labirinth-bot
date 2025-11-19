import asyncio
import feedparser
import yaml
import deepl
import ollama
import os
import json
import torch
from datetime import datetime
from aiogram import Bot
from aiogram.types import InputFile
from dotenv import load_dotenv
from diffusers import FluxPipeline
from huggingface_hub import login

login(token=os.getenv("HF_TOKEN"))

pipe = FluxPipeline.from_pretrained("black-forest-labs/FLUX.1-schnell", torch_dtype=torch.bfloat16)
pipe.to("cuda")

load_dotenv()

with open("config.yaml") as f:
    config = yaml.safe_load(f)

bot = Bot(token=os.getenv("BOT_TOKEN"))
translator = deepl.Translator(os.getenv("DEEPL_KEY"))

SEEN_FILE = "seen.txt"
seen_ids = set(open(SEEN_FILE).read().splitlines()) if os.path.exists(SEEN_FILE) else set()

category_map = {"AI": "ai", "CYBER": "cyber", "HARDWARE": "hardware"}

async def process_entry(entry, feed_name):
    entry_id = entry.link
    if entry_id in seen_ids:
        return

    title_en = entry.title
    summary_en = entry.summary if 'summary' in entry else entry.get('description', '')
    link = entry.link

    prompt = f"""Sei l'editor italiano di Labirinth. Tono underground ma professionale.
Titolo originale: {title_en}
Summary: {summary_en[:3500]}

Rispondi SOLO con JSON valido:
{{
  "category": "AI" o "CYBER" o "HARDWARE" o "IGNORE",
  "title": "titolo italiano max 90 char",
  "text": "cappello 2-4 righe italiano perfetto",
  "hashtags": "#AI #Cyber #Hardware"
}}"""

    response = None
    for _ in range(6):
        try:
            resp = ollama.chat(model='llama3.1:8b', messages=[{'role': 'user', 'content': prompt}])
            response = resp['message']['content'].strip()
            if response:
                break
        except Exception as e:
            print(f"Ollama retry... {e}")
            await asyncio.sleep(12)

    if not response:
        return

    try:
        result = json.loads(response)
    except:
        return

    if result.get("category") == "IGNORE":
        return

    cat_key = category_map.get(result["category"])
    if not cat_key or cat_key not in config["channels"]:
        return

    title_it = translator.translate_text(result["title"], target_lang="IT").text
    text_it = translator.translate_text(result["text"], target_lang="IT").text
    hashtags = result.get("hashtags", "#Labirinth")

    full_message = f"*{title_it}*\n\n{text_it}\n\n{hashtags}\n\nFonte: {feed_name}\n→ {link}\n\nDiscuti → @LabirinthTalk"

    image = pipe(f"cyberpunk minotaur labyrinth circuit, acid green deep purple neon glow, dark background, ultra detailed, dramatic lighting, no text, 16:9", num_inference_steps=4, guidance_scale=0.0).images[0]

    temp_path = "/tmp/labirinth.png"
    image.save(temp_path)

    posted = await bot.send_photo(
        chat_id=config["channels"][cat_key],
        photo=InputFile(temp_path),
        caption=full_message,
        parse_mode="Markdown"
    )

    post_link = f"https://t.me/{config['channels'][cat_key][1:]}/{posted.message_id}"

    teaser = f"*{title_it}* #{result['category']}\n\n{text_it[:150]}...\n\n→ {post_link}\n{hashtags}"

    await bot.send_message(config["channels"]["main"], teaser, parse_mode="Markdown", disable_web_page_preview=True)

    seen_ids.add(entry_id)
    open(SEEN_FILE, "a").write(entry_id + "\n")
    os.remove(temp_path)

    print(f"POSTATO → {title_it} [{result['category']}]")

async def main_loop():
    while True:
        print(f"{datetime.now()} → Scan feed... ({len(seen_ids)} già pubblicate)")
        for feed in config["feeds"]:
            try:
                d = feedparser.parse(feed["url"])
                for entry in reversed(d.entries[:20]):
                    await process_entry(entry, feed["name"])
            except Exception as e:
                print(f"Errore feed: {e}")
        await asyncio.sleep(1800)

if __name__ == "__main__":
    asyncio.run(main_loop())  print(f"Errore feed: {e}")
        await asyncio.sleep(1800)

if __name__ == "__main__":
    asyncio.run(main_loop())  print(f"Errore feed: {e}")
        await asyncio.sleep(1800)

if __name__ == "__main__":
    asyncio.run(main_loop())  print(f"Errore feed: {e}")
        await asyncio.sleep(1800)

if __name__ == "__main__":
    asyncio.run(main_loop())   print(f"Errore feed: {e}")
        await asyncio.sleep(1800)

if __name__ == "__main__":
    asyncio.run(main_loop())  print(f"Errore feed: {e}")
        await asyncio.sleep(1800)

if __name__ == "__main__":
    asyncio.run(main_loop())  print(f"Errore feed: {e}")
        await asyncio.sleep(1800)

if __name__ == "__main__":
    asyncio.run(main_loop())_loop())ption as e:
                print(e)
        await asyncio.sleep(1800)

if __name__ == "__main__":
    asyncio.run(main())
