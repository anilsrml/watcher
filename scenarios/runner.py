"""Bir senaryoyu baştan sona koşar ve koşu kaydını yazar.

Kullanım: uv run --env-file .env python scenarios/runner.py ops-checkout-deploy-01
Deneme:   uv run --env-file .env python scenarios/runner.py ops-checkout-deploy-01 --trial 60,180,60

Akış: 10 dk normal trafik, 15 dk olay, 5 dk toparlanma. Alarm olaydan 2 dk sonra kaydedilir;
agent'a yalnız incident_id ve pencere verilir. Deneme koşuları tekrar sayılmaz.
Kill switch: Ctrl+C ya da `docker --context default stop watcher-k6`. Koşucu k6'yı durdurur,
checkout'u v1.0.0'a döndürür ve kaydı aborted işaretler.
"""

import argparse
import json
import os
import random
import secrets
import subprocess
import sys
import time
import urllib.request
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCENARIO_DIR = ROOT / "scenarios"
RUNS = SCENARIO_DIR / "runs"
CALENDAR = SCENARIO_DIR / "campaigns.json"
K6_IMAGE = "grafana/k6:2.3.0"
SERVICES = ("frontend", "product", "cart", "checkout", "payment")

SCENARIOS = {
    "campaign-flash-sale-01": {"INCIDENT": "campaign"},
    "attack-homepage-flood-01": {"INCIDENT": "flood", "ATTACKER_IP": "45.142.120.18"},
    "campaign-rate-limit-01": {
        "INCIDENT": "nat_campaign",
        "NAT_IPS": "176.40.12.7,176.40.12.19",
    },
    "ops-checkout-deploy-01": {"INCIDENT": "none", "deploy": ("checkout", "v1.1.0")},
}
PHASES = (600, 900, 300)  # saniye: normal trafik, olay, toparlanma
ALARM_AFTER_S = 120
REPETITIONS = 3
MAX_CLOCK_OFFSET_S = 2
CAMPAIGN_NAMES = (
    "Kasım Fırsatları",
    "Hafta Sonu İndirimi",
    "Flaş Fırsat Saati",
    "Teknoloji Günleri",
    "Sepette Ekstra İndirim",
    "Gece Yarısı Fırsatı",
)


def plan(scenario: str, repetition: int | None, started: datetime, phases) -> dict:
    """repetition None ise deneme koşusudur."""
    baseline, incident, recovery = phases
    at = lambda seconds: (started + timedelta(seconds=seconds)).isoformat()
    alarm = baseline + min(ALARM_AFTER_S, incident // 2)
    trial = repetition is None
    suffix = f"trial-{started:%Y%m%dT%H%M%SZ}" if trial else f"r{repetition}"
    return {
        "run_id": f"{scenario}-{suffix}",
        "incident_id": f"inc-{secrets.token_hex(4)}",
        "scenario_id": scenario,
        "repetition": repetition,
        "trial": trial,
        "holdout": repetition == REPETITIONS,
        "phases_s": list(phases),
        "started_at": started.isoformat(),
        "incident_start": at(baseline),
        "alarm_at": at(alarm),
        "incident_end": at(baseline + incident),
        "planned_end": at(baseline + incident + recovery),
        "window": {"start": started.isoformat(), "end": at(alarm)},
    }


def next_repetition(scenario: str, runs: Path) -> int:
    done = sum(
        1
        for path in runs.glob("*.json")
        if (r := json.loads(path.read_text()))["scenario_id"] == scenario
        and not r["trial"]
        and not r.get("aborted")
    )
    if done >= REPETITIONS:
        sys.exit(f"{scenario}: {REPETITIONS} tekrar zaten koşuldu")
    return done + 1


def record_path(runs: Path, run: dict) -> Path:
    # Yarıda kalan koşu tekrar sayılmaz; kaydı durur, adını yeniden koşuya bırakır.
    started = datetime.fromisoformat(run["started_at"])
    suffix = f"-aborted-{started:%Y%m%dT%H%M%SZ}" if run.get("aborted") else ""
    return runs / f"{run['run_id']}{suffix}.json"


def add_campaign(calendar: Path, run: dict) -> dict:
    entry = {
        "id": f"kmp-{datetime.fromisoformat(run['incident_start']):%Y%m%d-%H%M}",
        "name": random.choice(CAMPAIGN_NAMES),
        "start": run["incident_start"],
        "end": run["incident_end"],
        "expected_traffic_multiplier": 5,
        "expected_conversion": 0.05,
    }
    data = json.loads(calendar.read_text(encoding="utf-8"))
    data["campaigns"].append(entry)
    calendar.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return entry


def clock_offset(date_header: str, now: datetime) -> float:
    return (parsedate_to_datetime(date_header) - now).total_seconds()


def release(env: list[str]) -> str:
    attributes = next(e for e in env if e.startswith("OTEL_RESOURCE_ATTRIBUTES="))
    return attributes.split("service.version=", 1)[1].split(",", 1)[0]


def ground_truth_commit(path: Path) -> str:
    git = ["git", "-C", str(path.parent)]
    tracked = subprocess.run(
        [*git, "ls-files", "--error-unmatch", path.name],
        check=False,
        capture_output=True,
    )
    unchanged = subprocess.run(
        [*git, "diff", "--quiet", "HEAD", "--", path.name], check=False
    )
    if tracked.returncode or unchanged.returncode:
        sys.exit(f"{path}: ground truth koşudan önce commit'lenmeli")
    log = [*git, "log", "-1", "--format=%H", "--", path.name]
    return subprocess.run(
        log, capture_output=True, text=True, check=True
    ).stdout.strip()


def vps(*args: str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "--context", "watcher-vds", *args], check=True, **kwargs
    )


