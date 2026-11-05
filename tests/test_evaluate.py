"""Değerlendirme: geliştirme ve holdout koşuları ayrı seçilir, macro-F1 doğru hesaplanır, holdout bir kez ölçülür."""

import pytest

import evaluate


def test_dev_and_holdout_runs_do_not_overlap():
    dev = evaluate.select_runs(holdout=False)
    holdout = evaluate.select_runs(holdout=True)

    assert len(dev) == 8 and {r["repetition"] for r in dev} == {1, 2}
    assert len(holdout) == 4 and {r["repetition"] for r in holdout} == {3}


def test_macro_f1_counts_unknown_as_a_miss():
    perfect = [
        ("attack", "attack"),
        ("legit_campaign", "legit_campaign"),
        ("ops_failure", "ops_failure"),
    ]
    assert evaluate.macro_f1(perfect) == 1.0

    abstained = [
        ("attack", "attack"),
        ("legit_campaign", "legit_campaign"),
        ("ops_failure", "unknown"),
    ]
    assert evaluate.macro_f1(abstained) == pytest.approx(2 / 3)

    confused = [("legit_campaign", "attack"), ("attack", "attack")]
    # attack: P=1/2, R=1 → 2/3; legit_campaign: 0; ops_failure yok → 0
    assert evaluate.macro_f1(confused) == pytest.approx((2 / 3) / 3)


def fake_investigate(incident_id, start, end):
    return {
        "label": "attack",
        "confidence": "high",
        "citation_validity": 1.0,
        "metadata": {"cost_usd": 0.01, "total_seconds": 4.2},
    }


def test_holdout_is_measured_only_once(tmp_path):
    evaluate.main(["--holdout"], fake_investigate, tmp_path)
    assert "macro-F1" in (tmp_path / "holdout.md").read_text()

    with pytest.raises(SystemExit):
        evaluate.main(["--holdout"], fake_investigate, tmp_path)


def test_dev_report_lists_every_run(tmp_path):
    evaluate.main([], fake_investigate, tmp_path)

    text = (tmp_path / "dev.md").read_text()
    assert text.count("| attack-homepage-flood-01-r") == 2
    assert "r3" not in text
