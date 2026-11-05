"""Geliştirme koşularının (r1) Grafana yanıtlarını test kaydı olarak yazar. Holdout (r3) kaydedilmez.

Kullanım: uv run --env-file .env python tests/fixtures/record.py
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1] / "agent"))
import telemetry

RUNS = {
    "flood-r1": "attack-homepage-flood-01-r1",
    "deploy-r1": "ops-checkout-deploy-01-r1",
    "flash-r1": "campaign-flash-sale-01-r1",
}


def record(run_id: str) -> dict:
    run = json.loads(
        (HERE.parents[1] / "scenarios" / "runs" / f"{run_id}.json").read_text()
    )
    fetch, recorded = telemetry.grafana(os.environ["LAB_BIND_IP"]), {}

    def recording(path, params):
        recorded[telemetry.request_key(path, params)] = fetch(path, params)
        return recorded[telemetry.request_key(path, params)]

    start, end = (datetime.fromisoformat(run["window"][k]) for k in ("start", "end"))
    telemetry.collect(start, end, recording, HERE / "campaigns.json")
    return recorded


for name, run_id in RUNS.items():
    recorded = record(run_id)
    (HERE / f"{name}.json").write_text(json.dumps(recorded, ensure_ascii=False) + "\n")
    print(name, len(recorded), "yanıt")
