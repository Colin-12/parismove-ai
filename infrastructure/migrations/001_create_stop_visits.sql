-- Migration 001 — ParisMove AI
-- Crée la table principale d'historisation des passages captés par l'ingestion.
--
-- Stratégie :
--   * Chaque ligne = un snapshot d'un passage prévu à un arrêt, capté à un instant T.
--   * On historise tout : même passage peut apparaître plusieurs fois avec des horaires
--     prévus qui évoluent (retards qui se confirment ou se résorbent).
--   * Contrainte d'unicité : (stop_id, vehicle_journey_id, recorded_at) pour éviter
--     les doublons si le cron insère deux fois le même batch.
--   * Index sur (recorded_at) et (line_id, recorded_at) pour les requêtes analytiques.

CREATE TABLE IF NOT EXISTS stop_visits (
    -- Identité
    id                    BIGSERIAL PRIMARY KEY,

    -- Identifiants métier
    stop_id               TEXT NOT NULL,
    line_id               TEXT NOT NULL,
    vehicle_journey_id    TEXT,

    -- Métadonnées ligne
    line_name             TEXT,
    operator              TEXT,
    direction             TEXT,
    transport_mode        TEXT NOT NULL DEFAULT 'unknown',

    -- Horaires (paire arrivée et paire départ car PRIM peut ne donner que l'un)
    aimed_arrival         TIMESTAMPTZ,
    expected_arrival      TIMESTAMPTZ,
    aimed_departure       TIMESTAMPTZ,
    expected_departure    TIMESTAMPTZ,

    -- Statut
    arrival_status        TEXT,
    departure_status      TEXT,

    -- Retard calculé (en secondes, positif = retard, négatif = avance)
    -- Stocké pour éviter le recalcul à chaque requête analytique.
    delay_seconds         INTEGER,

    -- Traçabilité
    recorded_at           TIMESTAMPTZ NOT NULL,
    source                TEXT NOT NULL DEFAULT 'prim',
    inserted_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Unicité : évite les doublons en cas de rejeu d'un batch.
-- On n'inclut pas vehicle_journey_id dans la PK car il peut être NULL (PostgreSQL
-- traite NULL != NULL donc l'unicité ne marche pas si on l'inclut directement).
-- COALESCE force une valeur de substitution pour les NULL, rendant l'index unique
-- fonctionnel même pour les visites sans identifiant de course.
CREATE UNIQUE INDEX IF NOT EXISTS idx_stop_visits_unique
    ON stop_visits (
        stop_id,
        line_id,
        COALESCE(vehicle_journey_id, ''),
        recorded_at
    );

-- Index pour les requêtes analytiques fréquentes
CREATE INDEX IF NOT EXISTS idx_stop_visits_recorded_at
    ON stop_visits (recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_stop_visits_line_recent
    ON stop_visits (line_id, recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_stop_visits_stop_recent
    ON stop_visits (stop_id, recorded_at DESC);

-- Index partiel pour les analyses de retard (on ne garde que les lignes exploitables)
CREATE INDEX IF NOT EXISTS idx_stop_visits_delays
    ON stop_visits (line_id, recorded_at DESC)
    WHERE delay_seconds IS NOT NULL;

COMMENT ON TABLE stop_visits IS
    'Historique des passages aux arrêts IDFM, capté via l''API PRIM.';
COMMENT ON COLUMN stop_visits.recorded_at IS
    'Instant auquel la donnée a été captée par l''ingestion.';
COMMENT ON COLUMN stop_visits.delay_seconds IS
    'Retard calculé : positif = en retard, négatif = en avance, NULL = non comparable.';
