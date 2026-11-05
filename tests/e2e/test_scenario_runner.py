"""Koşucu kısa bir deneme koşusunu baştan sona yürütür. Çalışan VPS lab'ı ve dizüstünde Docker gerekir (~5 dk)."""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest
from grafana import LAB_IP, eventually, get_json

import runner

pytestmark = pytest.mark.skipif(
    not (LAB_IP and os.environ.get("GRAFANA_ADMIN_PASSWORD")),
    reason="LAB_BIND_IP ve GRAFANA_ADMIN_PASSWORD gerekli: uv run --env-file .env pytest tests/e2e",
)

ROOT = Path(__file__).parents[2]


def nanoseconds(iso):
    return int(datetime.fromisoformat(iso).timestamp() * 10**9)


def test_trial_deploy_run_breaks_checkout_then_rolls_back(tmp_path):
    # 180 sn olay ~18 ödeme denemesi demek; çok ürünlü sepet (~%30) en az bir kez hataya düşer.
    subprocess.run(
        [sys.executable, "scenarios/runner.py", "ops-checkout-deploy-01"]
        + ["--trial", "20,180,10", "--runs-dir", str(tmp_path)],
        cwd=ROOT,
        check=True,
    )

    record = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert record["trial"] and not record["aborted"] and record["k6_exit"] == 0
    assert record["deploy"]["version"] == "v1.1.0"
    env = runner.vps(
        "inspect",
        "watcher-lab-checkout-1",
        "--format",
        "{{json .Config.Env}}",
        capture_output=True,
        text=True,
    )
    assert runner.release(json.loads(env.stdout)) == "v1.0.0"

    def checkout_errors():
        streams = get_json(
            "loki/loki/api/v1/query_range",
            query='{service_name="checkout"} |= "unhandled error"',
            start=nanoseconds(record["deploy"]["at"]),
            end=nanoseconds(record["deploy"]["rollback_at"]),
        )["data"]["result"]
        return [line for s in streams for _, line in s["values"]]

    assert eventually(checkout_errors)