def check_clock() -> None:
    synced = subprocess.run(
        ["timedatectl", "show", "-p", "NTPSynchronized", "--value"],
        check=False,
        capture_output=True,
        text=True,
    )
    if synced.stdout.strip() != "yes":
        sys.exit("dizüstü saati NTP ile senkron değil")
    with urllib.request.urlopen(
        f"http://{os.environ['LAB_BIND_IP']}/healthz", timeout=10
    ) as r:
        offset = clock_offset(r.headers["Date"], datetime.now(UTC))
    if abs(offset) > MAX_CLOCK_OFFSET_S:
        sys.exit(f"VPS saati {offset:+.0f} sn kayık; NTP'nin düzeltmesini bekle")


def check_versions() -> None:
    for service in SERVICES:
        env = vps(
            "inspect",
            f"watcher-lab-{service}-1",
            "--format",
            "{{json .Config.Env}}",
            capture_output=True,
            text=True,
        )
        if (found := release(json.loads(env.stdout))) != "v1.0.0":
            sys.exit(f"{service} {found} sürümünde; koşu v1.0.0 ile başlar")


def host_profile() -> dict:
    # Gürültü, sabit bir işin koşular arasındaki süre sapmasıyla ölçülür (VMware steal time göstermeyebilir).
    job = (
        "import time; t = time.perf_counter(); sum(i * i for i in range(5_000_000)); d = time.perf_counter() - t;"
        "m = next(l for l in open('/proc/cpuinfo') if l.startswith('model name')).split(':')[1].strip();"
        "print(m); print(round(d, 3))"
    )
    out = vps(
        "exec",
        "watcher-lab-payment-1",
        "python",
        "-c",
        job,
        capture_output=True,
        text=True,
    )
    cpu_model, seconds = out.stdout.strip().splitlines()
    return {"cpu_model": cpu_model, "noise_job_s": float(seconds)}


def deploy(service: str, version: str) -> str:
    subprocess.run(
        [sys.executable, "lab/deploy.py", service, version], cwd=ROOT, check=True
    )
    return datetime.now(UTC).isoformat()


