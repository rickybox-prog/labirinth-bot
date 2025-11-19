import asyncio
import feedparser
import yaml
import deepl
import ollama
import re
import torch
from datetime import datetime
from aiogram import Bot
from io import BytesIO
from dotenv import load_dotenv
import json

# Carica Flux una volta sola
pipe = FluxPipeline.from_pretrained("black-forest-labs/FLUX.1-schnell", torch_dtype=torch.bfloat16)
pipe.to("cuda")

load_dotenv()

with open("config.yaml") as f:
    config = yaml.safe_load(f)

bot = Bot(token=config["bot_token"])
translator = deepl.Translator(config["deepl_key"])

SEEN_FILE = "seen.txt"
seen_ids = set(open(SEEN_FILE).readlines()) if os.path.exists(SEEN_FILE) else set()

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
Sei un esperto italiano di AI, cybersecurity e hardware estremo.
Testo originale:
Titolo: {title_en}
Summary: {summary_en[:3500]}

Compito:
- Decidi categoria: AI, CYBER, HARDWARE o IGNORE (solo se non rilevante)
- Scrivi titolo italiano accattivante (max 90 caratteri)
- Scrivi cappello 2-4 righe in italiano perfetto, tono underground/professionale
- Max 4 hashtag

Rispondi ESATTAMENTE con JSON valido JSON, niente altro testo:
{{"category": "AI" or "CYBER" or "HARDWARE" or "IGNORE", "title": "...", "text": "...", "hashtags": "#AI #RISC-V"}}

Solo il JSON, niente altro.
"""

    response = ollama.chat(model='llama3.1:8b', messages=[{'role': 'user', 'content': prompt}])['message']['content'].strip()

    try:
        result = json.loads(response)
    except:
        print("JSON fallito, skip")
        return

    if result["category"] == "IGNORE":
        return

    category_key = result["category"].lower()  # ai, cyber, hardware

    if category_key not in config["channels"]:
        print("Categoria non valida")
        return

    title_it = translator.translate_text(result["title"], target_lang="IT").text
    text_it = translator.translate_text(result["text"], target_lang="IT").text

    message = f"*{title_it}*\n\n{text_it}\n\n{result['hashtags']}\n\nFonte: {feed_name}\n→ {link}\n\n@LabirinthTalk"

    # Genera immagine cyberpunk
    image_prompt = f"cyberpunk neon digital art, {title_en.lower()}, dark purple and acid green glow, circuits neural networks minotaur labyrinth theme, dramatic lighting, ultra detailed, no text, 16:9"
    image = pipe(image_prompt, num_inference_steps=4, guidance_scale=0.0, max_sequence_length=256).images[0]

    buf = BytesIO()
    image.save(buf, format='PNG')
    buf.seek(0)

    # Post completo nella categoria
    posted = await bot.send_photo(chat_id=config["channels"][category_key], photo=buf, caption=message, parse_mode="Markdown")

    link_to_post = f"https://t.me/{config['channels'][category_key].lstrip('@')}/{posted.message_id}"

    teaser = f"*{title_it}* #{result['category']}\n\n{text_it[:150]}...\n\n→ {link_to_post}\n{result['hashtags']} @LabirinthTalk"

    await bot.send_message(config["channels"]["main"], teaser, parse_mode="Markdown")

    # Salva per non duplicare
    with open(SEEN_FILE, "a") as f:
        f.write(entry_id + "\n")

    print(f"Postato: {title_it} → {result['category']}")

async def main_loop():
    while True:
        print(f"{datetime.now()} – Scan feed...")
        for feed in config["feeds"]:
            d = feedparser.parse(feed["url"])
            for entry in d.entries[:15]:  # ultimi 15 per sicurezza
                await process_entry(entry, feed["name"])
        await asyncio.sleep(1800)  # 30 min

if __name__ == "__main__":
    asyncio.run(main_loop())