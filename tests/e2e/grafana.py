"""e2e testleri için Grafana datasource proxy yardımcıları. Backend portları kapalı; sorgular Grafana'dan geçer."""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

LAB_IP = os.environ.get("LAB_BIND_IP")
GRAFANA = f"http://{LAB_IP}:3000/api/datasources/proxy/uid"
WAIT_SECONDS = 60


def get_json(path, **params):
    url = f"{GRAFANA}/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.load(response)


def eventually(check):
    # Tempo, ilk trace yeni gelirken bir kez 400 döndü; süre bitene kadar hatayı "henüz yok" say.
    deadline = time.monotonic() + WAIT_SECONDS
    while True:
        try:
            result, error = check(), None
        except urllib.error.HTTPError as exc:
            result, error = None, exc
        if result or time.monotonic() >= deadline:
            if error:
                raise error
            return result
        time.sleep(3)
