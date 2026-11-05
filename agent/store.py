"""Evidence store: her kanıt bir evidence_id ile SQLite'ta durur. evidence_id olay içinde tekildir (E01, E02...)."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS evidence (
    incident_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    query TEXT NOT NULL,
    status TEXT NOT NULL,
    summary TEXT NOT NULL,
    data TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    PRIMARY KEY (incident_id, evidence_id)
)
"""
FIELDS = (
    "evidence_id",
    "title",
    "source",
    "query",
    "status",
    "summary",
    "data",
    "collected_at",
)


def connect(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.execute(SCHEMA)
    return db


def save_evidence(
    db: sqlite3.Connection, incident_id: str, evidence: list[dict]
) -> list[dict]:
    now = datetime.now(UTC).isoformat()
    saved = [
        {"evidence_id": f"E{i:02d}", **e, "collected_at": now}
        for i, e in enumerate(evidence, 1)
    ]
    with db:
        db.execute("DELETE FROM evidence WHERE incident_id = ?", (incident_id,))
        db.executemany(
            f"INSERT INTO evidence (incident_id, {', '.join(FIELDS)}) VALUES (?{', ?' * len(FIELDS)})",
            [
                (
                    incident_id,
                    *(
                        json.dumps(e[f], ensure_ascii=False) if f == "data" else e[f]
                        for f in FIELDS
                    ),
                )
                for e in saved
            ],
        )
    return saved


def load_evidence(db: sqlite3.Connection, incident_id: str) -> list[dict]:
    rows = db.execute(
        f"SELECT {', '.join(FIELDS)} FROM evidence WHERE incident_id = ? ORDER BY evidence_id",
        (incident_id,),
    )
    return [
        {f: json.loads(v) if f == "data" else v for f, v in zip(FIELDS, row)}
        for row in rows
    ]
