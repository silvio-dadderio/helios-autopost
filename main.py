#!/usr/bin/env python3
"""
HÉLIOS Cool Roof — Auto-Post autonome (Railway)
- LinkedIn : texte, mardi + vendredi à 9h00 UTC
- Instagram : image, lundi à 9h00 UTC
- Alerte email quand plus d'images
"""

import os
import json
import random
import smtplib
import requests
import schedule
import time
from datetime import datetime
from pathlib import Path
from email.mime.text import MIMEText

BUFFER_TOKEN      = os.environ["BUFFER_TOKEN"]
BUFFER_ORG_ID     = os.environ["BUFFER_ORG_ID"]
LINKEDIN_CHANNEL  = os.environ["LINKEDIN_CHANNEL"]
INSTAGRAM_CHANNEL = os.environ["INSTAGRAM_CHANNEL"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
ALERT_EMAIL       = os.environ["ALERT_EMAIL"]
SMTP_FROM         = os.environ["SMTP_FROM"]
SMTP_PASSWORD     = os.environ["SMTP_PASSWORD"]
SMTP_SERVER       = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT         = int(os.environ.get("SMTP_PORT", "587"))
IMAGES_API        = os.environ.get("IMAGES_API_URL", "")
HISTORY_FILE      = "/data/used_images.json"

def load_history():
    os.makedirs("/data", exist_ok=True)
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return {"used_instagram": [], "posts_linkedin": 0, "posts_instagram": 0}

def save_history(h):
    os.makedirs("/data", exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(h, f, indent=2, ensure_ascii=False)

def list_available_images():
    if Path("images.json").exists():
        with open("images.json") as f:
            return json.load(f)
    return []

def pick_next_image():
    all_images = list_available_images()
    history = load_history()
    used = set(history.get("used_instagram", []))
    remaining = [img for img in all_images if img not in used]
    if not remaining:
        send_alert_email()
        return None
    img = remaining[0]
    print(f"📸 Image : {img} ({len(remaining)-1} restante(s))")
    return img

def send_alert_email():
    print("🔴 Plus d'images — envoi email...")
    try:
        msg = MIMEText("HÉLIOS Auto-Post : plus d'images Instagram disponibles. Ajoutez-en sur GitHub.")
        msg["Subject"] = "🔴 HÉLIOS — Plus d'images Instagram"
        msg["From"] = SMTP_FROM
        msg["To"] = ALERT_EMAIL
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_FROM, SMTP_PASSWORD)
            s.send_message(msg)
        print(f"✅ Email envoyé à {ALERT_EMAIL}")
    except Exception as e:
        print(f"⚠️  Erreur email : {e}")

FORMAT_PROMPTS = {
    "storytelling": "Écris un post LinkedIn storytelling avant/après chantier Cool Roof. Commence par une situation terrain concrète. 180-250 mots, CTA final, 4-5 hashtags.",
    "technique": "Écris un post LinkedIn conseil technique Cool Roof. Inclus : Réflectance 95%, SRI 120, émissivité 0.89. 180-250 mots, CTA final, 4-5 hashtags.",
    "preuve_sociale": "Écris un post LinkedIn preuve sociale Cool Roof. Cas client fictif réaliste. 180-250 mots, CTA final, 4-5 hashtags.",
}

FALLBACK_LINKEDIN = """Il faisait 52°C en surface de toiture. En plein mois de juillet.

L'entrepôt de notre client était devenu invivable. Climatisation à fond, productivité en chute.

Deux semaines après l'application de notre système PRIMATHERM® PH107 :
→ -18°C en surface de toiture
→ -4°C à l'intérieur des locaux
→ -30% de consommation climatisation

Réflectance 95%, SRI 120, émissivité 0.89. ROI : 2 à 4 ans.

Vous gérez des bâtiments qui surchauffent l'été ? Parlons-en.

#CoolRoof #ToitureIndustrielle #EfficacitéÉnergétique #BâtimentDurable #HÉLIOS"""

FALLBACK_INSTAGRAM = """☀️ Quand la chaleur devient un problème, HÉLIOS devient la solution.

95% du rayonnement solaire réfléchi. SRI 120. Des toitures fraîches même en plein été.

Demandez votre devis → lien en bio

#CoolRoof #ToitureIndustrielle #Helios #EfficaciteEnergetique #RoofCoating #BatimentDurable"""

def call_claude(prompt, system="", max_tokens=600):
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": "claude-sonnet-4-20250514", "max_tokens": max_tokens, "system": system, "messages": [{"role": "user", "content": prompt}]},
            timeout=30
        )
        return r.json()["content"][0]["text"].strip()
    except Exception as e:
        print(f"⚠️  Erreur Claude : {e}")
        return None

