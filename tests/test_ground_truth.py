"""Ground truth her senaryo için koşudan önce yazılır; koşucu commit'lenmemiş etiketle başlamaz."""

import json
from pathlib import Path

import pytest

SCENARIOS = Path(__file__).parents[1] / "scenarios"
LABELS = {
    "campaign-flash-sale-01": "legit_campaign",
    "attack-homepage-flood-01": "attack",
    "campaign-rate-limit-01": "legit_campaign",
    "ops-checkout-deploy-01": "ops_failure",
}


@pytest.mark.parametrize("scenario", LABELS)
def test_ground_truth_is_written_for_every_scenario(scenario):
    truth = json.loads(
        (SCENARIOS / scenario / "ground_truth.json").read_text(encoding="utf-8")
    )

    assert set(truth) == {"scenario_id", "label", "root_cause", "expected_signals"}
    assert truth["scenario_id"] == scenario
    assert truth["label"] == LABELS[scenario]
    assert truth["root_cause"]
    assert truth["expected_signals"] and all(truth["expected_signals"])
