# ADR 004 — Calcul du score santé de trajet

**Statut :** Accepté
**Date :** 2026-04
**Auteur :** Colin

## Contexte

Le projet ParisMove AI doit fournir une **fonctionnalité différenciante** au-delà
de la simple prédiction de retard : aider l'utilisateur à choisir le trajet le
moins polluant et le plus confortable, pas seulement le plus rapide.

Plusieurs approches étaient possibles : score numérique brut, classification
binaire (bon/mauvais), comparaison relative...

## Décision

Implémenter un score multicritère **A-E façon Nutri-Score** qui combine :
- **Pollution** (60 %) — qualité de l'air mesurée et modélisée
- **Météo** (30 %) — confort thermique, précipitations, vent, UV
- **Trafic** (10 %) — historique de retards comme proxy de congestion

Le score est calculé sur des **trajets décrits par une liste de coordonnées GPS**
(pas par identifiants d'arrêts), pour rester générique aux modes (transport en
commun, marche, vélo).

## Justifications

### Format A-E plutôt que 0-100

- **UX éprouvée** : Nutri-Score, Yuka, Ecovadis utilisent ce format
- **Lisibilité dashboard** : couleurs vert/jaune/rouge intuitives
- **Décision rapide** : un utilisateur n'a pas besoin de comprendre pourquoi
  le score est 73 vs 76, il veut savoir "est-ce que c'est bien ou pas"

Le score 0-100 reste exposé en sortie pour le débugging et les analyses
fines, mais l'affichage principal utilise la lettre.

### Pondération 60/30/10

Choix défendable scientifiquement :
- La qualité de l'air a l'**impact santé le plus prouvé** (études OMS, ANSES) :
  exposition chronique au PM2.5 réduit l'espérance de vie en moyenne de 8-10 mois
  en Île-de-France.
- La météo joue surtout sur le confort, pas sur la santé long terme.
- Le trafic est un proxy indirect de la pollution (corrélé) → poids faible
  pour ne pas double-compter.

Les poids sont passables en paramètre, donc ajustables sans changer le code.

### Trajet = liste de coordonnées GPS (pas d'arrêts)

- **Générique** : marche pour le métro, le RER, le vélo, la marche
- **Découplé du référentiel IDFM** : si IDFM change ses IDs, on est résilient
- **Testable simplement** sans dépendre de la BDD des arrêts

L'inconvénient : on ne sait pas exactement par où passe le trajet entre 2
waypoints. On considère que les waypoints sont représentatifs (ex: pour un
RER, on prend les gares principales traversées).

### Pas de PostGIS

Supabase free tier supporte PostGIS, mais on n'en a pas besoin :
- Seulement 4 stations AQICN et 10 points météo à comparer
- Calcul haversine en Python : <1 ms pour les volumes en jeu
- Évite la dépendance et simplifie les tests

Si on monte à 100+ stations un jour, on pourra activer PostGIS et utiliser
`ST_DWithin` pour les requêtes spatiales côté SQL.

## Conséquences

### Positives
- API simple : `score_journey(waypoints)` → `JourneyScore` avec grade A-E
- Module testable indépendamment (chaque sub-score a ses tests)
- Extensible : on peut ajouter d'autres dimensions (bruit, sécurité...) sans
  casser l'existant

### Négatives
- **Précision spatiale limitée** par le nombre de capteurs (4 stations AQICN)
  → on émet un warning quand la station la plus proche est à >5km
- **Sub-score trafic peu précis** tant que `stop_visits` n'a pas les coordonnées
  des arrêts (limitation documentée, à corriger plus tard via enrichissement
  avec les positions des StopArea IDFM)
- Pondération arbitraire (60/30/10) discutable scientifiquement —
  on offre la possibilité de la modifier en paramètre

## Implémentation

Service séparé `services/healthscore` avec :
- `exposure.py` : calcul haversine, recherche du plus proche
- `pollution.py` : sub-score basé sur seuils OMS/EPA
- `weather.py`   : sub-score multifactoriel (T°, pluie, vent, UV)
- `traffic.py`   : sub-score basé sur historique retards
- `scoring.py`   : agrégation pondérée + conversion grade A-E
- `compare.py`   : orchestrateur principal
- `data_access.py` : requêtes BDD pour les snapshots actuels
- `cli.py`       : interface ligne de commande
