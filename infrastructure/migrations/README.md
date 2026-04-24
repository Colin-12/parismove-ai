# Migrations SQL

Scripts de création et évolution du schéma de base de données.
Les fichiers sont numérotés dans l'ordre d'application.

## Appliquer une migration

Via l'interface Supabase :

1. Va sur ton projet Supabase → **SQL Editor** (icône `</>` dans la sidebar)
2. Clique **"New query"**
3. Copie-colle le contenu du fichier `.sql`
4. Clique **"Run"**

Les migrations sont **idempotentes** (`CREATE TABLE IF NOT EXISTS`) donc tu peux les rejouer sans risque.

## Migrations existantes

| Fichier | Objet |
|---|---|
| `001_create_stop_visits.sql` | Table principale d'historisation des passages |

## Convention de nommage

`NNN_verbe_objet.sql` où `NNN` est un numéro séquentiel sur 3 chiffres.

Exemples :
- `002_add_pollution_measurements.sql`
- `003_add_index_on_journey.sql`
