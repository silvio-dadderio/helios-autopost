#!/usr/bin/env python3
"""
HÉLIOS Cool Roof — Auto-Post autonome (Railway)
- LinkedIn : image (semaines impaires) ou texte (semaines paires), mardi 09:00 UTC
- Instagram : image, mardi 16:00 UTC (18h00 Paris)
- Alerte email quand plus d'images
"""

import os
import io
import json
import random
import smtplib
import requests
import schedule
import time
from datetime import datetime
from pathlib import Path
from email.mime.text import MIMEText
from PIL import Image

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
INSTAGRAM_MAX_PX  = 4500

def load_history():
    os.makedirs("/data", exist_ok=True)
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return {"used_instagram": [], "used_linkedin": [], "posts_linkedin": 0, "posts_instagram": 0}

def save_history(h):
    os.makedirs("/data", exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(h, f, indent=2, ensure_ascii=False)

def list_images(filename):
    if Path(filename).exists():
        with open(filename) as f:
            return json.load(f)
    return []

def pick_next(all_images, used_list):
    used = set(used_list)
    remaining = [img for img in all_images if img not in used]
    if not remaining:
        return None
    return remaining[0]

def send_alert_email(subject, body):
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
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

def call_claude(prompt, system="", max_tokens=600):
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": "claude-sonnet-4-6", "max_tokens": max_tokens, "system": system, "messages": [{"role": "user", "content": prompt}]},
            timeout=30
        )
        return r.json()["content"][0]["text"].strip()
    except Exception as e:
        print(f"⚠️  Erreur Claude : {e}")
        return None

def generate_linkedin_text():
    fmt = random.choice(list(FORMAT_PROMPTS.keys()))
    print(f"✍️  Format : {fmt}")
    return call_claude(FORMAT_PROMPTS[fmt], system="Tu es le community manager de HÉLIOS Cool Roof BtoB. Style direct, expert, chiffres concrets.")

def generate_linkedin_caption_with_image(image_name):
    prompt = f"Écris un post LinkedIn avec image pour HÉLIOS Cool Roof. Photo : {image_name}. 150-200 mots, accroche forte, chiffres techniques (Réflectance 95%, SRI 120), CTA, 4-5 hashtags."
    return call_claude(prompt, system="Tu es le community manager de HÉLIOS Cool Roof BtoB. Style direct, expert, chiffres concrets.")

def generate_instagram_caption(image_name):
    return call_claude(f"Légende Instagram pour photo Cool Roof ({image_name}). 80-120 mots, 1-2 emojis, Réflectance 95% ou SRI 120, CTA lien en bio, 8-10 hashtags.", max_tokens=300)

