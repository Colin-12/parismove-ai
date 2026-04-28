-- Migration 002 — ParisMove AI
-- Crée la table d'historisation des mesures de qualité de l'air (AQICN).
--
-- Stratégie :
--   * Une ligne = une mesure d'une station à un instant T (selon AQICN).
--   * Unicité : (station_id, measured_at) — AQICN ne renvoie qu'une mesure
--     par horodatage de toute façon.
--   * Index sur (recorded_at) et (station_id, measured_at) pour les
--     requêtes analytiques et les jointures avec stop_visits.

CREATE TABLE IF NOT EXISTS air_measurements (
    id                BIGSERIAL PRIMARY KEY,

    -- Identifiants
    station_id        TEXT NOT NULL,
    station_name      TEXT NOT NULL,

    -- Géolocalisation (utile pour les jointures spatiales avec les arrêts)
    latitude          DOUBLE PRECISION NOT NULL,
    longitude         DOUBLE PRECISION NOT NULL,

    -- Indice agrégé
    aqi               INTEGER,

    -- Polluants (µg/m³)
    pm25              REAL,
    pm10              REAL,
    no2               REAL,
    o3                REAL,
    so2               REAL,
    co                REAL,

    -- Conditions ambiantes
    temperature_c     REAL,
    humidity_pct      REAL,
    pressure_hpa      REAL,
    wind_speed_ms     REAL,

    -- Traçabilité
    measured_at       TIMESTAMPTZ NOT NULL,
    recorded_at       TIMESTAMPTZ NOT NULL,
    attribution       TEXT,
    source            TEXT NOT NULL DEFAULT 'aqicn',
    inserted_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_air_measurements_unique
    ON air_measurements (station_id, measured_at);

CREATE INDEX IF NOT EXISTS idx_air_measurements_recorded_at
    ON air_measurements (recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_air_measurements_station_recent
    ON air_measurements (station_id, measured_at DESC);

-- Index pour les requêtes "qualité de l'air actuelle dans un rayon"
CREATE INDEX IF NOT EXISTS idx_air_measurements_geo
    ON air_measurements (latitude, longitude);

COMMENT ON TABLE air_measurements IS
    'Mesures de qualité de l''air collectées via l''API AQICN.';
COMMENT ON COLUMN air_measurements.aqi IS
    'Air Quality Index US EPA. 0-50 bon, 51-100 modéré, 101+ mauvais.';
COMMENT ON COLUMN air_measurements.measured_at IS
    'Horodatage déclaré par AQICN (peut différer de recorded_at).';
