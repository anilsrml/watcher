"""Agent gerçek lab'a karşı: her kaynak sorgulanır; anahtar varsa gerçek LLM'le rapor üretilir. Yalnız geliştirme koşusu (r1)."""

import json
import os
from datetime import datetime
from pathlib import Path

import pytest
from grafana import LAB_IP

import classify
import investigate
import telemetry

pytestmark = pytest.mark.skipif(
    not LAB_IP, reason="LAB_BIND_IP gerekli: uv run --env-file .env pytest tests/e2e"
)

ROOT = Path(__file__).parents[2]


def dev_run(run_id):
    run = json.loads((ROOT / "scenarios" / "runs" / f"{run_id}.json").read_text())
    assert not run["holdout"]
    return run["incident_id"], *(
        datetime.fromisoformat(run["window"][k]) for k in ("start", "end")
    )


def test_every_source_answers_for_a_dev_window():
    _, start, end = dev_run("ops-checkout-deploy-01-r1")

    evidence, _ = telemetry.collect(
        start, end, telemetry.grafana(LAB_IP), ROOT / "scenarios" / "campaigns.json"
    )

    assert [e["title"] for e in evidence if e["status"] != "ok"] == []


@pytest.mark.skipif(
    not (os.environ.get("LLM_MODEL") and os.environ.get("LLM_API_KEY")),
    reason="LLM_MODEL ve LLM_API_KEY gerekli",
)
def test_real_llm_writes_cited_report(tmp_path):
    incident_id, start, end = dev_run("ops-checkout-deploy-01-r1")

    result = investigate.run(incident_id, start, end, reports_dir=tmp_path)

    assert result["label"] in classify.LABELS
    assert result["decision"] and result["citation_validity"] > 0.5
    assert (tmp_path / f"{incident_id}.md").exists()
