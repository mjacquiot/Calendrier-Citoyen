# 🏛️ Portail Citoyen & Calendrier Automatisé – Dunières & Haut Pays du Velay

Portail d'information citoyenne et calendrier interactif automatisé au service des administrés de la commune de **Dunières (Haute-Loire, 43220)** et de la communauté de communes **Haut Pays du Velay Communauté**.

Ce projet est une solution **100 % Cloud, autonome et sans serveur**, conçue pour collecter, trier, enrichir et publier quotidiennement l'actualité locale et associative sans nécessiter d'ordinateur allumé ni d'infrastructure payante (sans Supabase, sans base de données externe complexe).

---

## 🎯 Objectifs du Projet

En tant qu'élu local, l'enjeu est de simplifier l'accès à l'information publique en décloisonnant les différents canaux de communication :
1. **Centraliser l'information municipale et intercommunale** éparse (applications mobiles, presse locale, agendas numériques).
2. **Résoudre les liens profonds en 2 étapes** : extraire automatiquement le contenu des annonces renvoyant vers des liseuses en ligne (ex. Calaméo), des arrêtés ou affiches PDF.
3. **Assurer un tri intelligent par IA** : filtrer rigoureusement le contenu d'intérêt public lié au mandat local (travaux, manifestations, vie associative, arrêtés, séances de conseil) en excluant toute information privée.
4. **Offrir un calendrier glissant dynamique en 3 volets** :
   - ⏪ **Rétrospective (-15 jours)** : Ce qui s'est passé récemment (comptes-rendus, arrêtés passés).
   - 📍 **Aujourd'hui** : Les événements, alertes et permanences du jour.
   - ⏩ **Agenda à venir (+15 jours)** : Événements associatifs, conseils municipaux/communautaires, chantiers annoncés.
5. **Déploiement statique ultra-rapide** : Publication automatique quotidienne via GitHub Actions vers GitHub Pages avec un fichier structuré `data.json`.

---

## 🏗️ Architecture Fonctionnelle

```
[ Sources Locales ]
  ├── Illiwap Dunières (43087)
  ├── Illiwap Haut Pays du Velay
  ├── La Commère 43
  └── Le Progrès
         │
         ▼
[ Scrapers & Résolution Récursive ]
  └── Détection des liens externes (Calaméo, PDF, arrêtés, affiches)
         │
         ▼
[ Filtrage & Normalisation IA (Gemini) ]
  ├── Tri d'intérêt public & exclusion vie privée
  ├── Catégorisation thématique
  └── Extraction normalisée des dates & lieux
         │
         ▼
[ Génération data.json & Déploiement ]
  └── GitHub Actions (Cron 06h00 Europe/Paris)
         │
         ▼
[ Vitrine GitHub Pages (Tailwind CSS) ]
  ├── Volet 1 : -15 jours (Rétrospective)
  ├── Volet 2 : Aujourd'hui
  └── Volet 3 : +15 jours (Agenda)
```

Pour plus de détails techniques, voir [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 📁 Arborescence du Projet

```text
.
├── .github/
│   └── workflows/
│       └── daily-pipeline.yml   # Workflow automatisé quotidien (6h/7h)
├── config/
│   └── sources.json             # Paramétrage des sources, mots-clés et catégories
├── src/
│   ├── scrapers/                # Modules de collecte (Illiwap, La Commère 43, Le Progrès)
│   ├── enrichment/              # Résolution récursive (Calaméo, extraction PDF/images)
│   ├── ai/                      # Analyse, filtrage de confidentialité et structuration IA
│   ├── notifications/           # Alertes WhatsApp (CallMeBot) et résumés pour l'élu
│   └── utils/                   # Gestion des dates, fusion et exports JSON
├── web/
│   ├── index.html               # Vitrine responsive moderne (HTML5 + Tailwind CSS)
│   ├── app.js                   # Moteur d'affichage du calendrier en 3 volets
│   └── data.json                # Fichier de données consommé par l'interface web
├── .env.example                 # Modèle des variables d'environnement
├── ARCHITECTURE.md              # Documentation de l'architecture logicielle
├── ROADMAP.md                   # Feuille de route par jalons
└── README.md                    # Présentation et prise en main du projet
```

---

## 🚀 Démarrage Rapide

### Prérequis Locaux (Optionnel pour le développement)
- Python 3.11 ou supérieur
- Clé API Google Gemini (gratuite avec quotas généreux)

### Installation locale
1. Clonez le dépôt :
   ```bash
   git clone https://github.com/<votre-organisation-ou-nom>/portail-dunieres.git
   cd portail-dunieres
   ```

2. Créez un environnement virtuel Python :
   ```bash
   python -m venv .venv
   # Windows (PowerShell) :
   .venv\Scripts\Activate.ps1
   # Linux/Mac :
   source .venv/bin/activate
   ```

3. Installez les dépendances :
   ```bash
   pip install -r requirements.txt
   ```

4. Configurez vos variables :
   ```bash
   cp .env.example .env
   ```
   Renseignez votre `GEMINI_API_KEY` dans le fichier `.env`.

5. Lancez le serveur local pour tester le portail web :
   ```bash
   cd web
   python -m http.server 8000
   ```
   Accédez à [http://localhost:8000](http://localhost:8000).

---

## ⚙️ Configuration GitHub Actions & Secrets

Pour que la solution s'exécute automatiquement chaque matin dans le Cloud GitHub :

1. Rendez-vous dans les paramètres du dépôt GitHub : **Settings > Secrets and variables > Actions**.
2. Créez les secrets suivants :
   - `GEMINI_API_KEY` : Votre clé Google AI Studio.
   - `CALLMEBOT_PHONE` *(optionnel)* : Numéro international pour le compte-rendu WhatsApp (ex. `+336XXXXXXXX`).
   - `CALLMEBOT_API_KEY` *(optionnel)* : Clé API CallMeBot.
3. Activez **GitHub Pages** dans **Settings > Pages** en sélectionnant la branche `main` et le dossier `/web` (ou via GitHub Actions Deployment).

---

## 🔒 Confidentialité & Déontologie Électorale

Le module d'analyse IA intègre des règles strictes :
- **Intérêt public exclusif** : Seuls les événements municipaux, associatifs, réglementaires, scolaires et culturels ouverts au public sont retenus.
- **Protection de la vie privée (RGPD)** : Aucune donnée nominative privée, litige individuel ou échange personnel n'est collecté ni publié.
- **Transparence locale** : Chaque information affiche systématiquement sa source d'origine et un lien vers la publication officielle.

---

## 📌 Feuille de Route

Consultez [ROADMAP.md](ROADMAP.md) pour suivre l'état d'avancement des 4 jalons d'implémentation.
