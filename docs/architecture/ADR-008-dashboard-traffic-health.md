# ADR-008 — Pages Trafic et Score santé (dashboard)

## Statut
Accepté — mai 2026

## Contexte
Le dashboard initial couvrait l'Accueil et la Qualité de l'air. Pour
démontrer l'ensemble de la stack (trafic PRIM + scoring multicritère),
deux nouvelles pages étaient nécessaires.

## Décision
**Page Trafic** (`3_Trafic.py`) : KPIs 24h (passages, lignes actives,
retard moyen, % en retard), barchart top 10 lignes en retard, heatmap
heure × jour sur 7 jours, filtre par mode dans la sidebar.

**Page Score santé** (`4_Score_sante.py`) : deux dropdowns (10 zones IDF
prédéfinies correspondant aux points météo de l'ingestion), bouton
"Calculer", affichage grade A-E + 3 sous-scores, carte Folium avec tracé
du trajet et stations Airparif colorées par AQI.

Les 10 zones prédéfinies correspondent aux `DEFAULT_METEO_POINTS` de
l'ingestion — garantit qu'on a toujours des données météo récentes pour
ces points.

## Conséquences
- ✅ Dashboard 4 pages + coach IA couvre toute la stack du projet
- ✅ Réutilisation à 100 % du service `healthscore` existant
- ⚠️ Tracé en vol d'oiseau visible (pointillés) — documenté dans
  l'expander méthodologique de la page
