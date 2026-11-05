"""Agent'ı koşulmuş senaryolarda çalıştırır: koşu başına tahmin ve doğru etiket, macro-F1.

Kullanım: uv run --env-file .env python agent/evaluate.py             # geliştirme seti: r1, r2
Holdout:  uv run --env-file .env python agent/evaluate.py --holdout   # r3; yalnız bir kez, sonuç agent/eval/holdout.md

incident_id'yi ground truth'la yalnız bu betik eşler; agent koşu kayıtlarını ve ground truth'u okumaz.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parents[1]
RUNS = ROOT / "scenarios" / "runs"
CLASSES = ("attack", "legit_campaign", "ops_failure")


def select_runs(holdout: bool, runs_dir: Path = RUNS) -> list[dict]:
    runs = [json.loads(p.read_text()) for p in sorted(runs_dir.glob("*.json"))]
    return [
        r
        for r in runs
        if not r["trial"] and not r.get("aborted") and r["holdout"] == holdout
    ]


def truth(scenario_id: str) -> str:
    return json.loads(
        (ROOT / "scenarios" / scenario_id / "ground_truth.json").read_text()
    )["label"]


def macro_f1(pairs: list[tuple[str, str]]) -> float:
    """pairs: (doğru, tahmin). unknown tahmini yalnız kaçırma sayılır; hiçbir sınıfa yanlış pozitif yazmaz."""
    scores = []
    for c in CLASSES:
        tp = sum(t == c and p == c for t, p in pairs)
        fp = sum(t != c and p == c for t, p in pairs)
        fn = sum(t == c and p != c for t, p in pairs)
        scores.append(2 * tp / (2 * tp + fp + fn) if tp else 0.0)
    return sum(scores) / len(scores)


def evaluate(runs: list[dict], investigate) -> list[dict]:
    rows = []
    for run in runs:
        start, end = (
            datetime.fromisoformat(run["window"][k]) for k in ("start", "end")
        )
        result = investigate(run["incident_id"], start, end)
        rows.append(
            {
                "run_id": run["run_id"],
                "incident_id": run["incident_id"],
                "truth": truth(run["scenario_id"]),
                "predicted": result["label"],
                "confidence": result["confidence"],
                "citation_validity": result["citation_validity"],
                "cost_usd": result["metadata"]["cost_usd"],
                "seconds": result["metadata"]["total_seconds"],
            }
        )
        print(
            f"{run['run_id']}: {rows[-1]['truth']} → {rows[-1]['predicted']}",
            flush=True,
        )
    return rows


def render(rows: list[dict], title: str) -> str:
    score = macro_f1([(r["truth"], r["predicted"]) for r in rows])
    costs = [r["cost_usd"] for r in rows if r["cost_usd"] is not None]
    out = [
        f"# {title}",
        "",
        f"Tarih: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        "",
        f"- **macro-F1: {score:.3f}** ({len(rows)} koşu; unknown kaçırma sayılır)",
        f"- Doğru: {sum(r['truth'] == r['predicted'] for r in rows)}/{len(rows)}",
        f"- Ortalama atıf geçerliliği: %{sum(r['citation_validity'] for r in rows) / len(rows) * 100:.0f}",
        f"- Olay başına ortalama maliyet: {'$' + format(sum(costs) / len(costs), '.4f') if costs else 'bilinmiyor'}",
        f"- Ortalama rapor süresi: {sum(r['seconds'] for r in rows) / len(rows):.1f} sn",
        "",
        "| Koşu | incident_id | Doğru etiket | Tahmin | Güven | Atıf | Maliyet | Süre (sn) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    out += [
        f"| {r['run_id']} | {r['incident_id']} | {r['truth']} | {r['predicted']}{'' if r['truth'] == r['predicted'] else ' ✗'} "
        f"| {r['confidence']} | %{r['citation_validity'] * 100:.0f} "
        f"| {'$' + format(r['cost_usd'], '.4f') if r['cost_usd'] is not None else '?'} | {r['seconds']} |"
        for r in rows
    ]
    return "\n".join(out) + "\n"


def main(argv=None, investigate=None, out_dir: Path = ROOT / "agent" / "eval") -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--holdout", action="store_true", help="r3 koşuları; yalnız bir kez"
    )
    args = parser.parse_args(argv)
    path = out_dir / ("holdout.md" if args.holdout else "dev.md")
    if args.holdout and path.exists():
        sys.exit(f"{path} zaten var: holdout bir kez ölçülür")
    if investigate is None:
        import investigate as agent

        investigate = agent.run
    rows = evaluate(select_runs(args.holdout), investigate)
    title = (
        "Holdout (r3), single-shot LLM"
        if args.holdout
        else "Geliştirme seti (r1, r2), single-shot LLM"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(render(rows, title))
    print(
        f"macro-F1 {macro_f1([(r['truth'], r['predicted']) for r in rows]):.3f} → {path}"
    )


if __name__ == "__main__":
    main()