def start_k6(scenario: dict, phases) -> subprocess.Popen:
    env = {
        "LAB_BIND_IP": os.environ["LAB_BIND_IP"],
        **{k: v for k, v in scenario.items() if k != "deploy"},
        **dict(zip(("BASELINE_S", "INCIDENT_S", "RECOVERY_S"), map(str, phases))),
    }
    flags = [arg for k, v in env.items() for arg in ("-e", f"{k}={v}")]
    command = [
        "docker",
        "--context",
        "default",
        "run",
        "--rm",
        "-i",
        "--name",
        "watcher-k6",
    ]
    command += ["--network", "host", *flags, K6_IMAGE, "run", "--quiet", "-"]
    with open(ROOT / "loadgen" / "shop.js", "rb") as script:
        return subprocess.Popen(command, stdin=script)


def run(scenario_id: str, phases, trial: bool, runs: Path) -> dict:
    scenario = SCENARIOS[scenario_id]
    truth = ground_truth_commit(SCENARIO_DIR / scenario_id / "ground_truth.json")
    repetition = None if trial else next_repetition(scenario_id, runs)
    check_clock()
    check_versions()
    host = host_profile()

    started = datetime.now(UTC)
    record = plan(scenario_id, repetition, started, phases)
    record |= {"ground_truth_commit": truth, "host": host, "aborted": False}
    if scenario["INCIDENT"] in ("campaign", "nat_campaign"):
        record["campaign_id"] = add_campaign(CALENDAR, record)["id"]
    for key in ("ATTACKER_IP", "NAT_IPS"):
        if key in scenario:
            record[key.lower()] = scenario[key]

    baseline, incident, _ = phases
    events = [(baseline + min(ALARM_AFTER_S, incident // 2), "alarm")]
    if "deploy" in scenario:
        events += [(baseline, "deploy"), (baseline + incident, "rollback")]
    print(f"{record['run_id']} başladı: {record['incident_id']}", flush=True)
    k6 = start_k6(scenario, phases)
    clock = time.monotonic()
    try:
        for offset, event in sorted(events):
            remaining = clock + offset - time.monotonic()
            if remaining > 0 and _exited(k6, remaining):
                raise RuntimeError(f"k6 erken bitti (çıkış {k6.returncode})")
            if event == "alarm":
                print(
                    f"ALARM {record['incident_id']} pencere {record['window']}",
                    flush=True,
                )
            elif event == "deploy":
                record["deploy"] = {
                    "service": scenario["deploy"][0],
                    "version": scenario["deploy"][1],
                }
                record["deploy"]["at"] = deploy(*scenario["deploy"])
            else:
                record["deploy"]["rollback_at"] = deploy(
                    scenario["deploy"][0], "v1.0.0"
                )
        record["k6_exit"] = k6.wait()
    except BaseException:
        record["aborted"] = True
        subprocess.run(
            ["docker", "--context", "default", "stop", "watcher-k6"],
            check=False,
            capture_output=True,
        )
        if "deploy" in record and "rollback_at" not in record["deploy"]:
            record["deploy"]["rollback_at"] = deploy(scenario["deploy"][0], "v1.0.0")
        raise
    finally:
        record["ended_at"] = datetime.now(UTC).isoformat()
        runs.mkdir(exist_ok=True)
        path = record_path(runs, record)
        path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"kayıt: {path}", flush=True)
    return record


def _exited(process: subprocess.Popen, timeout: float) -> bool:
    try:
        process.wait(timeout=timeout)
        return True
    except subprocess.TimeoutExpired:
        return False


def phases_arg(value: str) -> tuple[int, int, int]:
    baseline, incident, recovery = (int(v) for v in value.split(","))
    return baseline, incident, recovery


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("scenario", choices=SCENARIOS)
    parser.add_argument(
        "--trial",
        type=phases_arg,
        nargs="?",
        const=(60, 180, 60),
        metavar="B,I,R",
        help="kısa deneme koşusu, saniye: normal,olay,toparlanma (varsayılan 60,180,60)",
    )
    parser.add_argument("--runs-dir", type=Path, default=RUNS)
    args = parser.parse_args()
    run(args.scenario, args.trial or PHASES, args.trial is not None, args.runs_dir)


if __name__ == "__main__":
    main()
