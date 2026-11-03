# 🏛️ Architecture Technique & Schéma des Flux

Ce document détaille l'architecture logicielle, la chaîne de traitement de données et les mécanismes de sécurité de la solution **Le calendrier Dunièrois de Maxime JACQUIOT** pour la commune de Dunières et le Haut Pays du Velay Communauté.

---

## 1. Vue d'Ensemble de l'Architecture

La solution repose sur une architecture **Jamstack 100 % Cloud**, serverless et à coût nul :
- **Orchestrateur & Exécution** : GitHub Actions (tâches planifiées Cron quotidiennes à 06h00 et déclenchement manuel).
- **Moteur de traitement** : Scripts Python 3.11 modulaires (collecte, enrichissement récursif, IA).
- **Modèle d'Intelligence Artificielle** : Google Gemini API (tri déontologique, extraction temporelle et catégorisation).
- **Stockage de Données** : Fichier plat `web/data.json` mis à jour de façon déterministe.
- **Hébergement Frontend** : GitHub Pages (haute disponibilité, CDN mondial, zéro maintenance serveur).
- **Interface Utilisateur** : Dépliant triptyque 3D minimaliste avec calendriers 2x7 (-14j / +14j), vue Aujourd'hui chronologique et popups dynamiques par jour.

```mermaid
flowchart TD
    subgraph Sources["1. Sources Locales"]
        S1["Illiwap Dunières (43087)"]
        S2["Illiwap Haut Pays du Velay"]
        S3["La Commère 43 (Filtre Dunières)"]
        S4["Le Progrès (Haute-Loire - Zone 43220)"]
    end

    subgraph Scrapers["2. Collecte & Enrichissement Récursif"]
        C1["Scrapers Multi-Sources"]
        C2{"Détection Lien Externe ?"}
        C3["Résolveur Calaméo / Liseuse"]
        C4["Extracteur PDF / Arrêtés"]
    end

    subgraph AI["3. Filtrage & Structuration IA"]
        AI1["Filtre Déontologique Mandat Public"]
        AI2["Extraction Dates, Heures & Tarifs"]
        AI3["Catégorisation Thématique & Nature"]
    end

    subgraph Build["4. Pipeline & Génération"]
        P1["Normalisation & Fenêtre Glissante (-14j / Aujourd'hui / +14j)"]
        P2["Génération web/data.json"]
        P3["Git Commit / GitHub Pages Deploy"]
    end

    subgraph Delivery["5. Dépliant Triptyque & Diffusion"]
        W1["Volet Passé : Calendrier 2x7 (-14 jours)"]
        W2["Volet Central : Aujourd'hui (Chronologique, Heures, Prix)"]
        W3["Volet Avenir : Calendrier 2x7 (+14 jours)"]
        W4["Popup Dynamique Plein Écran par Jour"]
    end

    S1 --> C1
    S2 --> C1
    S3 --> C1
    S4 --> C1
    C1 --> C2
    C2 -- Oui --> C3
    C2 -- Oui --> C4
    C2 -- Non --> AI1
    C3 --> AI1
    C4 --> AI1
    AI1 --> AI2
    AI2 --> AI3
    AI3 --> P1
    P1 --> P2
    P2 --> P3
    P3 --> W1
    P3 --> W2
    P3 --> W3
    W1 --> W4
    W2 --> W4
    W3 --> W4
```

---

## 2. Conception de l'Interface : Dépliant Triptyque

L'interface est conçue selon la métaphore tactile d'un **dépliant papier triptyque à trois volets** :

1. **Volet Central (« Aujourd'hui »)** :
   - Foyer principal d'ouverture de l'application.
   - Événements actifs ordonnés **chronologiquement**.
   - Visibilité immédiate des 3 piliers d'identification : **l'horaire précis**, **la nature de l'événement** et **le tarif / prix**.

2. **Volets Latéraux Pliés (Effet 3D)** :
   - Sur grand écran, des rabats inclinés en 3D avec ombrage de pli révèlent les deux autres pages sur les côtés de l'écran.
   - Clic direct sur le volet de gauche ou la flèche gauche `◀` pour déplier le passé.
   - Clic direct sur le volet de droite ou la flèche droite `▶` pour déplier l'avenir.

3. **Calendriers 2 Lignes × 7 Colonnes (14 Jours)** :
   - Dans le volet passé (-14 jours) et avenir (+14 jours), la grille organise exactement 14 jours.
   - Chaque case affiche en direct **l'horaire et le titre complet** sans troncature brutale.
   - Les jours calmes restent épurés pour faire ressortir instantanément les journées actives.

4. **Popup Dynamique Plein Écran** :
   - Clic sur n'importe quel jour pour ouvrir une vue détaillée de toute la journée.
   - Navigation jour par jour intégrée (`◀ Jour` / `Jour ▶`) sans quitter la fenêtre modale.
