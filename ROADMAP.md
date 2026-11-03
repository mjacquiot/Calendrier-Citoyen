# 🗺️ Feuille de Route d'Implémentation (Roadmap)

Plan de développement par jalons du projet de portail citoyen et calendrier automatisé pour Dunières et le Haut Pays du Velay Communauté.

---

## 📍 Vue Globale des Jalons

| Jalon | Titre | Objectif Principal | Statut |
| :--- | :--- | :--- | :--- |
| **Jalon 1** | **Environnement & Architecture** | Arborescence, spécifications techniques, documentation de référence | 🟢 **Validé** |
| **Jalon 2** | **Collecte & Résolution Récursive** | Scrapers Illiwap, Commère 43, Progrès + Résolveurs Calaméo/PDF | 🟢 **Validé** |
| **Jalon 3** | **Intelligence Artificielle & Données** | Filtrage public/privé, structuration JSON et fenêtrage 3 volets | 🟢 **Validé** |
| **Jalon 4** | **Dépliant Triptyque, Déploiement & Alertes** | Interface triptyque minimaliste 2x7, popups, GitHub Actions Cloud | 🟢 **Opérationnel** |

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
  - Connecteur Le Progrès (Haute-Loire / filtre Dunières).
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
- [x] **Extraction d'entités structurées** :
  - Extraction et normalisation des dates, plages horaires et lieux.
  - Attribution des catégories thématiques officielles.
- [x] **Génération du fichier de production** :
  - Calcul déterministe de la date de référence et des 3 volets temporels.
  - Export propre dans `web/data.json`.

---

### 🟢 Jalon 4 : Vitrine Dépliant Triptyque Minimaliste & Déploiement Cloud (Terminé)
- [x] **Interface Dépliant Triptyque à 3 Volets** :
  - **Volet Gauche (Passé)** : Calendrier 2 lignes × 7 colonnes pour les 14 jours écoulés avec horaires et titres nets.
  - **Volet Central (Aujourd'hui)** : Point du jour en direct, tri chronologique des événements, mise en avant claire des heures, des tarifs et de la nature de l'activité.
  - **Volet Droit (Avenir)** : Calendrier prévisionnel 2 lignes × 7 colonnes pour les 14 prochains jours.
  - **Popup Dynamique Plein Écran** : Fiche complète au clic sur n'importe quel jour avec parcours jour par jour.
  - **Épuration Minimaliste** : En-tête compact "Le calendrier Dunièrois de Maxime JACQUIOT", suppression des sections d'archive redondantes.
- [x] **Automatisation GitHub Actions & GitHub Pages** :
  - Exécution quotidienne planifiée (06:00 CET).
  - Déclenchement manuel (`workflow_dispatch`).
  - Déploiement automatique vers GitHub Pages.
