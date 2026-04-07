#!/usr/bin/env python3
"""
HÉLIOS Cool Roof — Auto-Post autonome (Railway)
- LinkedIn : texte, mardi + vendredi à 9h00
- Instagram : image, lundi à 9h00
- Tourne en continu, s'arrête + envoie un email quand plus d'images
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

# ─── CONFIG (variables d'environnement Railway) ───────────────────────────────

BUFFER_TOKEN      = os.environ["BUFFER_TOKEN"]
BUFFER_ORG_ID     = os.environ["BUFFER_ORG_ID"]
LINKEDIN_CHANNEL  = os.environ["LINKEDIN_CHANNEL"]
INSTAGRAM_CHANNEL = os.environ["INSTAGRAM_CHANNEL"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

ALERT_EMAIL       = os.environ["ALERT_EMAIL"]        # ton email perso
SMTP_FROM         = os.environ["SMTP_FROM"]          # ex: helios@gmail.com
SMTP_PASSWORD     = os.environ["SMTP_PASSWORD"]      # mot de passe app Gmail
SMTP_SERVER       = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT         = int(os.environ.get("SMTP_PORT", "587"))

# Fichier historique (persisté via volume Railway)
HISTORY_FILE = "/data/used_images.json"
IMAGES_API   = os.environ.get("IMAGES_API_URL", "")  # URL publique dossier images (voir README)

EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# ─── HISTORIQUE ───────────────────────────────────────────────────────────────

def load_history() -> dict:
    os.makedirs("/data", exist_ok=True)
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return {"used_instagram": [], "posts_linkedin": 0, "posts_instagram": 0}

def save_history(history: dict):
    os.makedirs("/data", exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

# ─── IMAGES (Google Drive public ou dossier statique) ─────────────────────────

def list_available_images() -> list[str]:
    """
    Retourne la liste des images dispo.
    Option A : fichier images.json dans le repo (liste statique, à mettre à jour manuellement)
    Option B : URL API externe
    """
    images_file = Path("images.json")
    if images_file.exists():
        with open(images_file) as f:
            return json.load(f)
    return []

def pick_next_image() -> str | None:
    all_images = list_available_images()
    if not all_images:
        print("❌ Aucune image disponible dans images.json")
        return None

    history = load_history()
    used = set(history.get("used_instagram", []))
    remaining = [img for img in all_images if img not in used]

    if not remaining:
        send_alert_email()
        return None

    next_img = remaining[0]
    print(f"📸 Image sélectionnée : {next_img} ({len(remaining)-1} restante(s))")
    if len(remaining) <= 2:
        print(f"⚠️  Stock faible : {len(remaining)} image(s) restante(s)")
    return next_img

# ─── ALERTE EMAIL ─────────────────────────────────────────────────────────────

def send_alert_email():
    print("🔴 Plus d'images — envoi email d'alerte...")
    try:
        msg = MIMEText("""Bonjour,

Le script HÉLIOS Auto-Post a épuisé toutes les images disponibles pour Instagram.

➡️  Ajoute de nouvelles images dans images.json sur GitHub pour relancer la rotation.

— HÉLIOS Auto-Post (Railway)
""")
        msg["Subject"] = "🔴 HÉLIOS Auto-Post — Plus d'images Instagram disponibles"
        msg["From"]    = SMTP_FROM
        msg["To"]      = ALERT_EMAIL

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_FROM, SMTP_PASSWORD)
            server.send_message(msg)

        print(f"✅ Email envoyé à {ALERT_EMAIL}")
    except Exception as e:
        print(f"⚠️  Erreur envoi email : {e}")

# ─── GÉNÉRATION TEXTE (CLAUDE) ────────────────────────────────────────────────

FORMAT_PROMPTS = {
    "storytelling": """Écris un post LinkedIn storytelling (avant/après chantier).
Commence par une situation terrain concrète (ex: "Il faisait 47°C dans l'entrepôt.").
Structure : problème → transformation Cool Roof → chiffres clés → CTA.
Ne commence jamais par "Découvrez" ou "Aujourd'hui".""",

    "technique": """Écris un post LinkedIn conseil technique.
Structure : accroche chiffrée → mécanisme Cool Roof → bénéfices → CTA.
Intègre obligatoirement : Réflectance 95%, SRI 120, émissivité 0.89.""",

    "preuve_sociale": """Écris un post LinkedIn preuve sociale / retour terrain.
Invente un cas client réaliste (usine, entrepôt, grande surface). Pas de nom réel.
Structure : contexte → problème → solution HÉLIOS → résultats mesurables → CTA.""",
}

def generate_linkedin_text() -> str:
    format_key = random.choice(list(FORMAT_PROMPTS.keys()))
    print(f"✍️  Format LinkedIn : {format_key}")

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 600,
                "system": "Tu es le community manager expert de HÉLIOS Cool Roof (BtoB, toitures industrielles). Posts LinkedIn : direct, expert, chiffres concrets, jamais de corporate vague.",
                "messages": [{"role": "user", "content": f"""{FORMAT_PROMPTS[format_key]}

Contraintes : 180-250 mots, sauts de ligne aérés, 1 CTA final, 4-5 hashtags.
Ton professionnel mais humain."""}]
            },
            timeout=30
        )
        return response.json()["content"][0]["text"].strip()
    except Exception as e:
        print(f"⚠️  Erreur Claude : {e} — fallback utilisé")
        return FALLBACK_LINKEDIN

def generate_instagram_caption(image_name: str) -> str:
    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": f"""Légende Instagram pour une photo Cool Roof ({image_name}).
