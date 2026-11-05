"""Bir alarmı salt okunur inceler: kanıt toplar, SQLite'a yazar, LLM'le sınıflandırır, JSON + Markdown rapor üretir.

Kullanım: uv run --env-file .env python agent/investigate.py inc-6af22b72 --start 2026-11-05T11:03:28+00:00 --end 2026-11-05T11:15:28+00:00
Pencere koşu başı → alarm. .env'de LAB_BIND_IP, LLM_MODEL ve LLM_API_KEY gerekli.
"""

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path

import classify
import report as markdown
import store
import telemetry

ROOT = Path(__file__).parents[1]
AGENT = ROOT / "agent"


def investigate(
    incident_id, start, end, fetch, complete, campaigns_path, db, reports_dir
) -> dict:
    started = time.monotonic()
    evidence, aliases = telemetry.collect(start, end, fetch, campaigns_path)
    collect_seconds = round(time.monotonic() - started, 1)
    evidence = store.save_evidence(db, incident_id, evidence)
    window = {"start": start.isoformat(), "end": end.isoformat()}
    answer = complete(classify.build_messages(incident_id, window, evidence))
    result = {
        "incident_id": incident_id,
        "window": window,
        **classify.parse(answer["text"], evidence),
    }
    result |= {
        "evidence": evidence,
        "aliases": aliases,
        "metadata": {
            **{
                k: answer[k]
                for k in (
                    "model",
                    "input_tokens",
                    "output_tokens",
                    "cost_usd",
                    "llm_seconds",
                )
            },
            "queries": sum(
                len(e["query"].splitlines())
                for e in evidence
                if e["source"] != "campaigns.json"
            ),
            "collect_seconds": collect_seconds,
            "total_seconds": round(time.monotonic() - started, 1),
        },
    }
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / f"{incident_id}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    (reports_dir / f"{incident_id}.md").write_text(markdown.render(result))
    return result


def run(
    incident_id: str,
    start: datetime,
    end: datetime,
    reports_dir: Path = AGENT / "reports",
) -> dict:
    return investigate(
        incident_id,
        start,
        end,
        telemetry.grafana(os.environ["LAB_BIND_IP"]),
        classify.litellm_complete(os.environ["LLM_MODEL"], os.environ["LLM_API_KEY"]),
        ROOT / "scenarios" / "campaigns.json",
        store.connect(AGENT / "evidence.db"),
        reports_dir,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("incident_id")
    parser.add_argument("--start", type=datetime.fromisoformat, required=True)
    parser.add_argument(
        "--end", type=datetime.fromisoformat, required=True, help="alarm anı"
    )
    args = parser.parse_args()
    result = run(args.incident_id, args.start, args.end)
    print(
        f"{args.incident_id}: {result['label']} ({result['confidence']}) → agent/reports/{args.incident_id}.md"
    )


if __name__ == "__main__":
    main()
