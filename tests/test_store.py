"""Evidence store: her kanıt bir evidence_id ile SQLite'ta durur."""

import store

EVIDENCE = [
    {
        "title": "traffic",
        "source": "loki",
        "query": "sum(count_over_time(...))",
        "status": "ok",
        "summary": "Son 2 dk: 3648 istek/dk",
        "data": {"recent_per_min": 3648},
    },
    {
        "title": "deploys",
        "source": "grafana",
        "query": "/api/annotations?tags=deploy",
        "status": "unreachable",
        "summary": "Grafana annotation API erişilemedi",
        "data": {"error": "timeout"},
    },
]


def test_saved_evidence_gets_ids_and_reads_back(tmp_path):
    db = store.connect(tmp_path / "evidence.db")

    saved = store.save_evidence(db, "inc-0000aaaa", EVIDENCE)

    assert [e["evidence_id"] for e in saved] == ["E01", "E02"]
    assert store.load_evidence(db, "inc-0000aaaa") == saved


def test_reinvestigation_replaces_old_evidence(tmp_path):
    db = store.connect(tmp_path / "evidence.db")
    store.save_evidence(db, "inc-0000aaaa", EVIDENCE)
    store.save_evidence(db, "inc-0000bbbb", EVIDENCE[:1])

    store.save_evidence(db, "inc-0000aaaa", EVIDENCE[:1])

    assert len(store.load_evidence(db, "inc-0000aaaa")) == 1
    assert len(store.load_evidence(db, "inc-0000bbbb")) == 1
