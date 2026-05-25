# ADR-003 — Enrichissement par jointure (star schema)

## Statut
Accepté — avril 2026

## Contexte
L'API PRIM IDFM renvoie des identifiants techniques de lignes
(`STIF:Line::C01390:`) sans noms commerciaux ni métadonnées. Le référentiel
officiel IDFM (~2 100 lignes) contient ces informations. Il faut décider
comment associer chaque passage à sa ligne enrichie.

## Décision
Adopter un **modèle dimensionnel** (star schema) :

- `stop_visits` : table de faits, données brutes telles qu'ingérées
- `idfm_lines` : table de dimensions, attributs des lignes (nom, mode,
  couleur, opérateur)
- L'enrichissement se fait **par JOIN au moment de la lecture**, jamais
  à l'ingestion

## Conséquences
- ✅ Donnée brute préservée à 100 % — mises à jour du référentiel sans
  risque pour l'historique
- ✅ Pattern industriel reconnu (Kimball), facile à expliquer en soutenance
- ✅ Découplage ingestion (rapide) / enrichissement (à la demande)
- ⚠️ Les requêtes de lecture nécessitent un JOIN — négligeable à notre
  échelle (table de dimension indexée, quelques milliers de lignes)