def download_and_resize_image(image_url):
    try:
        r = requests.get(image_url, timeout=30, headers={"User-Agent": "Mozilla/5.0", "Accept": "image/*"})
        if r.status_code != 200:
            print(f"⚠️  Image non trouvée ({r.status_code}) : {image_url}")
            return None
        print(f"📥 Image téléchargée : {len(r.content)} bytes")
        img = Image.open(io.BytesIO(r.content))
        if img.mode not in ("RGB",):
            img = img.convert("RGB")
        w, h = img.size
        if w > INSTAGRAM_MAX_PX or h > INSTAGRAM_MAX_PX:
            ratio = min(INSTAGRAM_MAX_PX / w, INSTAGRAM_MAX_PX / h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
            print(f"📐 Redimensionné : {w}x{h} → {img.size}")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        return buf.getvalue()
    except Exception as e:
        print(f"⚠️  Erreur resize : {e}")
        return None

def upload_image_to_buffer(image_url, image_name):
    image_data = download_and_resize_image(image_url)
    if not image_data:
        return None
    mutation = """mutation UploadMedia($input: UploadMediaInput!) {
      uploadMedia(input: $input) { id url }
    }"""
    try:
        files = {
            "operations": (None, json.dumps({"query": mutation, "variables": {"input": {"organizationId": BUFFER_ORG_ID, "file": None}}})),
            "map": (None, json.dumps({"0": ["variables.input.file"]})),
            "0": (f"{Path(image_name).stem}.jpg", image_data, "image/jpeg")
        }
        r = requests.post("https://api.buffer.com/graphql", headers={"Authorization": f"Bearer {BUFFER_TOKEN}"}, files=files, timeout=60)
        data = r.json()
        if "errors" in data:
            print(f"⚠️  Upload échoué : {data['errors']}")
            return None
        url = data["data"]["uploadMedia"]["url"]
        print(f"✅ Image uploadée : {url}")
        return url
    except Exception as e:
        print(f"⚠️  Erreur upload : {e}")
        return None

MUTATION = """mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess { post { id status } }
    ... on MutationError { message }
  }
}"""

def post_linkedin_text(text):
    variables = {"input": {"channelId": LINKEDIN_CHANNEL, "text": text, "schedulingType": "automatic", "mode": "addToQueue"}}
    try:
        r = requests.post("https://api.buffer.com/graphql", headers={"Authorization": f"Bearer {BUFFER_TOKEN}", "Content-Type": "application/json"}, json={"query": MUTATION, "variables": variables}, timeout=30)
        data = r.json()
        if "errors" in data:
            print(f"❌ Buffer LinkedIn : {data['errors']}")
            return False
        result = data.get("data", {}).get("createPost", {})
        if "post" in result:
            print(f"✅ LinkedIn texte envoyé ! ID: {result['post']['id']}")
            return True
        print(f"⚠️  Réponse : {data}")
        return False
    except Exception as e:
        print(f"❌ Erreur : {e}")
        return False

def post_linkedin_image(text, buffer_url):
    variables = {"input": {"channelId": LINKEDIN_CHANNEL, "text": text, "schedulingType": "automatic", "mode": "addToQueue", "assets": [{"image": {"url": buffer_url}}]}}
    try:
        r = requests.post("https://api.buffer.com/graphql", headers={"Authorization": f"Bearer {BUFFER_TOKEN}", "Content-Type": "application/json"}, json={"query": MUTATION, "variables": variables}, timeout=30)
        data = r.json()
        if "errors" in data:
            print(f"❌ Buffer LinkedIn image : {data['errors']}")
            return False
        result = data.get("data", {}).get("createPost", {})
        if "post" in result:
            print(f"✅ LinkedIn image envoyé ! ID: {result['post']['id']}")
            return True
        print(f"⚠️  Réponse : {data}")
        return False
    except Exception as e:
        print(f"❌ Erreur : {e}")
        return False

def post_instagram(text, buffer_url):
    variables = {"input": {"channelId": INSTAGRAM_CHANNEL, "text": text, "schedulingType": "automatic", "mode": "addToQueue", "metadata": {"instagram": {"type": "post", "shouldShareToFeed": True}}, "assets": [{"image": {"url": buffer_url}}]}}
    try:
        r = requests.post("https://api.buffer.com/graphql", headers={"Authorization": f"Bearer {BUFFER_TOKEN}", "Content-Type": "application/json"}, json={"query": MUTATION, "variables": variables}, timeout=30)
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
    h = load_history()

    # Semaines impaires → image, semaines paires → texte
    week_number = datetime.now().isocalendar()[1]
    use_image = (week_number % 2 == 1)

    if use_image:
        all_linkedin = list_images("images-linkedin.json")
        image_name = pick_next(all_linkedin, h.get("used_linkedin", []))
        if image_name:
            print(f"🖼️  LinkedIn avec image : {image_name}")
            image_url = f"{IMAGES_API.replace('/images', '')}/images-linkedin/{image_name}"
            buffer_url = upload_image_to_buffer(image_url, image_name)
            if not buffer_url:
                print("⚠️  Upload échoué → bascule sur texte")
                use_image = False
            else:
                text = generate_linkedin_caption_with_image(image_name)
                if not text:
                    print("⚠️  Claude indisponible → post annulé")
                    return
                ok = post_linkedin_image(text, buffer_url)
                if ok:
                    h.setdefault("used_linkedin", []).append(image_name)
                    h["posts_linkedin"] = h.get("posts_linkedin", 0) + 1
                    save_history(h)
                return
        else:
            print("📝 Plus d'images LinkedIn → bascule sur texte")
            use_image = False

    if not use_image:
        text = generate_linkedin_text()
        if not text:
            print("⚠️  Claude indisponible → post annulé")
            return
        ok = post_linkedin_text(text)
        if ok:
            h["posts_linkedin"] = h.get("posts_linkedin", 0) + 1
            save_history(h)

def job_instagram():
    print(f"\n[{datetime.now().strftime('%d/%m/%Y %H:%M')}] 📸 Job Instagram")
    h = load_history()
    all_images = list_images("images.json")
    image_name = pick_next(all_images, h.get("used_instagram", []))
    if not image_name:
        send_alert_email("🔴 HÉLIOS — Plus d'images Instagram", "Toutes les images ont été publiées. Ajoutez-en sur GitHub.")
        return
    print(f"📸 Image : {image_name} ({len(all_images) - len(h.get('used_instagram', [])) - 1} restante(s))")
    caption = generate_instagram_caption(image_name) or "☀️ Cool Roof HÉLIOS — 95% de réflectance solaire. Demandez votre devis → lien en bio. #CoolRoof #HÉLIOS"
    image_url = f"{IMAGES_API}/{image_name}"
    buffer_url = upload_image_to_buffer(image_url, image_name)
    if not buffer_url:
        print("❌ Upload image échoué — post Instagram annulé")
        return
    ok = post_instagram(caption, buffer_url)
    if ok:
        h.setdefault("used_instagram", []).append(image_name)
        h["posts_instagram"] = h.get("posts_instagram", 0) + 1
        save_history(h)

def start_scheduler():
    print("=" * 55)
    print("  HÉLIOS Auto-Post — Démarrage Railway")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 55)
    print("  LinkedIn  : mardi 09:00 UTC (image ou texte en alternance)")
    print("  Instagram : mardi 16:00 UTC (18h00 Paris)")
    print("=" * 55)

    schedule.every().tuesday.at("09:00").do(job_linkedin)
    schedule.every().tuesday.at("16:00").do(job_instagram)

    print("\n✅ Scheduler actif — en attente des prochains créneaux...\n")
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    start_scheduler()
