"""Uçtan uca inceleme: kaydedilmiş lab yanıtları + taklit LLM → evidence store, JSON ve Markdown rapor."""

import json
import re
from datetime import datetime

from test_telemetry import FIXTURES, FLOOD_WINDOW, replay

import investigate
import store

LLM_ANSWER = {
    "label": "attack",
    "confidence": "high",
    "decision": {
        "text": "client-1'den ana sayfaya L7 flood",
        "evidence_ids": ["E03", "E04"],
    },
    "impact": [{"text": "Sipariş/dk baseline'a yakın", "evidence_ids": ["E08"]}],
    "timeline": [{"text": "Trafik 10 kat arttı", "evidence_ids": ["E01"]}],
    "hypotheses": [
        {
            "label": "legit_campaign",
            "verdict": "rejected",
            "text": "Takvimde kampanya yok",
            "evidence_ids": ["E13"],
        },
        {
            "label": "ops_failure",
            "verdict": "rejected",
            "text": "Uydurma kanıt",
            "evidence_ids": ["E77"],
        },
    ],
    "could_mislead": [],
    "missing_evidence": [],
    "next_steps": ["client-1 için engelleme kararını değerlendir"],
}


def fake_llm(messages):
    return {
        "text": json.dumps(LLM_ANSWER, ensure_ascii=False),
        "model": "fake",
        "input_tokens": 5000,
        "output_tokens": 800,
        "cost_usd": 0.01,
        "llm_seconds": 0.1,
    }


def run(tmp_path):
    start, end = (datetime.fromisoformat(t) for t in FLOOD_WINDOW)
    db = store.connect(tmp_path / "evidence.db")
    report = investigate.investigate(
        "inc-6af22b72",
        start,
        end,
        replay("flood-r1"),
        fake_llm,
        FIXTURES / "campaigns.json",
        db,
        tmp_path,
    )
    return report, db


def test_report_files_and_evidence_are_written(tmp_path):
    report, db = run(tmp_path)

    assert report["label"] == "attack"
    saved = json.loads((tmp_path / "inc-6af22b72.json").read_text())
    assert saved["label"] == "attack" and saved["metadata"]["queries"] > 30
    assert saved["metadata"]["input_tokens"] == 5000
    assert len(store.load_evidence(db, "inc-6af22b72")) == len(saved["evidence"])


def test_every_citation_in_markdown_exists_in_store(tmp_path):
    _, db = run(tmp_path)

    markdown, invalid = (
        (tmp_path / "inc-6af22b72.md").read_text().split("## Geçersiz atıflar")
    )
    stored = {e["evidence_id"] for e in store.load_evidence(db, "inc-6af22b72")}
    cited = set(re.findall(r"\bE\d{2}\b", markdown))
    assert cited and cited <= stored
    assert "Uydurma kanıt" not in markdown and "Uydurma kanıt" in invalid
    assert (
        "45.142.120.18" in markdown
    )  # takma ad tablosu nöbetçi için gerçek IP'yi gösterir
