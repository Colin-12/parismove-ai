# ADR-001 — Choix du fournisseur de stockage

## Statut
Accepté — avril 2026

## Contexte
Le projet nécessite une base PostgreSQL accessible depuis plusieurs services
(ingestion, dashboard, coach) et depuis GitHub Actions. Budget : 0 €.

## Décision
**Supabase** (free tier) est retenu comme fournisseur de base de données.

Critères déterminants : PostGIS natif pour les calculs géospatiaux, free
tier confortable (500 Mo, 2 Go bande passante), pas de mise en pause si
le cron d'ingestion toutes les 30 min maintient l'activité.

## Conséquences
- ✅ Mise en place en moins d'une heure, pas de gestion de serveur
- ✅ Dashboard Supabase pour explorer les données directement
- ⚠️ Limite 500 Mo : impose une politique de rétention (90 jours)
- ⚠️ Verrouillage modéré sur PostgREST/RLS, migration vers Postgres vanilla
  possible si besoin
