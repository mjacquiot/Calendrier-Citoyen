# 🗺️ Feuille de Route d'Implémentation (Roadmap)

Plan de développement par jalons du projet de portail citoyen et calendrier automatisé pour Dunières et le Haut Pays du Velay Communauté.

---

## 📍 Vue Globale des Jalons

| Jalon | Titre | Objectif Principal | Statut |
| :--- | :--- | :--- | :--- |
| **Jalon 1** | **Environnement & Architecture** | Arborescence, spécifications techniques, documentation de référence | 🟢 **Validé** |
| **Jalon 2** | **Collecte & Résolution Récursive** | Scrapers Illiwap, Commère 43, Progrès + Résolveurs Calaméo/PDF | 🟢 **Validé** |
| **Jalon 3** | **Intelligence Artificielle & Données** | Filtrage public/privé, structuration JSON v2, cache Gemini & conformité presse | 🟢 **Validé** |
| **Jalon 4** | **Interface Google Calendar & Déploiement** | Grille horaire J-7/J+7, ruban 15j, export `.ics`, deep-links, CI/CD & tests | 🟢 **Opérationnel** |

---

## 📋 Détail des Jalons

### 🟢 Jalon 1 : Environnement & Architecture (Terminé)
- [x] Initialisation de l'arborescence modulaire (`src/`, `web/`, `.github/workflows/`, `config/`, `tests/`).
- [x] Définition du modèle de configuration des sources (`config/sources.json`) et ajouts manuels (`config/manual_events.json`).
- [x] Rédaction de la documentation (`README.md`, `ARCHITECTURE.md`, `.env.example`).

### 🟢 Jalon 2 : Modules de Collecte Multi-Sources & Enrichissement Récursif (Terminé)
- [x] **Scraper Illiwap** : stations Dunières (`43087`) et Haut Pays du Velay, déduplication de cartes.
- [x] **Scrapers Presse Locale** : La Commère 43 et Le Progrès avec IDs stables et parsing RSS résilient.
- [x] **Moteur d'Enrichissement Récursif** : détection URLs, résolveurs Calaméo/PDF avec cache en mémoire, déduplication sensible aux dates.

### 🟢 Jalon 3 : Pipeline d'Analyse IA, Fiabilité & Conformité (Terminé)
- [x] **Schéma Pydantic strict (`schema_version: 2`)** : catégories `Literal`, tarif dédié, créneaux multiples.
- [x] **Cache disque Gemini + backoff exponentiel + lecture multimodale des affiches courtes**.
- [x] **Repli heuristique durci** : exclusion des portraits commerciaux, comptes-rendus sportifs passés et parutions sans événement ; isolation du texte principal des articles de presse.
- [x] **Conformité droit d'auteur & résilience** : synthèses presse sans recopie d'article intégral, garde-fou anti-écrasement si une source échoue, export `web/calendar.ics` RFC 5545.

### 🟢 Jalon 4 : Interface Google Calendar, Accessibilité & CI/CD (Opérationnel)
- [x] **Vue Google Calendar J-7 / Aujourd'hui / J+7** : grille horaire `07h–23h`, zone « Toute la journée », ruban 15 jours, recherche inter-jours.
- [x] **Sécurité & Accessibilité** : délégation d'événements sans `onclick` inline, sanitisation d'URL, focus trap modale, rôles ARIA et navigation clavier.
- [x] **Partage & Abonnement** : deep-linking (`?day=...&event=...`), balises Open Graph, manifeste PWA, téléchargement `.ics` unitaire et global.
- [x] **Tests automatisés & CI/CD** : suite `unittest` offline (`tests/`), workflow `ci.yml` + exécution quotidienne fiabilisée (`daily-pipeline.yml`).
