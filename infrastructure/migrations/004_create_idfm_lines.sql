-- Migration 004 — ParisMove AI
-- Crée la table de référence des lignes de transport en commun IDF.
--
-- Source : https://data.iledefrance-mobilites.fr/explore/dataset/referentiel-des-lignes/
-- Mise à jour : mensuelle (peu fréquent), via la commande
--               `python -m ingestion.cli refresh-references`.
--
-- Stratégie :
--   * UPSERT par line_id : on remplace les attributs si la ligne existe déjà.
--   * On ne supprime jamais une ligne (les anciennes données peuvent toujours
--     y faire référence dans stop_visits).

CREATE TABLE IF NOT EXISTS idfm_lines (
    line_id            TEXT PRIMARY KEY,

    -- Identifiants commerciaux
    short_name         TEXT,                              -- ex: "T2", "RER A", "258"
    long_name          TEXT,                              -- ex: "Tramway T2"
    transport_mode     TEXT,                              -- "metro", "rer", "bus", "tram"...
    transport_submode  TEXT,                              -- "regionalRail", "shuttleBus"...

    -- Réseau et opérateur
    network_name       TEXT,                              -- "RATP", "SNCF Transilien"...
    operator_name      TEXT,                              -- transporteur réel exploitant

    -- Esthétique (utile pour le dashboard)
    color_web_hex      TEXT,                              -- "#7B388C"
    text_color_hex     TEXT,                              -- "#FFFFFF"

    -- Statut
    status             TEXT,                              -- "active", "discontinued"...
    accessibility      TEXT,                              -- info accessibilité

    -- Traçabilité
    last_refreshed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_idfm_lines_short_name ON idfm_lines (short_name);
CREATE INDEX IF NOT EXISTS idx_idfm_lines_mode ON idfm_lines (transport_mode);

COMMENT ON TABLE idfm_lines IS
    'Référentiel des lignes IDF (table de dimension). Mise à jour mensuelle.';
COMMENT ON COLUMN idfm_lines.line_id IS
    'Identifiant SIRI (ex: STIF:Line::C01390:). Match stop_visits.line_id.';
COMMENT ON COLUMN idfm_lines.color_web_hex IS
    'Couleur officielle (sans #) pour l''affichage dans les dashboards.';
