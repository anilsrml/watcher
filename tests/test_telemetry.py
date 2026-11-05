"""Kanıt toplama: lab'dan kaydedilmiş Grafana yanıtlarıyla (yalnız geliştirme koşuları, r1).

Kayıtları yenilemek: uv run --env-file .env python tests/fixtures/record.py
"""

import json
import urllib.error
from datetime import datetime
from pathlib import Path

import telemetry

FIXTURES = Path(__file__).parent / "fixtures"
FLOOD_WINDOW = ("2026-11-05T11:03:28.451574+00:00", "2026-11-05T11:15:28.451574+00:00")
DEPLOY_WINDOW = ("2026-11-05T11:33:58.129245+00:00", "2026-11-05T11:45:58.129245+00:00")
FLASH_WINDOW = ("2026-11-05T10:02:43.045948+00:00", "2026-11-05T10:14:43.045948+00:00")
ATTACKER_IP = "45.142.120.18"


def replay(name):
    recorded = json.loads((FIXTURES / f"{name}.json").read_text())
    return lambda path, params: recorded[telemetry.request_key(path, params)]


def collect(name, window, campaigns=FIXTURES / "campaigns.json"):
    start, end = (datetime.fromisoformat(t) for t in window)
    return telemetry.collect(start, end, replay(name), campaigns)


def by_source(evidence, title):
    return next(e for e in evidence if e["title"] == title)


def test_flood_window_points_at_one_masked_client():
    evidence, aliases = collect("flood-r1", FLOOD_WINDOW)

    assert all(e["status"] == "ok" for e in evidence)
    assert by_source(evidence, "traffic")["data"]["ratio"] > 5
    top = by_source(evidence, "clients")["data"]["top_recent"][0]
    assert top["client"] == "client-1" and top["share"] > 0.8
    assert aliases["client-1"] == ATTACKER_IP
    # Gerçek IP yalnız sorguda ve aliases'ta kalır; LLM'e giden özet ve veride yoktur.
    assert ATTACKER_IP not in json.dumps([(e["summary"], e["data"]) for e in evidence])
    detail = by_source(evidence, "client-1")["data"]
    assert detail["pages"].keys() == {"home"} and detail["sessions"] == 0
    assert by_source(evidence, "campaigns")["data"]["campaigns"] == []
    assert by_source(evidence, "deploys")["data"]["deploys"] == []


def test_deploy_window_shows_marker_and_checkout_errors():
    evidence, _ = collect("deploy-r1", DEPLOY_WINDOW)

    deploys = by_source(evidence, "deploys")["data"]["deploys"]
    assert [(d["service"], d["version"]) for d in deploys] == [("checkout", "v1.1.0")]
    errors = by_source(evidence, "app_errors")["data"]["recent"]
    assert {"service": "checkout", "exception": "KeyError", "count": 1} in errors
    assert by_source(evidence, "funnel")["data"]["recent"]["checkout_failed"] > 0


def test_campaign_window_finds_active_campaign():
    evidence, _ = collect("flash-r1", FLASH_WINDOW)

    campaigns = by_source(evidence, "campaigns")["data"]["campaigns"]
    assert [c["active_at_alarm"] for c in campaigns] == [True]
    assert by_source(evidence, "clients")["data"]["distinct_recent"] > 500


def test_unreachable_source_is_recorded_not_raised():
    def down(path, params):
        raise urllib.error.URLError("connection refused")

    start, end = (datetime.fromisoformat(t) for t in FLOOD_WINDOW)
    evidence, _ = telemetry.collect(start, end, down, FIXTURES / "campaigns.json")

    assert {e["status"] for e in evidence if e["source"] != "campaigns.json"} == {
        "unreachable"
    }
    assert by_source(evidence, "campaigns")["status"] == "ok"
