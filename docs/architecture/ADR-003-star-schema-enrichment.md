# ADR 003 — Enrichissement des données via jointure (star schema)

**Statut :** Accepté
**Date :** 2026-04
**Auteur :** Colin

## Contexte

Les données ingérées via l'API PRIM IDFM contiennent des identifiants
techniques de lignes (`STIF:Line::C01390:`) mais pas toujours leurs noms
commerciaux ("T2"). Pour rendre la donnée exploitable dans le dashboard et
le coach RAG, il faut associer chaque `line_id` à son nom court, son mode
de transport, sa couleur, etc.

Il existe un référentiel officiel publié par IDFM
(`data.iledefrance-mobilites.fr/explore/dataset/referentiel-des-lignes/`)
qui contient ~2000 lignes de transport en commun en IDF.

## Décision

Adopter un **modèle dimensionnel** (star schema) :

- **Table de faits** : `stop_visits` (et plus tard `air_measurements`,
  `weather_observations`). Garde la donnée brute, intacte, telle qu'ingérée
  par les pipelines.
- **Table de dimensions** : `idfm_lines`. Contient les attributs des lignes
  (nom commercial, couleur, opérateur, etc.).
- L'**enrichissement se fait par JOIN au moment de la lecture**, pas à
  l'ingestion.

## Alternatives rejetées

### Alternative 1 — Enrichir à l'ingestion

À chaque insertion dans `stop_visits`, faire un lookup et remplir
`line_name = "T2"` directement.

**Rejeté** car :
- Si IDFM change le nom d'une ligne, l'historique reste figé sur l'ancien nom
- Le pipeline d'ingestion devient plus lent (1 requête de plus par batch)
- La donnée brute est perdue : on ne peut plus distinguer "info absente côté
  PRIM" de "info enrichie côté nous"

### Alternative 2 — Pas d'enrichissement, fallback sur le code court

Afficher "C01390" partout, puisque c'est ce que renvoie l'API.

**Rejeté** car :
- Illisible pour l'utilisateur final (qui sait ce qu'est un C01390 ?)
- Empêche les analyses agrégées par mode de transport, opérateur, etc.

## Conséquences

### Positives

- Donnée brute préservée à 100 %
- Mises à jour du référentiel sans risque pour l'historique
- Découplage entre ingestion (rapide) et enrichissement (au besoin)
- Pattern industriel reconnu (Kimball, star schema), facile à expliquer
  en soutenance

### Négatives

- Les requêtes de lecture nécessitent un JOIN (négligeable à notre échelle :
  table de dimension de quelques milliers de lignes, indexée sur la clé
  primaire `line_id`)
- Le module `LineLookup` charge tout le référentiel en RAM au démarrage
  des services consommateurs (~200 Ko, négligeable)

## Implémentation

- Migration SQL `004_create_idfm_lines.sql` crée la table de dimension
- Module `ingestion.reference.idfm_loader` télécharge et upsert le
  référentiel via la commande CLI `refresh-references`
- Module `shared.db.lookups.LineLookup` expose un cache mémoire utilisable
  par les autres services (dashboard, coach)
- Pas de modification de la table `stop_visits` : l'enrichissement se fait
  via JOIN dans les requêtes analytiques

## Exemple de requête d'enrichissement

```sql
SELECT
    sv.recorded_at,
    sv.stop_id,
    sv.delay_seconds,
    line.short_name AS line_name,
    line.transport_mode,
    line.color_web_hex
FROM stop_visits sv
LEFT JOIN idfm_lines line ON sv.line_id = line.line_id
WHERE sv.recorded_at >= NOW() - INTERVAL '24 hours'
ORDER BY sv.recorded_at DESC;
```

Le LEFT JOIN garantit que les lignes inconnues du référentiel apparaissent
quand même (avec `line_name = NULL`), ce qui évite de perdre de la donnée.