80-120 mots, 1-2 emojis, Réflectance 95% ou SRI 120, CTA "lien en bio", 8-10 hashtags FR/EN."""}]
            },
            timeout=30
        )
        return response.json()["content"][0]["text"].strip()
    except Exception as e:
        print(f"⚠️  Erreur Claude : {e} — fallback utilisé")
        return FALLBACK_INSTAGRAM

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

Moins de climatisation, plus de confort, ROI en 2 à 4 ans.

Demandez votre devis → lien en bio

#CoolRoof #ToitureIndustrielle #PeintureReflective #EfficaciteEnergetique #Helios #RoofCoating #BuildingSolutions #FacilityManagement #BatimentDurable #Isolation"""

# ─── UPLOAD IMAGE BUFFER ──────────────────────────────────────────────────────

def upload_image_url_to_buffer(image_url: str) -> str | None:
    """Upload depuis une URL publique via mutation Buffer correcte."""
    mutation = """mutation UploadMedia($input: UploadMediaInput!) {
      uploadMedia(input: $input) { id url }
    }"""
    try:
        # Télécharger l'image depuis GitHub
        img_response = requests.get(image_url, timeout=30)
        if img_response.status_code != 200:
            print(f"⚠️  Image non trouvée : {image_url}")
            return None

        ext = image_url.split(".")[-1].lower()
        mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                    "webp": "image/webp", "heic": "image/heic"}
        mime_type = mime_map.get(ext, "image/jpeg")
        filename = image_url.split("/")[-1]

        files = {
            "operations": (None, json.dumps({
                "query": mutation,
                "variables": {"input": {"organizationId": BUFFER_ORG_ID, "file": None}}
            })),
            "map": (None, json.dumps({"0": ["variables.input.file"]})),
            "0": (filename, img_response.content, mime_type)
        }
        response = requests.post(
            "https://api.buffer.com/graphql",
            headers={"Authorization": f"Bearer {BUFFER_TOKEN}"},
            files=files,
            timeout=60
        )
        data = response.json()
        if "errors" in data:
            print(f"⚠️  Upload image échoué : {data['errors']}")
            return None
        media_id = data["data"]["uploadMedia"]["id"]
        print(f"✅ Image uploadée (ID: {media_id})")
        return media_id
    except Exception as e:
        print(f"⚠️  Erreur upload : {e}")
        return None

# ─── PROGRAMMER SUR BUFFER ────────────────────────────────────────────────────

def schedule_buffer_post(channel_id: str, text: str, media_id: str = None) -> bool:
    mutation = """mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess {
          post { id status }
        }
        ... on MutationError {
          userFacingMessage
        }
      }
    }"""

    variables = {"input": {
        "channelId": channel_id,
        "text": text,
        "schedulingType": "automatic",
        "mode": "addToQueue"
    }}
    if media_id:
        variables["input"]["mediaIds"] = [media_id]

    try:
        response = requests.post(
            "https://api.buffer.com/graphql",
            headers={"Authorization": f"Bearer {BUFFER_TOKEN}", "Content-Type": "application/json"},
            json={"query": mutation, "variables": variables},
            timeout=30
        )
        data = response.json()
        if "errors" in data:
            print(f"❌ Erreur Buffer : {data['errors']}")
            return False
        result = data.get("data", {}).get("createPost", {})
        if "post" in result:
            print(f"✅ Post envoyé ! ID: {result['post']['id']}")
            return True
        elif "userFacingMessage" in result:
            print(f"❌ Erreur Buffer : {result['userFacingMessage']}")
            return False
        else:
            print(f"⚠️  Réponse inattendue : {data}")
            return False
    except Exception as e:
        print(f"❌ Erreur : {e}")
        return False

# ─── JOBS PLANIFIÉS ───────────────────────────────────────────────────────────

def job_linkedin():
    print(f"\n[{datetime.now().strftime('%d/%m/%Y %H:%M')}] 📤 Job LinkedIn")
    text = generate_linkedin_text()
    ok = schedule_buffer_post(LINKEDIN_CHANNEL, text)
    if ok:
        history = load_history()
        history["posts_linkedin"] = history.get("posts_linkedin", 0) + 1
        save_history(history)
        print(f"   Total LinkedIn : {history['posts_linkedin']}")

def job_instagram():
    print(f"\n[{datetime.now().strftime('%d/%m/%Y %H:%M')}] 📸 Job Instagram")
    image_name = pick_next_image()
    if not image_name:
        print("   ⛔ Arrêt Instagram — plus d'images.")
        return

    caption = generate_instagram_caption(image_name)

    # URL publique de l'image (depuis le repo GitHub)
    image_url = f"{IMAGES_API}/{image_name}"
    media_id = upload_image_url_to_buffer(image_url)

    ok = schedule_buffer_post(INSTAGRAM_CHANNEL, caption, media_id)
    if ok:
        history = load_history()
        history.setdefault("used_instagram", []).append(image_name)
        history["posts_instagram"] = history.get("posts_instagram", 0) + 1
        save_history(history)
        print(f"   Total Instagram : {history['posts_instagram']}")

# ─── SCHEDULER ────────────────────────────────────────────────────────────────

def start_scheduler():
    print("=" * 55)
    print("  HÉLIOS Auto-Post — Démarrage Railway")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 55)
    print("  LinkedIn  : mardi + vendredi à 09:00")
    print("  Instagram : lundi à 09:00")
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
