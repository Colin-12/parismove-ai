-- Migration 003 — ParisMove AI
-- Crée la table d'historisation des observations météo + qualité air modélisée.
--
-- Source : Open-Meteo (forecast + air-quality endpoints).
-- Stratégie :
--   * Une ligne = une observation à un point GPS, à un instant T.
--   * Unicité : (point_id, observed_at).
--   * Index sur (recorded_at) et (point_id, observed_at) pour l'analytique.

CREATE TABLE IF NOT EXISTS weather_observations (
    id                       BIGSERIAL PRIMARY KEY,

    -- Identifiants logique + spatial
    point_id                 TEXT NOT NULL,
    point_name               TEXT NOT NULL,
    latitude                 DOUBLE PRECISION NOT NULL,
    longitude                DOUBLE PRECISION NOT NULL,
    elevation_m              REAL,

    -- Météo
    temperature_c            REAL,
    apparent_temperature_c   REAL,
    humidity_pct             REAL,
    pressure_hpa             REAL,
    surface_pressure_hpa     REAL,
    cloud_cover_pct          REAL,
    visibility_m             REAL,

    -- Précipitations
    precipitation_mm         REAL,
    rain_mm                  REAL,
    showers_mm               REAL,
    snowfall_cm              REAL,

    -- Vent
    wind_speed_ms            REAL,
    wind_gusts_ms            REAL,
    wind_direction_deg       REAL,

    -- UV / soleil
    uv_index                 REAL,
    is_day                   BOOLEAN,

    -- Code météo synthétique (WMO 4677)
    weather_code             SMALLINT,

    -- Qualité de l'air modélisée (CAMS)
    aqi_european             REAL,
    pm25                     REAL,
    pm10                     REAL,
    no2                      REAL,
    o3                       REAL,
    so2                      REAL,
    co                       REAL,

    -- Pollens
    alder_pollen             REAL,
    birch_pollen             REAL,
    grass_pollen             REAL,
    ragweed_pollen           REAL,

    -- Traçabilité
    observed_at              TIMESTAMPTZ NOT NULL,
    recorded_at              TIMESTAMPTZ NOT NULL,
    source                   TEXT NOT NULL DEFAULT 'open-meteo',
    inserted_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_weather_observations_unique
    ON weather_observations (point_id, observed_at);

CREATE INDEX IF NOT EXISTS idx_weather_observations_recorded_at
    ON weather_observations (recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_weather_observations_point_recent
    ON weather_observations (point_id, observed_at DESC);

CREATE INDEX IF NOT EXISTS idx_weather_observations_geo
    ON weather_observations (latitude, longitude);

-- Index partiel pour les analyses pluie / temps couvert
CREATE INDEX IF NOT EXISTS idx_weather_observations_rainy
    ON weather_observations (point_id, observed_at DESC)
    WHERE precipitation_mm > 0;

COMMENT ON TABLE weather_observations IS
    'Observations météo et qualité air modélisée via Open-Meteo (CAMS).';
COMMENT ON COLUMN weather_observations.weather_code IS
    'Code WMO 4677 : 0=clair, 1-3=variable, 51-55=bruine, 61-65=pluie...';
COMMENT ON COLUMN weather_observations.aqi_european IS
    'EAQI 1-5 (1=très bon, 5=très mauvais), modélisé par CAMS.';
