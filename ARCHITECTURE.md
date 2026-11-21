# 🏛️ Architecture Technique & Schéma des Flux

Ce document détaille l'architecture logicielle, la chaîne de traitement de données et les mécanismes de fiabilité de la solution **Calendrier Citoyen de Dunières** pour la commune de Dunières et le Haut Pays du Velay Communauté.

---

## 1. Vue d'Ensemble de l'Architecture

La solution repose sur une architecture **Jamstack 100 % Cloud**, serverless et à coût nul :
- **Orchestrateur & CI/CD** : GitHub Actions (`daily-pipeline.yml` exécuté chaque matin à `04:17 UTC` + `ci.yml` pour les tests à chaque `push`/`PR` et le déploiement sur modification de `web/`).
- **Moteur de traitement** : Scripts Python 3.11 modulaires avec client HTTP `requests` doté de retries/backoff et masquage des paramètres sensibles dans les logs.
- **Modèle d'Intelligence Artificielle** : Google Gemini (`gemini-2.5-flash`) avec schéma Pydantic strict (`Literal` pour catégories, importance et nature éditoriale), cache disque persisté entre runs (`data/cache/classifier_cache.json`), support multimodal des affiches courtes et repli heuristique déterministe.
- **Stockage & Flux ouverts** :
  - `web/data.json` (schéma v2 sans duplication : objets complets dans `all_events`, références par ID dans `buckets`, garde-fou anti-écrasement en cas de panne source).
  - `web/calendar.ics` (flux iCalendar RFC 5545 prêt à l'abonnement).
- **Hébergement Frontend** : GitHub Pages (HTML/JS statique, manifeste PWA léger, zéro backend).

```mermaid
flowchart TD
    subgraph Sources["1. Sources Locales"]
        S1["Illiwap Dunières (43087)"]
        S2["Illiwap Haut Pays du Velay"]
        S3["La Commère 43 (Filtre territoire)"]
        S4["Le Progrès (Haute-Loire)"]
        S5["config/manual_events.json"]
    end

    subgraph DedupEnrich["2. Déduplication & Enrichissement"]
        D1["Déduplication titre + date"]
        C2{"Lien externe ?"}
        C3["Résolveur Calaméo"]
        C4["Extracteur PDF (pypdf)"]
    end

    subgraph AI["3. Filtrage & Structuration IA"]
        AI0{"Cache Gemini ?"}
        AI1["Gemini 2.5 Flash / Repli Heuristique"]
        AI2["Tri déontologique & politique presse"]
        AI3["Extraction dates, multi-créneaux, lieu & tarif"]
    end

    subgraph Build["4. Génération & Garde-fous"]
        P1["Fenêtre glissante J-7 / Aujourd'hui / J+7"]
        P2["Fusion anti-écrasement (schéma v2)"]
        P3["Export web/data.json + web/calendar.ics"]
    end

    subgraph Delivery["5. Interface Web & Alertes"]
        W1["Agenda du jour (Grille 07h-23h & Liste)"]
        W2["Ruban 15j + Vues 7j passés / 7j à venir"]
        W3["Modale détaillée, deep-link & export .ics"]
        W4["Synthèse WhatsApp CallMeBot (optionnelle)"]
    end

    S1 --> D1
    S2 --> D1
    S3 --> D1
    S4 --> D1
    S5 --> D1
    D1 --> C2
    C2 -- Oui --> C3
    C2 -- Oui --> C4
    C2 -- Non --> AI0
    C3 --> AI0
    C4 --> AI0
    AI0 -- Non --> AI1
    AI0 -- Oui --> P1
    AI1 --> AI2
    AI2 --> AI3
    AI3 --> P1
    P1 --> P2
    P2 --> P3
    P3 --> W1
    P3 --> W2
    P3 --> W3
    P3 --> W4
```

---

## 2. Conception de l'Interface : Vue Google Calendar Épurée

1. **Ruban interactif 15 jours (`J-7` → `Aujourd'hui` → `J+7`)** :
   - Grille 15 colonnes sur desktop et ruban horizontal scrollable sur mobile.
   - Pastilles colorées par catégorie indiquant d'un coup d'œil la densité des événements.
2. **Vue « Agenda du jour » (par défaut)** :
   - **Zone « Toute la journée »** pour les informations continues, arrêtés ou publications sans horaire fixe.
   - **Grille horaire `07h–23h`** avec calcul des colonnes en cas de chevauchements, affichage des événements multi-créneaux et ligne « Maintenant » sur `Europe/Paris`.
   - **Bascule Grille / Liste** instantanée et navigation clavier (`←` / `→` / `Échap`).
3. **Vues « 7j passés » & « 7j à venir »** :
   - Ruban compact 7 jours + cartes chronologiques cliquables et accessibles au clavier.
4. **Modale fiche événement** :
   - Affiche grand format, date, créneaux horaires, lieu, tarif explicite, pièce jointe Calaméo/PDF avec aperçu texte.
   - Liens d'action : source officielle, **+ Ajouter à Google Calendar**, téléchargement **`.ics`**, et **Partager** par lien direct (`?day=YYYY-MM-DD&event=...`).
