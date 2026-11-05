"""Kampanya takvimi: senaryo koşucusu yazar, agent okur. İkisi aynı biçime güvenir."""

import json
from datetime import datetime
from pathlib import Path

CALENDAR = Path(__file__).parents[1] / "scenarios" / "campaigns.json"
FIELDS = {
    "id": str,
    "name": str,
    "start": str,
    "end": str,
    "expected_traffic_multiplier": (int, float),
    "expected_conversion": (int, float),
}


def test_campaign_calendar_entries_are_well_formed():
    campaigns = json.loads(CALENDAR.read_text(encoding="utf-8"))["campaigns"]

    for campaign in campaigns:
        assert set(campaign) == set(FIELDS), campaign
        for field, kind in FIELDS.items():
            assert isinstance(campaign[field], kind), (campaign["id"], field)
        start, end = (datetime.fromisoformat(campaign[k]) for k in ("start", "end"))
        assert start.tzinfo and start < end, campaign["id"]
