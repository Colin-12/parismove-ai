# ADR 001 — Choix du fournisseur de stockage

**Statut :** Accepté
**Date :** 2026-04
**Auteur :** Colin

## Contexte

Le projet nécessite une base de données relationnelle avec support géospatial (calculs d'itinéraires, distances entre arrêts) et une API REST accessible depuis le dashboard et l'API FastAPI. Le projet dispose d'un budget de 0 €.

## Options étudiées

| Option | Coût | Géospatial | API REST auto | Pause si inactif |
|---|---|---|---|---|
| **Supabase** (free tier) | 0 € | PostGIS inclus | Oui (PostgREST) | Après 7 jours, réveil auto |
| Neon (free tier) | 0 € | PostGIS inclus | Non | Après 5 minutes, réveil auto |
| Railway Postgres | ~5 $/mois après essai | PostGIS dispo | Non | Non |
| SQLite local + déploiement statique | 0 € | Extension SpatiaLite | Non | N/A |
| Google Cloud SQL | Free tier limité | PostGIS dispo | Non | Non |

## Décision

**Supabase** est retenu pour les raisons suivantes :

1. **PostGIS natif** : indispensable pour les calculs géospatiaux (distance entre deux arrêts, exposition cumulée à la pollution le long d'un trajet).
2. **API REST auto-générée** (PostgREST) : permet au dashboard de consommer directement les données sans écrire de backend supplémentaire, tout en laissant la possibilité d'ajouter une API FastAPI pour la logique métier.
3. **Authentification intégrée** : utile pour une éventuelle évolution multi-utilisateurs.
4. **Free tier confortable** : 500 Mo de stockage, 2 Go de bande passante, 50 000 utilisateurs authentifiés.

## Conséquences

### Positives
- Mise en place en moins d'une heure.
- Pas de gestion de serveur.
- Dashboard Supabase pour explorer la donnée.

### Négatives
- **Pause après 7 jours d'inactivité** : impact sur les démos. Mitigation : le cron d'ingestion toutes les 15 minutes maintient la base active.
- **Verrouillage fournisseur modéré** : on utilise PostgREST et les règles RLS (row-level security) spécifiques. Mitigation : la couche ingestion parle SQL standard, migration vers un Postgres vanilla possible si besoin.
- **Limite de 500 Mo** : impose une politique de rétention. Décision : garder 90 jours de données brutes, agréger au-delà.

## Alternatives rejetées

- **Neon** écarté car la mise en pause après 5 minutes perturbe l'expérience dashboard et ajoute de la latence au premier appel.
- **SQLite** écarté car incompatible avec un déploiement cloud multi-service.
