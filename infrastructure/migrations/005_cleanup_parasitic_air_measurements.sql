-- Migration 005 — Nettoyage des données AQICN parasites
--
-- Suite à un bug d'identifiants AQICN dans `feat/aqicn-client`, certaines
-- stations à l'étranger ont été ingérées par erreur (Londres, Ziyang...).
-- Cette migration les supprime pour ne pas polluer les analyses futures.
--
-- Critère de suppression :
--   * Latitude hors de [48.0, 50.0] OU longitude hors de [1.5, 3.5]
--     (bounding box étendue de l'Île-de-France)
--
-- À exécuter une seule fois après le merge de fix/aqicn-stations.

BEGIN;

-- 1. Compte des lignes à supprimer (sanity check)
DO $$
DECLARE
    bad_count INT;
BEGIN
    SELECT COUNT(*) INTO bad_count
    FROM air_measurements
    WHERE latitude < 48.0 OR latitude > 50.0
       OR longitude < 1.5 OR longitude > 3.5;

    RAISE NOTICE 'Lignes parasites détectées : %', bad_count;
END $$;

-- 2. Liste les stations à supprimer (pour traçabilité)
SELECT
    station_id, station_name, latitude, longitude,
    COUNT(*) AS measurements_count,
    MIN(measured_at) AS first_seen,
    MAX(measured_at) AS last_seen
FROM air_measurements
WHERE latitude < 48.0 OR latitude > 50.0
   OR longitude < 1.5 OR longitude > 3.5
GROUP BY station_id, station_name, latitude, longitude
ORDER BY measurements_count DESC;

-- 3. Suppression effective des mesures hors IDF
DELETE FROM air_measurements
WHERE latitude < 48.0 OR latitude > 50.0
   OR longitude < 1.5 OR longitude > 3.5;

-- 4. Vérification finale : il ne doit rester que des stations IDF
SELECT
    'Vérification post-cleanup' AS status,
    COUNT(*) AS lignes_restantes,
    MIN(latitude) AS lat_min,
    MAX(latitude) AS lat_max,
    MIN(longitude) AS lon_min,
    MAX(longitude) AS lon_max
FROM air_measurements;

COMMIT;

-- Note : si tu veux d'abord voir ce qui sera supprimé sans faire la suppression,
-- remplace `BEGIN; ... COMMIT;` par `BEGIN; ... ROLLBACK;` pour faire un dry-run.
