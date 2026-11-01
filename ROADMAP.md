# 🗺️ Feuille de Route d'Implémentation (Roadmap)

Plan de développement par jalons du projet de portail citoyen et calendrier automatisé pour Dunières et le Haut Pays du Velay Communauté.

---

## 📍 Vue Globale des Jalons

| Jalon | Titre | Objectif Principal | Statut |
| :--- | :--- | :--- | :--- |
| **Jalon 1** | **Environnement & Architecture** | Arborescence, spécifications techniques, documentation de référence | 🟢 **Validé** |
| **Jalon 2** | **Collecte & Résolution Récursive** | Scrapers Illiwap, Commère 43, Progrès + Résolveurs Calaméo/PDF | 🟢 **Validé** |
| **Jalon 3** | **Intelligence Artificielle & Données** | Filtrage public/privé, structuration JSON et fenêtrage 3 volets | 🟢 **Validé** |
| **Jalon 4** | **Vitrine Web, Déploiement & Alertes** | Interface Tailwind responsive, GitHub Actions Cloud, WhatsApp | 🟢 **Opérationnel** |

---

## 📋 Détail des Jalons

### 🟢 Jalon 1 : Environnement & Architecture (Terminé)
- [x] Initialisation de l'arborescence modulaire (`src/`, `web/`, `.github/workflows/`, `config/`).
- [x] Définition du modèle de configuration des sources (`config/sources.json`).
- [x] Rédaction du guide de démarrage et de présentation (`README.md`).
- [x] Rédaction de l'architecture logicielle et des flux récursifs (`ARCHITECTURE.md`).
- [x] Création du modèle des variables d'environnement (`.env.example`) et `.gitignore`.
- [x] Validation de l'étape 1 avec l'utilisateur.

---

### 🟢 Jalon 2 : Modules de Collecte Multi-Sources & Enrichissement Récursif (Terminé)
- [x] **Scraper Illiwap** :
  - Collecte de la station Dunières (code `43087`).
  - Collecte de la station Haut Pays du Velay Communauté.
  - Gestion approfondie des pages de détail, dates et pièces jointes.
- [x] **Scrapers Presse Locale** :
  - Connecteur recherche & RSS La Commère 43 (filtre Dunières / canton).
  - Connecteur Le Progrès (Haute-Loire).
- [x] **Moteur d'Enrichissement Récursif en 2 Étapes** :
  - Détection automatique d'URLs dans le corps des publications (`link_detector.py`).
  - Résolveur Calaméo (`calameo_resolver.py`) : extraction du titre, auteur, descriptif détaillé (villages/dates) et couverture.
  - Résolveur PDF (`pdf_resolver.py`) : extraction de texte in-memory avec `pypdf`.
  - Déduplication intelligente multi-sources (`recursive_manager.py`).
- [x] Validation sur données réelles en direct (`src/test_jalon2.py`).

---

### 🟢 Jalon 3 : Pipeline d'Analyse IA & Structuration des Données (Terminé)
- [x] **Intégration de l'évaluation déontologique** :
  - Filtrage strict : conservation exclusive des événements d'intérêt public lié au mandat communal/intercommunal (`src/ai/classifier.py`).
  - Exclusion formelle : faits divers individuels (accidents, cambriolages, délits), vie privée et publicités commerciales privées.
  - Compatibilité double mode : API Google Gemini (`google-genai` / `gemini-2.5-flash`) et moteur heuristique républicain sécurisé.
- [x] **Extraction Temporelle & Géographique** :
  - Détection des dates de début et fin (`src/utils/date_helpers.py`).
  - Normalisation des lieux et catégorisation thématique standardisée (`src/ai/schemas.py`).
- [x] **Algorithme de Fenêtrage Glissant en 3 Volets** :
  - ⏪ **Rétrospective** : $[J-15, J-1]$
  - 📍 **Aujourd'hui** : $J$
  - ⏩ **Agenda à venir** : $[J+1, J+15]$
- [x] Génération atomique de `web/data.json` avec compteurs et métadonnées (`src/utils/data_generator.py`).

---

### 🟢 Jalon 4 : Vitrine Web Citoyenne, Déploiement Cloud & Alertes (Opérationnel)
- [x] **Vitrine Web Responsive Moderne (`web/`)** :
  - Interface soignée HTML5 + Tailwind CSS (`web/index.html`).
  - Moteur dynamique réactif (`web/app.js`) consommant `data.json`.
  - Volets glissants interactifs avec compteurs d'événements.
  - Filtres instantanés par catégories (Vie Municipale, Travaux, Associations, Culture, Alertes).
  - Barre de recherche en temps réel.
  - Boutons d'accès direct vers les documents Calaméo et arrêtés PDF.
- [x] **Pipeline Cloud 100% Autonome (`.github/workflows/daily-pipeline.yml`)** :
  - Déclenchement automatique chaque matin (05:00 UTC / 06:00 CET).
  - Exécution du script maître `src/main.py` sans dépendance machine.
  - Déploiement automatique vers **GitHub Pages**.
- [x] **Notification Élu WhatsApp (`src/notifications/whatsapp_bot.py`)** :
  - Synthèse matinale via CallMeBot avec compteurs et alertes du jour.
- [x] **Automation Antigravity locale intégrée** :
  - Sidecar de synchronisation planifiée prêt dans le tableau de bord Automations.
