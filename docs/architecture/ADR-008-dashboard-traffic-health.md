# ADR 008 — Dashboard pages 3 & 4 (Trafic + Score santé)

**Statut :** Accepté
**Date :** 2026-05
**Auteur :** Colin

## Contexte

Le dashboard ParisMove AI livré en PR 1 contient les pages **Accueil**
et **Qualité de l'air**. La PR 3 a embarqué le **Coach IA**.

Pour boucler la couverture fonctionnelle (4 pages + chat), il manque :
- Une page **Trafic** pour visualiser les passages PRIM IDFM
- Une page **Score santé** interactive permettant à l'utilisateur de
  calculer la qualité d'un trajet entre 2 zones

## Décision

### Page Trafic (`3_Trafic.py`)

Affichage en **4 sections** :

1. **KPIs en haut** (4 cartes) : Total passages 24h, lignes actives,
   retard moyen, % de passages en retard.
2. **Top 10 lignes les plus en retard** : barchart horizontal avec
   couleur dégradée vert→jaune→rouge selon le retard.
3. **Heatmap heure × jour de la semaine** : grille 7×24 du retard
   moyen sur les 7 derniers jours.
4. **Filtre par mode de transport** dans la sidebar (Métro, RER, Bus,
   Tram, Train, ou "Tous"). Les KPIs restent globaux pour le contexte.

### Page Score santé (`4_Score_sante.py`)

Workflow interactif :

1. **Sélecteurs** : 2 dropdowns avec 10 zones prédéfinies IDF
   (Châtelet, La Défense, Gare du Nord, etc.).
2. **Bouton "Calculer"** : déclenche le calcul via le service
   `healthscore.scoring.score_journey`.
3. **Affichage du résultat** :
   - Carte d'en-tête colorée par grade (A→E) avec score /100
   - 3 sub-scores en metrics (Pollution, Météo, Trafic)
   - Conseil actionnable selon le grade
   - Avertissements éventuels (données manquantes, station >5km)
4. **Carte Folium** : tracé en vol d'oiseau du trajet + stations
   Airparif proches colorées par AQI.

## Justifications

### Pourquoi ces choix de viz pour le Trafic ?

- **KPIs synthétiques en haut** : règle d'or des dashboards data, on
  donne le contexte global d'abord avant le détail.
- **Top 10 horizontal** : plus lisible que vertical pour 10 items aux
  noms parfois longs (ex: "Bus 174 — Paris-Defense").
- **Heatmap** : la viz idéale pour visualiser des patterns à 2
  dimensions (heure × jour). Permet de repérer instantanément les
  heures de pointe et les jours problématiques.
- **Filtre mode dans la sidebar** : pratique commune Streamlit
  (sidebar = configuration, body = contenu).

### Pourquoi des zones prédéfinies pour le Score santé ?

- **UX accessible** : un utilisateur lambda ne connaît pas les
  coordonnées GPS de Châtelet. Un dropdown est immédiat.
- **Cohérence des données** : les 10 zones correspondent aux
  `DEFAULT_METEO_POINTS` du service ingestion, donc on a déjà
  des données météo récentes pour ces points.
- **Couverture suffisante** : Châtelet, La Défense, Gare du Nord,
  Saint-Lazare, Gare de Lyon, Montparnasse, Versailles, Saint-Denis,
  Boulogne, Créteil = 95% des trajets pertinents en IDF.
- **Évolution future** : l'ADR-007 prévoit d'ajouter un champ libre
  pour les power users en PR 5 si besoin.

### Pourquoi un tracé en vol d'oiseau ?

- **Pas de routage multimodal** dans le scope (cf. ADR-009 à venir
  pour l'API IDFM journey-planner).
- Le but est de **donner un repère visuel**, pas de calculer un
  itinéraire optimal. L'utilisateur comprend que le tracé est
  indicatif (il est en pointillés).
- Si on intègre IDFM journey-planner plus tard, on pourra
  facilement remplacer la `PolyLine` par les segments réels.

### Pourquoi afficher les stations Airparif sur la carte ?

- **Contexte spatial** : permet de visualiser quelle station a été
  utilisée pour calculer le sous-score Pollution.
- **Transparence scientifique** : si une station est loin du trajet,
  l'utilisateur le voit immédiatement (cohérent avec l'avertissement
  "station > 5 km" du healthscore).

## Conséquences

### Positives

- **Dashboard 4 pages complet** + chat IA → couvre toute la stack
- **Réutilisation maximale** : la page Score santé utilise 100% le
  service healthscore existant, aucun code dupliqué
- **Filtre par mode** : transforme une page statique en outil
  exploratoire (l'utilisateur peut creuser les patterns Métro vs Bus)
- **Carte avec context** : la viz Folium fait le lien entre les
  données structurelles (BDD) et la réalité géographique

### Négatives

- **Tracé pas optimal** : visible que c'est en pointillés. Risque
  qu'un utilisateur attende un vrai itinéraire (à expliquer dans
  l'expander méthodo).
- **Performances** : la heatmap fait une query 7 jours × 24 heures.
  Mitigé par `@st.cache_data(ttl=300)`.

## Suivi

- **PR 5 (potentielle)** : intégration API IDFM journey-planner pour
  remplacer le tracé en vol d'oiseau par un vrai itinéraire multimodal.
- **PR 6 (potentielle)** : modèle ML retard XGBoost intégré à la page
  Trafic comme prédiction des prochaines heures.

## Structure finale du dashboard

```
services/dashboard/src/dashboard/
├── app.py                      # Page Accueil
├── data.py                     # Toutes les requêtes BDD + helpers
├── theme.py                    # CSS et helpers UI
├── config.py                   # Settings
└── pages/
    ├── 1_Qualite_de_l_air.py   # PR 1
    ├── 2_Coach_IA.py           # PR 3 (livrée avant la 2 chronologiquement)
    ├── 3_Trafic.py             # PR 2 (cette ADR)
    └── 4_Score_sante.py        # PR 2 (cette ADR)
```