def generate_linkedin_text():
    fmt = random.choice(list(FORMAT_PROMPTS.keys()))
    print(f"✍️  Format : {fmt}")
    text = call_claude(FORMAT_PROMPTS[fmt], system="Tu es le community manager de HÉLIOS Cool Roof BtoB. Style direct, expert, chiffres concrets.")
    return text or FALLBACK_LINKEDIN

def generate_instagram_caption(image_name):
    text = call_claude(f"Légende Instagram pour photo Cool Roof ({image_name}). 80-120 mots, 1-2 emojis, Réflectance 95% ou SRI 120, CTA lien en bio, 8-10 hashtags.", max_tokens=300)
    return text or FALLBACK_INSTAGRAM

MUTATION = """mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess { post { id status } }
    ... on MutationError { message }
  }
}"""

def post_linkedin(text):
    variables = {"input": {
        "channelId": LINKEDIN_CHANNEL,
        "text": text,
        "schedulingType": "automatic",
        "mode": "addToQueue"
    }}
    try:
        r = requests.post("https://api.buffer.com/graphql",
            headers={"Authorization": f"Bearer {BUFFER_TOKEN}", "Content-Type": "application/json"},
            json={"query": MUTATION, "variables": variables}, timeout=30)
        data = r.json()
        if "errors" in data:
            print(f"❌ Buffer LinkedIn : {data['errors']}")
            return False
        result = data.get("data", {}).get("createPost", {})
        if "post" in result:
            print(f"✅ LinkedIn envoyé ! ID: {result['post']['id']}")
            return True
        print(f"⚠️  Réponse : {data}")
        return False
    except Exception as e:
        print(f"❌ Erreur : {e}")
        return False

def post_instagram(text, image_url):
    variables = {"input": {
        "channelId": INSTAGRAM_CHANNEL,
        "text": text,
        "schedulingType": "automatic",
        "mode": "addToQueue",
        "metadata": {"instagram": {"type": "post", "shouldShareToFeed": True}},
        "assets": {"images": [{"url": image_url}]}
    }}
    try:
        r = requests.post("https://api.buffer.com/graphql",
            headers={"Authorization": f"Bearer {BUFFER_TOKEN}", "Content-Type": "application/json"},
            json={"query": MUTATION, "variables": variables}, timeout=30)
        data = r.json()
        if "errors" in data:
            print(f"❌ Buffer Instagram : {data['errors']}")
            return False
        result = data.get("data", {}).get("createPost", {})
        if "post" in result:
            print(f"✅ Instagram envoyé ! ID: {result['post']['id']}")
            return True
        print(f"⚠️  Réponse : {data}")
        return False
    except Exception as e:
        print(f"❌ Erreur : {e}")
        return False

def job_linkedin():
    print(f"\n[{datetime.now().strftime('%d/%m/%Y %H:%M')}] 📤 Job LinkedIn")
    text = generate_linkedin_text()
    ok = post_linkedin(text)
    if ok:
        h = load_history()
        h["posts_linkedin"] = h.get("posts_linkedin", 0) + 1
        save_history(h)

def job_instagram():
    print(f"\n[{datetime.now().strftime('%d/%m/%Y %H:%M')}] 📸 Job Instagram")
    image_name = pick_next_image()
    if not image_name:
        return
    caption = generate_instagram_caption(image_name)
    image_url = f"{IMAGES_API}/{image_name}"
    ok = post_instagram(caption, image_url)
    if ok:
        h = load_history()
        h.setdefault("used_instagram", []).append(image_name)
        h["posts_instagram"] = h.get("posts_instagram", 0) + 1
        save_history(h)

def start_scheduler():
    print("=" * 55)
    print("  HÉLIOS Auto-Post — Démarrage Railway")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 55)
    print("  LinkedIn  : mardi + vendredi à 09:00 UTC")
    print("  Instagram : lundi à 09:00 UTC")
    print("=" * 55)

    schedule.every().tuesday.at("09:00").do(job_linkedin)
    schedule.every().friday.at("09:00").do(job_linkedin)
    schedule.every().monday.at("09:00").do(job_instagram)

    print("\n✅ Scheduler actif — en attente des prochains créneaux...\n")
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    start_scheduler()
