# 📅 Calendrier Citoyen de Dunières • J-7 / J+7

Portail d'information citoyenne et calendrier interactif automatisé au service des administrés de la commune de **Dunières (Haute-Loire, 43220)** et de la communauté de communes **Haut Pays du Velay Communauté**.

Ce projet est une solution **100 % Cloud, autonome et sans serveur**, conçue pour collecter, trier, enrichir et publier quotidiennement l'actualité municipale et associative sans nécessiter d'ordinateur allumé ni d'infrastructure payante.

---

## 🎯 Objectifs du Projet

En tant qu'élu local, l'enjeu est de simplifier l'accès à l'information publique en décloisonnant les différents canaux de communication :
1. **Centraliser l'information municipale et intercommunale** éparse (Illiwap, presse locale, ajouts manuels éventuels).
2. **Résoudre les liens profonds en 2 étapes** : extraire automatiquement le contenu des annonces renvoyant vers des liseuses en ligne (ex. Calaméo) ou des arrêtés PDF.
3. **Assurer un tri déontologique par IA (Gemini + repli heuristique)** : conserver exclusivement le contenu d'intérêt public local (travaux, manifestations ouvertes, vie associative, arrêtés, séances de conseil, services publics) et exclure faits divers, vie privée, publicités/ouvertures commerciales privées et comptes-rendus passés sans événement.
4. **Offrir une expérience épurée type Google Calendar (fenêtre glissante J-7 / J+7)** :
   - 🗓️ **Ruban interactif 15 jours** : vue synthétique des 7 jours passés, d'aujourd'hui et des 7 prochains jours avec pastilles de catégories.
   - 📍 **Agenda du jour (Grille horaire 07h–23h ou Liste)** : zone « Toute la journée », gestion multi-créneaux et chevauchements, ligne « Maintenant » sur `Europe/Paris`.
   - ⏪ **7 jours passés** & ⏩ **7 jours à venir** : rubans 7 jours et flux chronologique en cartes détaillées.
   - 🔍 **Modale fiche complète & exports** : partage par lien direct (`?day=...&event=...`), ajout à Google Calendar et téléchargement/abonnement `.ics` (`web/calendar.ics`).
5. **Déploiement statique ultra-rapide** : publication automatique quotidienne via GitHub Actions vers GitHub Pages avec `web/data.json` (schéma v2) et `web/calendar.ics`.

---

## 🏗️ Architecture Fonctionnelle

```
[ Sources Locales ]
  ├── Illiwap Dunières (43087)
  ├── Illiwap Haut Pays du Velay
  ├── La Commère 43 (Synthèse presse + lien source)
  ├── Le Progrès (Haute-Loire / Filtre territoire)
  └── config/manual_events.json (Ajouts manuels optionnels)
         │
         ▼
[ Déduplication & Enrichissement Récursif ]
  ├── Déduplication sensible aux dates (préserve les récurrences)
  └── Résolution Calaméo & PDF en mémoire (avec cache par exécution)
         │
         ▼
[ Filtrage & Structuration IA (Gemini + Cache + Repli Heuristique) ]
  ├── Tri déontologique & exclusion faits divers / commercial / privé
  ├── Catégorisation stricte, extraction lieu, tarif, dates & créneaux multiples
  └── Politique presse : synthèse uniquement (jamais d'article intégral recopié)
         │
         ▼
[ Génération web/data.json (v2) + web/calendar.ics ]
  ├── Garde-fou anti-écrasement si une source est en panne
  └── GitHub Actions (Cron 04:17 UTC, tests CI & GitHub Pages)
```

Pour plus de détails techniques, voir [ARCHITECTURE.md](ARCHITECTURE.md).

---

## ✍️ Ajouter un événement manuellement (optionnel)

Le fichier [config/manual_events.json](config/manual_events.json) accepte un tableau JSON d'événements officiels complémentaires (ex. permanence exceptionnelle, réunion publique) :

```json
[
  {
    "id": "manual_reunion_budget_2026",
    "title": "Réunion publique sur le budget communal",
    "date": "2026-11-26",
    "time": "de 18h30 à 20h00",
    "location": "Salle des Associations, Dunières",
    "description": "Présentation des orientations budgétaires ouverte à tous les habitants.",
    "url": "https://station.illiwap.com/fr/public/43087"
  }
]
```

---

## 📁 Arborescence du Projet

```text
.
├── .github/workflows/
│   ├── ci.yml                   # Tests automatisés (Python + JS) & déploiement web
│   └── daily-pipeline.yml       # Pipeline quotidien automatisé + cache IA + GitHub Pages
├── config/
│   ├── sources.json             # Paramétrage des sources, fenêtre J-7/J+7, mots-clés
│   └── manual_events.json       # Événements manuels optionnels
├── src/
│   ├── scrapers/                # Collecteurs (Illiwap, La Commère 43, Le Progrès)
│   ├── enrichment/              # Résolution récursive (Calaméo, PDF) & déduplication
│   ├── ai/                      # Schéma strict, Gemini (+ cache) & repli heuristique
│   ├── notifications/           # Résumé quotidien WhatsApp (CallMeBot)
│   ├── utils/                   # Client HTTP avec retry/masquage, dates, texte, générateur JSON/ICS
│   └── main.py                  # Orchestrateur principal
├── tests/                       # Suite de tests unitaires offline (unittest)
├── web/
│   ├── index.html               # Interface épurée type Google Calendar + PWA
│   ├── app.js                   # Moteur interactif, deep-linking, .ics, a11y
│   ├── favicon.svg              # Icône vectorielle
│   ├── manifest.json            # Manifeste PWA léger
│   ├── data.json                # Données structurées v2 (générées)
│   └── calendar.ics             # Flux iCalendar RFC 5545 (généré)
├── requirements.txt
├── ARCHITECTURE.md
└── ROADMAP.md
```

---

## 🧪 Tests locaux & Exécution

```bash
# Exécuter tous les tests unitaires offline
python -m unittest discover -s tests -v

# Vérifier la syntaxe JavaScript
node --check web/app.js

# Exécuter le pipeline complet (génère web/data.json et web/calendar.ics)
python src/main.py
```
