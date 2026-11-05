"""Senaryo koşucusunun lab'a dokunmayan mantığı: koşu planı, tekrarlar, kampanya kaydı, ön kontroller."""

import json
import re
import subprocess
from datetime import UTC, datetime

import pytest

import runner

T0 = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)


def test_every_scenario_has_ground_truth():
    written = {p.parent.name for p in runner.SCENARIO_DIR.glob("*/ground_truth.json")}

    assert set(runner.SCENARIOS) == written


def test_plan_puts_alarm_two_minutes_into_incident():
    plan = runner.plan("ops-checkout-deploy-01", 3, T0, runner.PHASES)

    assert plan["run_id"] == "ops-checkout-deploy-01-r3"
    assert plan["holdout"] is True and plan["trial"] is False
    assert plan["incident_start"] == "2026-11-05T12:10:00+00:00"
    assert plan["alarm_at"] == "2026-11-05T12:12:00+00:00"
    assert plan["incident_end"] == "2026-11-05T12:25:00+00:00"
    assert plan["planned_end"] == "2026-11-05T12:30:00+00:00"
    assert plan["window"] == {"start": T0.isoformat(), "end": plan["alarm_at"]}


def test_incident_id_does_not_reveal_scenario():
    ids = {
        runner.plan("attack-homepage-flood-01", 1, T0, runner.PHASES)["incident_id"]
        for _ in range(5)
    }

    assert len(ids) == 5
    assert all(re.fullmatch(r"inc-[0-9a-f]{8}", i) for i in ids)


def test_only_third_repetition_is_holdout():
    holdouts = [
        runner.plan("campaign-rate-limit-01", r, T0, runner.PHASES)["holdout"]
        for r in (1, 2, 3)
    ]

    assert holdouts == [False, False, True]


def test_trial_is_named_apart_and_never_holdout():
    plan = runner.plan("attack-homepage-flood-01", None, T0, (60, 180, 60))

    assert plan["trial"] is True and plan["holdout"] is False
    assert plan["run_id"] == "attack-homepage-flood-01-trial-20261105T120000Z"
    assert plan["alarm_at"] == "2026-11-05T12:02:30+00:00"


def test_trial_shorter_than_two_minutes_alarms_halfway():
    plan = runner.plan("ops-checkout-deploy-01", None, T0, (20, 60, 10))

    assert plan["alarm_at"] == "2026-11-05T12:00:50+00:00"


def record(runs, name, scenario, trial=False, aborted=False):
    (runs / f"{name}.json").write_text(
        json.dumps({"scenario_id": scenario, "trial": trial, "aborted": aborted})
    )


def test_repetitions_count_to_three_and_ignore_trials_and_aborted_runs(tmp_path):
    scenario = "campaign-flash-sale-01"
    assert runner.next_repetition(scenario, tmp_path) == 1

    record(tmp_path, "a", scenario)
    record(tmp_path, "b", scenario, trial=True)
    record(tmp_path, "c", "ops-checkout-deploy-01")
    record(tmp_path, "a-aborted", scenario, aborted=True)
    assert runner.next_repetition(scenario, tmp_path) == 2

    record(tmp_path, "d", scenario)
    record(tmp_path, "e", scenario)
    with pytest.raises(SystemExit):
        runner.next_repetition(scenario, tmp_path)


def test_campaign_entry_fits_calendar_and_hides_scenario(tmp_path):
    plan = runner.plan("campaign-rate-limit-01", 1, T0, runner.PHASES)
    calendar = tmp_path / "campaigns.json"
    calendar.write_text('{"campaigns": []}')

    entry = runner.add_campaign(calendar, plan)

    assert json.loads(calendar.read_text())["campaigns"] == [entry]
    assert (entry["start"], entry["end"]) == (
        plan["incident_start"],
        plan["incident_end"],
    )
    assert entry["expected_traffic_multiplier"] == 5
    assert entry["expected_conversion"] == 0.05
    text = f"{entry['id']} {entry['name']}".lower()
    assert not any(
        w in text
        for w in ("attack", "campaign", "rate", "limit", "nat", "test", "trial")
    )


def test_clock_offset_from_http_date_header():
    assert runner.clock_offset("Thu, 05 Nov 2026 12:00:03 GMT", T0) == 3


def test_release_is_read_from_container_env():
    env = [
        "PATH=/usr/bin",
        "OTEL_RESOURCE_ATTRIBUTES=service.version=v1.1.0",
        "SERVICE=checkout",
    ]

    assert runner.release(env) == "v1.1.0"


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def test_ground_truth_must_be_committed_and_unchanged(tmp_path):
    git(tmp_path, "init")
    truth = tmp_path / "ground_truth.json"
    truth.write_text("{}")
    with pytest.raises(SystemExit):
        runner.ground_truth_commit(truth)

    git(tmp_path, "add", ".")
    git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "gt")
    assert re.fullmatch(r"[0-9a-f]{40}", runner.ground_truth_commit(truth))

    truth.write_text('{"label": "changed"}')
    with pytest.raises(SystemExit):
        runner.ground_truth_commit(truth)


def test_aborted_run_keeps_its_record_without_taking_the_name(tmp_path):
    run = runner.plan("campaign-flash-sale-01", 1, T0, runner.PHASES)

    assert runner.record_path(tmp_path, run).name == "campaign-flash-sale-01-r1.json"
    run["aborted"] = True
    assert (
        runner.record_path(tmp_path, run).name
        == "campaign-flash-sale-01-r1-aborted-20261105T120000Z.json"
    )
