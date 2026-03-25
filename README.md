# HÉLIOS Auto-Post — Déploiement Railway

## Structure du projet
```
helios-autopost/
├── main.py           ← script principal
├── requirements.txt  ← dépendances Python
├── Procfile          ← commande Railway
├── images.json       ← liste des noms d'images Instagram
└── images/           ← tes photos (hébergées sur GitHub)
    ├── chantier_01.jpg
    └── ...
```

---

## Étape 1 — Créer le repo GitHub

1. Va sur github.com → New repository
2. Nom : `helios-autopost`
3. Public (pour que les images soient accessibles via URL)
4. Clone en local ou upload les fichiers directement

---

## Étape 2 — Ajouter tes images

- Mets tes photos dans le dossier `images/`
- Mets à jour `images.json` avec les noms exacts :
```json
[
  "chantier_marseille.jpg",
  "toiture_lyon.png",
  "airbus_marignane.jpg"
]
```
- Les images seront accessibles via :
  `https://raw.githubusercontent.com/TON_USER/helios-autopost/main/images/NOM.jpg`

---

## Étape 3 — Déployer sur Railway

1. Va sur railway.app → New Project → Deploy from GitHub
2. Sélectionne `helios-autopost`
3. Railway détecte le `Procfile` automatiquement

---

## Étape 4 — Variables d'environnement Railway

Dans Railway → ton projet → Variables, ajoute :

| Variable | Valeur |
|----------|--------|
| `BUFFER_TOKEN` | `pINUW9ktK31Xg3eTnjNr3Go0Bv0nHVDF3cYR30cxXD8` |
| `BUFFER_ORG_ID` | `69a6b2465c9ccf1c796f5498` |
| `LINKEDIN_CHANNEL` | `69a6b59e3f3b94a1210ec7e6` |
| `INSTAGRAM_CHANNEL` | `69c29a79af47dacb694d4a21` |
| `ANTHROPIC_API_KEY` | `ta-clé-anthropic` |
| `ALERT_EMAIL` | `ton@email.com` |
| `SMTP_FROM` | `helios@gmail.com` |
| `SMTP_PASSWORD` | `mot-de-passe-app-gmail` |
| `IMAGES_API_URL` | `https://raw.githubusercontent.com/TON_USER/helios-autopost/main/images` |

---

## Étape 5 — Mot de passe app Gmail (pour l'alerte email)

1. Google Account → Sécurité → Validation en 2 étapes (activer)
2. Puis : Mots de passe des applications → Générer
3. Colle le mot de passe généré dans `SMTP_PASSWORD`

---

## Ajouter de nouvelles images plus tard

1. Ajoute les fichiers dans `images/` sur GitHub
2. Mets à jour `images.json` avec les nouveaux noms
3. Railway redéploie automatiquement

---

## Planning de publication

| Jour | Réseau | Type |
|------|--------|------|
| Lundi 9h00 | Instagram | Image + légende |
| Mardi 9h00 | LinkedIn | Texte (storytelling / technique / preuve sociale) |
| Vendredi 9h00 | LinkedIn | Texte (format aléatoire) |
