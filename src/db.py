import sqlite3
from pathlib import Path

_DDL = """
CREATE TABLE IF NOT EXISTS bandi (
    id                      TEXT PRIMARY KEY,
    fonte                   TEXT NOT NULL,
    url                     TEXT NOT NULL,
    titolo                  TEXT,
    ente                    TEXT,
    categoria               TEXT,
    area_geografica         TEXT,
    posti                   INTEGER,
    scadenza                TEXT,
    titolo_studio_richiesto TEXT,
    requisiti_formali       TEXT,
    materie_esame           TEXT,
    tassa_concorso          REAL,
    link_candidatura        TEXT,
    documenti_richiesti     TEXT,
    testo_raw               TEXT NOT NULL DEFAULT '',
    parse_method            TEXT NOT NULL,
    extraction_confidence   REAL NOT NULL DEFAULT 0.0,
    status                  TEXT NOT NULL DEFAULT 'ok',
    created_at              TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bandi_scadenza     ON bandi(scadenza);
CREATE INDEX IF NOT EXISTS idx_bandi_status       ON bandi(status);

CREATE TABLE IF NOT EXISTS collector_runs (
    id           TEXT PRIMARY KEY,
    fonte        TEXT NOT NULL,
    started_at   TEXT NOT NULL,
    completed_at TEXT,
    n_trovati    INTEGER NOT NULL DEFAULT 0,
    n_nuovi      INTEGER NOT NULL DEFAULT 0,
    n_duplicati  INTEGER NOT NULL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'running',
    errori       TEXT
);

CREATE TABLE IF NOT EXISTS match_results (
    id           TEXT PRIMARY KEY,
    bando_id     TEXT NOT NULL REFERENCES bandi(id),
    profilo_nome TEXT NOT NULL,
    compatibilita TEXT NOT NULL,
    checklist    TEXT NOT NULL,
    da_verificare TEXT NOT NULL,
    spiegazione  TEXT NOT NULL DEFAULT '',
    disclaimer   TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_match_results_compatibilita ON match_results(compatibilita);
CREATE INDEX IF NOT EXISTS idx_match_results_bando_id      ON match_results(bando_id);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id           TEXT PRIMARY KEY,
    started_at   TEXT NOT NULL,
    completed_at TEXT,
    current_step TEXT,
    status       TEXT NOT NULL DEFAULT 'running',
    steps_json   TEXT NOT NULL DEFAULT '[]',
    error_step   TEXT,
    error_msg    TEXT
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started_at ON pipeline_runs(started_at);

CREATE TABLE IF NOT EXISTS user_actions (
    id         TEXT PRIMARY KEY,
    bando_id   TEXT NOT NULL REFERENCES bandi(id),
    action     TEXT NOT NULL,
    nota       TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_user_actions_bando_id ON user_actions(bando_id);
CREATE INDEX IF NOT EXISTS idx_user_actions_action   ON user_actions(action);
"""


def init_db(db_path: Path) -> None:
    """Crea tabelle e indici se non esistono. Idempotente."""
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(_DDL)
    finally:
        conn.close()
