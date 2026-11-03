# 📅 Le calendrier Dunièrois de Maxime JACQUIOT

Portail d'information citoyenne et calendrier interactif automatisé au service des administrés de la commune de **Dunières (Haute-Loire, 43220)** et de la communauté de communes **Haut Pays du Velay Communauté**.

Ce projet est une solution **100 % Cloud, autonome et sans serveur**, conçue pour collecter, trier, enrichir et publier quotidiennement l'actualité locale et associative sans nécessiter d'ordinateur allumé ni d'infrastructure payante (sans Supabase, sans base de données externe complexe).

---

## 🎯 Objectifs du Projet

En tant qu'élu local, l'enjeu est de simplifier l'accès à l'information publique en décloisonnant les différents canaux de communication :
1. **Centraliser l'information municipale et intercommunale** éparse (applications mobiles, presse locale, agendas numériques).
2. **Résoudre les liens profonds en 2 étapes** : extraire automatiquement le contenu des annonces renvoyant vers des liseuses en ligne (ex. Calaméo), des arrêtés ou affiches PDF.
3. **Assurer un tri intelligent par IA** : filtrer rigoureusement le contenu d'intérêt public lié au mandat local (travaux, manifestations, vie associative, arrêtés, séances de conseil) en excluant toute information privée.
4. **Offrir une expérience minimaliste en dépliant triptyque 3 volets** :
   - ⏪ **Volet Passé (-14 jours)** : Calendrier rétrospectif de 2 lignes × 7 colonnes avec heure et titre lisibles en 1 coup d'œil.
   - 📍 **Volet Aujourd'hui (Central)** : Événements actifs du jour triés par ordre chronologique avec mise en valeur immédiate des horaires, des tarifs et de la nature de l'événement.
   - ⏩ **Volet Avenir (+14 jours)** : Calendrier prévisionnel de 2 lignes × 7 colonnes avec lisibilité directe des 14 prochains jours.
   - 🔍 **Popup dynamique du jour** : Fiche détaillée prenant la place de l'écran lors du clic sur n'importe quel jour, avec navigation fluide jour par jour.
5. **Déploiement statique ultra-rapide** : Publication automatique quotidienne via GitHub Actions vers GitHub Pages avec un fichier structuré `data.json`.

---

## 🏗️ Architecture Fonctionnelle

```
[ Sources Locales ]
  ├── Illiwap Dunières (43087)
  ├── Illiwap Haut Pays du Velay
  ├── La Commère 43 (Filtre strict Dunières & Comcom)
  └── Le Progrès (Haute-Loire / Filtre strict Dunières)
         │
         ▼
[ Scrapers & Résolution Récursive ]
  └── Détection des liens externes (Calaméo, PDF, arrêtés, affiches)
         │
         ▼
[ Filtrage & Normalisation IA (Gemini) ]
  ├── Tri d'intérêt public & exclusion faits divers / vie privée
  ├── Catégorisation thématique & nature de l'activité
  └── Extraction normalisée des dates, heures & tarifs
         │
         ▼
[ Génération data.json & Déploiement ]
  └── GitHub Actions (Cron 06h00 Europe/Paris & manuel)
         │
         ▼
[ Vitrine Dépliant Triptyque (Tailwind CSS) ]
  ├── Volet Gauche : Passé (-14j en grille 2x7)
  ├── Volet Central : Aujourd'hui (Chronologique, Heures, Prix, Types)
  ├── Volet Droit : Avenir (+14j en grille 2x7)
  └── Popup dynamique plein écran par jour
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
│   ├── utils/                   # Gestion des dates, fusions et générateur data.json
│   └── main.py                  # Point d'entrée du pipeline de scraping & export
├── web/
│   ├── index.html               # Vitrine dépliant triptyque responsive & minimaliste
│   ├── app.js                   # Moteur interactif (calendriers 2x7, popups, tri horaire)
│   └── data.json                # Données compilées prêtes pour le frontend
├── requirements.txt             # Dépendances Python
├── ARCHITECTURE.md              # Schémas et documentation technique approfondie
└── ROADMAP.md                   # Suivi des jalons de développement
```

---

## 🚀 Fonctionnement du Déploiement

Le projet se déploie automatiquement sur **GitHub Pages** :
* **Automatique** : Tous les matins à 06:00 (heure de Paris) via le workflow GitHub Actions.
* **À la demande** : Depuis l'onglet **Actions** de GitHub, en cliquant sur **« Run workflow »** sur la branche `main`.
