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
- **Interface Utilisateur** : Format Agenda Professionnel pleine largeur (cases larges par créneau, calcul automatique de la durée, tri chronologique, mini-rubans 14 jours et popups dynamiques).

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

    subgraph Delivery["5. Format Agenda Pro & Diffusion"]
        W1["Volet Passé : Mini-ruban 14j + Lignes Larges (-14j)"]
        W2["Volet Central : Aujourd'hui (Planning Chronologique, Durées, Heures, Prix)"]
        W3["Volet Avenir : Mini-ruban 14j + Lignes Larges (+14j)"]
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

## 2. Conception de l'Interface : Agenda Professionnel

L'interface adopte la structure des outils de planification professionnelle (Google Agenda, Outlook) pour une lisibilité absolue :

1. **Volet Central (« Aujourd'hui »)** :
   - Foyer principal d'ouverture de l'application.
   - Événements actifs ordonnés **chronologiquement du matin au soir**.
   - **Une case large par créneau horaire** avec rail temporel gauche :
     - Heure de début et heure de fin (ex: `09:00 ➔ 12:00` ou `14:00 ➔ 19:00`).
     - Durée calculée automatiquement (ex: `⏱️ 3h`, `⏱️ 5h`, `⏱️ 1h`).
   - Corps pleine largeur : type d'activité (`🎭 Spectacle`, `🥾 Sport`, `🚧 Travaux`...), tarif (`🎟️ Gratuit / Entrée libre`), titre complet non tronqué et résumé.

2. **Volets « Passé (-14j) » et « Avenir (+14j) »** :
   - **Mini-Ruban 14 Jours** : 2 rangées de 7 pastilles compactes en haut de page donnant la vue d'ensemble immédiate des 14 jours (pastille bleue avec compteur si événement, neutre si calme). Clic direct pour défiler vers le jour.
   - **Flux Chronologique des Jours Actifs** : Affichage uniquement des jours contenant des événements en lignes larges pleine largeur. Zéro gaspillage d'espace, zéro coupure de titre.

3. **Popup Dynamique Plein Écran** :
   - Fiche complète de l'événement avec affiche grand format, arrêté PDF ou agenda Calaméo consultable directement.
   - Navigation jour par jour intégrée sans quitter la fenêtre.
