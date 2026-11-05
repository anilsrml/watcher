"""Bir mağaza servisini yeni sürümle yeniden başlatır ve Grafana'ya deploy marker'ı yazar.

Kullanım: uv run --env-file .env python lab/deploy.py checkout v1.4.2

Sürüm yalnız vX.Y.Z olabilir: agent'a cevabı sızdıracak kelimeler ("bozuk" vb.) marker'a giremez.
shortcut: sürüm kalıcı değil; düz `compose up` tüm servisleri v1.0.0'a döndürür. Senaryo koşucusu sürümü kendisi yönetecek.
"""

import argparse
import base64
import json
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path

SERVICES = ("frontend", "product", "cart", "checkout", "payment")
ROOT = Path(__file__).parents[1]


def version(value: str) -> str:
    if not re.fullmatch(r"v\d+\.\d+\.\d+", value):
        raise argparse.ArgumentTypeError("sürüm vX.Y.Z biçiminde olmalı")
    return value


def restart(service: str, release: str) -> None:
    env = {**os.environ, f"{service.upper()}_VERSION": release}
    compose = [
        "docker",
        "--context",
        "watcher-vds",
        "compose",
        "-f",
        "lab/compose.yaml",
    ]
    # --wait: marker, servis sağlık kontrolünü geçince yazılır.
    up = ["--env-file", ".env", "up", "-d", "--no-deps", "--wait", service]
    subprocess.run(compose + up, cwd=ROOT, env=env, check=True)


def mark(service: str, release: str) -> int:
    body = {
        "time": int(time.time() * 1000),
        "tags": ["deploy", f"service:{service}", f"version:{release}"],
        "text": f"{service} {release} deploy edildi",
    }
    auth = base64.b64encode(f"admin:{os.environ['GRAFANA_ADMIN_PASSWORD']}".encode())
    request = urllib.request.Request(
        f"http://{os.environ['LAB_BIND_IP']}:3000/api/annotations",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Basic {auth.decode()}",
        },
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)["id"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("service", choices=SERVICES)
    parser.add_argument("version", type=version)
    args = parser.parse_args()
    restart(args.service, args.version)
    print(f"marker {mark(args.service, args.version)}: {args.service} {args.version}")


if __name__ == "__main__":
    main()
