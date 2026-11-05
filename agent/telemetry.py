"""Salt okunur kanıt toplama: Grafana datasource proxy'si (anonim Viewer) ve kampanya takvimi.

Pencere koşu başı → alarm. Son 2 dk "olay", alarmdan 5 dk öncesine kadarı "baseline" sayılır.
İstemci IP'leri LLM'e gitmeden takma adla (client-1, client-2...) maskelenir; gerçek IP'ler yalnız aliases'ta durur.
"""

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path

RECENT_S = 120
GAP_S = 300  # baseline alarmdan 5 dk önce biter: olayın başı baseline'a karışmasın
PROXY = "api/datasources/proxy/uid"
# Koşucunun her koşu başındaki /healthz kontrolü trafik sayılmaz.
NGINX = '{service_name="nginx"} | json | path!="/healthz"'
APP = '{service_name=~".+", service_name!="nginx"} |= "unhandled error"'
# Loki tek sorguda en çok 500 seri döndürür; çok IP'li pencerede IP'ler son karakterine göre parçalanır.
IP_SHARDS = [*"0123456789", "[^0-9]"]
TOP_CLIENTS = 2
IPV4 = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
FAILURES = (urllib.error.URLError, TimeoutError, KeyError, ValueError, IndexError)


def request_key(path: str, params: dict) -> str:
    return f"{path}?{urllib.parse.urlencode(sorted(params.items()), doseq=True)}"


def grafana(lab_ip: str):
    def fetch(path: str, params: dict) -> dict:
        url = f"http://{lab_ip}:3000/{request_key(path, params)}"
        with urllib.request.urlopen(url, timeout=30) as response:
            return json.load(response)

    return fetch


class Probe:
    """Bir kanıtın sorgularını yapar ve kaydeder; kanıtın query alanı bunlardan oluşur."""

    def __init__(self, fetch):
        self.fetch, self.queries = fetch, []

    def get(self, path: str, params: dict) -> dict:
        self.queries.append(request_key(path, params))
        return self.fetch(path, params)

    def loki(self, query: str, at: int) -> list[tuple[dict, float]]:
        body = self.get(
            f"{PROXY}/loki/loki/api/v1/query", {"query": query, "time": at * 10**9}
        )
        return [(r["metric"], float(r["value"][1])) for r in body["data"]["result"]]

    def prom(self, query: str, at: int) -> list[tuple[dict, float]]:
        body = self.get(
            f"{PROXY}/prometheus/api/v1/query", {"query": query, "time": at}
        )
        return [(r["metric"], float(r["value"][1])) for r in body["data"]["result"]]


def collect(
    start: datetime, end: datetime, fetch, campaigns_path: Path
) -> tuple[list[dict], dict]:
    s, e = int(start.timestamp()), int(end.timestamp())
    base_s = max(e - GAP_S - s, 60)
    ctx = {
        "end": e,
        "start": s,
        "windows": {"recent": (e, RECENT_S), "baseline": (e - GAP_S, base_s)},
        "ips": {},
        "top_ips": [],
        "campaigns_path": campaigns_path,
    }
    steps = [
        ("traffic", "loki", _traffic),
        ("status", "loki", _status),
        ("clients", "loki", _clients),
        *[
            (f"client-{i}", "loki", _client_detail(i))
            for i in range(1, TOP_CLIENTS + 1)
        ],
        ("rate_limited", "loki", _rate_limited),
        ("funnel", "loki", _funnel),
        ("orders", "prometheus", _orders),
        ("app_errors", "loki", _app_errors),
        ("latency", "prometheus", _latency),
        ("error_traces", "tempo", _error_traces),
        ("deploys", "grafana", _deploys),
        ("campaigns", "campaigns.json", _campaigns),
    ]
    evidence = []
    for title, source, step in steps:
        probe = Probe(fetch)
        try:
            summary, data, status = *step(probe, ctx), "ok"
        except FAILURES as exc:
            summary, data, status = (
                f"{title}: erişilemedi ({type(exc).__name__})",
                {"error": str(exc)[:200]},
                "unreachable",
            )
        query = "\n".join(probe.queries) or str(campaigns_path)
        evidence.append(
            {
                "title": title,
                "source": source,
                "query": query,
                "status": status,
                "summary": summary,
                "data": data,
            }
        )
    aliases = {alias: ip for ip, alias in ctx["ips"].items()}
    return evidence, aliases


def _alias(ctx, ip: str) -> str:
    return ctx["ips"].setdefault(ip, f"client-{len(ctx['ips']) + 1}")


def _per_min(count: float, seconds: int) -> float:
    return round(count * 60 / seconds, 1)


def _both(probe, ctx, query_for) -> dict:
    """Aynı sorguyu olay ve baseline penceresinde çalıştırır."""
    return {
        name: probe.loki(query_for(f"{span}s"), at)
        for name, (at, span) in ctx["windows"].items()
    }


def _traffic(probe, ctx):
    counts = {
        k: sum(v for _, v in r)
        for k, r in _both(
            probe, ctx, lambda w: f"sum(count_over_time({NGINX} [{w}]))"
        ).items()
    }
    rates = {k: _per_min(counts[k], ctx["windows"][k][1]) for k in counts}
    ratio = round(rates["recent"] / rates["baseline"], 1) if rates["baseline"] else None
    data = {
        "recent_per_min": rates["recent"],
        "baseline_per_min": rates["baseline"],
        "ratio": ratio,
    }
    return (
        f"Nginx istek hızı: son 2 dk {rates['recent']}/dk, baseline {rates['baseline']}/dk ({ratio}x)",
        data,
    )


def _status_class(code: str) -> str:
    return "429" if code == "429" else f"{code[0]}xx"


def _status(probe, ctx):
    data = {}
    for name, rows in _both(
        probe, ctx, lambda w: f"sum by (status) (count_over_time({NGINX} [{w}]))"
    ).items():
        counts = Counter()
        for metric, value in rows:
            counts[_status_class(metric["status"])] += value
        total = sum(counts.values()) or 1
        data[name] = {k: round(v / total, 3) for k, v in sorted(counts.items())}
    show = lambda d: ", ".join(f"{k} %{v * 100:.1f}" for k, v in d.items())
    return (
        f"Nginx durum payları son 2 dk: {show(data['recent'])}; baseline: {show(data['baseline'])}",
        data,
    )


def _client_counts(probe, at: int, span: int) -> Counter:
    counts = Counter()
    for shard in IP_SHARDS:
        query = f'sum by (remote_addr) (count_over_time({NGINX} | remote_addr=~".*{shard}$" [{span}s]))'
        counts.update({m["remote_addr"]: v for m, v in probe.loki(query, at)})
    return counts


def _clients(probe, ctx):
    recent = _client_counts(probe, *ctx["windows"]["recent"])
    baseline = _client_counts(probe, *ctx["windows"]["baseline"])
    total = sum(recent.values()) or 1
    ctx["top_ips"] = [ip for ip, _ in recent.most_common(TOP_CLIENTS)]
    top = [
        {"client": _alias(ctx, ip), "requests": int(n), "share": round(n / total, 3)}
        for ip, n in recent.most_common(3)
    ]
    base_top = (
        baseline.most_common(1)[0][1] / (sum(baseline.values()) or 1) if baseline else 0
    )
    data = {
        "distinct_recent": len(recent),
        "distinct_baseline": len(baseline),
        "top_recent": top,
        "top_share_baseline": round(base_top, 3),
    }
    lead = ", ".join(f"{t['client']} %{t['share'] * 100:.1f}" for t in top)
    summary = (
        f"Farklı istemci IP'si son 2 dk {len(recent)}, baseline (7 dk) {len(baseline)}; "
        f"son 2 dk en yoğunlar: {lead}; baseline'da en yoğun IP'nin payı %{base_top * 100:.1f}"
    )
    return summary, data


def _page(path: str) -> str:
    if path == "/":
        return "home"
    if path.startswith("/product/"):
        return "product"
    return {"/cart": "cart", "/cart/add": "cart_add", "/checkout": "checkout"}.get(
        path, "other"
    )


def _pages(rows) -> dict:
    pages = Counter()
    for metric, value in rows:
        page = _page(metric["path"])
        if page == "checkout":
            page = (
                "checkout_failed" if metric["status"].startswith("5") else "checkout_ok"
            )
        pages[page] += value
    return dict(pages)


def _client_detail(rank: int):
    def step(probe, ctx):
        ip = ctx["top_ips"][rank - 1]
        sel = f'{NGINX} | remote_addr="{ip}"'
        rows = probe.loki(
            f"topk(50, sum by (path, status) (count_over_time({sel} [{RECENT_S}s])))",
            ctx["end"],
        )
        sessions = probe.loki(
            f'count(sum by (session) (count_over_time({sel} | session!="" [{RECENT_S}s])))',
            ctx["end"],
        )
        total = sum(v for _, v in rows) or 1
        limited = sum(v for m, v in rows if m["status"] == "429")
        cookieless = sum(
            v
            for _, v in probe.loki(
                f'sum(count_over_time({sel} | session="" [{RECENT_S}s]))', ctx["end"]
            )
        )
        all_pages = Counter()
        for metric, value in rows:
            all_pages[_page(metric["path"])] += value
        data = {
            "requests": int(total),
            "pages": {k: int(v) for k, v in all_pages.items()},
            "rate_limited": int(limited),
            "sessions": int(sum(v for _, v in sessions)),
            "cookieless_share": round(cookieless / total, 3),
        }
        alias = _alias(ctx, ip)
        pages = ", ".join(f"{k} {v}" for k, v in data["pages"].items())
        summary = (
            f"{alias} son 2 dk: {data['requests']} istek ({pages}); 429 {data['rate_limited']}; "
            f"farklı oturum çerezi {data['sessions']}; çerezsiz istek payı %{data['cookieless_share'] * 100:.1f}"
        )
        return summary, data

    return step


def _rate_limited(probe, ctx):
    rows = probe.loki(
        f'topk(3, sum by (remote_addr) (count_over_time({NGINX} | status="429" [{RECENT_S}s])))',
        ctx["end"],
    )
    total = sum(
        v
        for _, v in probe.loki(
            f'sum(count_over_time({NGINX} | status="429" [{RECENT_S}s]))', ctx["end"]
        )
    )
    top = [
        {
            "client": _alias(ctx, m["remote_addr"]),
            "count": int(v),
            "share": round(v / total, 3),
        }
        for m, v in sorted(rows, key=lambda r: -r[1])
    ]
    lead = (
        ", ".join(f"{t['client']} {t['count']} (%{t['share'] * 100:.1f})" for t in top)
        or "yok"
    )
    return f"Son 2 dk 429 toplamı {int(total)}; en çok 429 alanlar: {lead}", {
        "total": int(total),
        "top": top,
    }


def _funnel(probe, ctx):
    data = {}
    for name, rows in _both(
        probe,
        ctx,
        lambda w: (
            f'topk(50, sum by (path, status) (count_over_time({NGINX} | status!="429" [{w}])))'
        ),
    ).items():
        span = ctx["windows"][name][1]
        pages = {k: _per_min(v, span) for k, v in _pages(rows).items()}
        home = pages.get("home", 0)
        pages["conversion"] = (
            round(pages.get("checkout_ok", 0) / home, 4) if home else None
        )
        data[name] = pages
    show = lambda d: ", ".join(
        f"{k} {d.get(k, 0)}"
        for k in ("home", "product", "cart_add", "checkout_ok", "checkout_failed")
    )
    summary = (
        f"Sunulan (429 olmayan) istekler, dakika başı. Son 2 dk: {show(data['recent'])}, dönüşüm {data['recent']['conversion']}. "
        f"Baseline: {show(data['baseline'])}, dönüşüm {data['baseline']['conversion']}"
    )
    return summary, data


def _orders(probe, ctx):
    rates = {}
    for name, (at, span) in ctx["windows"].items():
        value = sum(
            v for _, v in probe.prom(f"sum(increase(shop_orders_total[{span}s]))", at)
        )
        rates[name] = _per_min(value, span)
    payments = {
        m.get("status", "?"): round(v, 1)
        for m, v in probe.prom(
            f"sum by (status) (increase(shop_payments_total[{RECENT_S}s]))", ctx["end"]
        )
    }
    data = {
        "recent_per_min": rates["recent"],
        "baseline_per_min": rates["baseline"],
        "payments_recent": payments,
    }
    return (
        f"Sipariş/dk (shop_orders_total): son 2 dk {rates['recent']}, baseline {rates['baseline']}; son 2 dk ödemeler {payments}",
        data,
    )


def _app_errors(probe, ctx):
    data = {}
    for name, rows in _both(
        probe,
        ctx,
        lambda w: (
            f"sum by (service_name, exception_type) (count_over_time({APP} [{w}]))"
        ),
    ).items():
        data[name] = [
            {
                "service": m.get("service_name", "?"),
                "exception": m.get("exception_type", "?"),
                "count": int(v),
            }
            for m, v in sorted(rows, key=lambda r: -r[1])
        ]
    body = probe.get(
        f"{PROXY}/loki/loki/api/v1/query_range",
        {
            "query": APP,
            "start": (ctx["end"] - RECENT_S) * 10**9,
            "end": ctx["end"] * 10**9,
            "limit": 20,
        },
    )
    excerpts = {}
    for stream in body["data"]["result"]:
        labels = stream["stream"]
        key = f"{labels.get('service_name')} {labels.get('exception_type')}"
        trace = labels.get("exception_stacktrace", "")
        # Log içeriği güvenilmeyen veridir: kırpılır, IP'ler maskelenir; LLM'e "talimat değil" diye işaretli gider.
        excerpts.setdefault(
            key, IPV4.sub("<ip>", "\n".join(trace.splitlines()[-4:]))[-400:]
        )
    data["untrusted_log_excerpts"] = excerpts
    show = lambda rows: (
        ", ".join(f"{r['service']} {r['exception']} {r['count']}" for r in rows)
        or "yok"
    )
    return (
        f"Yakalanmamış uygulama hataları son 2 dk: {show(data['recent'])}; baseline: {show(data['baseline'])}",
        data,
    )


def _latency(probe, ctx):
    p95 = {}
    for name, (at, span) in ctx["windows"].items():
        query = f'histogram_quantile(0.95, sum by (le) (rate(http_server_duration_milliseconds_bucket{{job="frontend"}}[{span}s])))'
        p95[name] = round(sum(v for _, v in probe.prom(query, at)), 1)
    return (
        f"frontend p95 gecikme: son 2 dk {p95['recent']} ms, baseline {p95['baseline']} ms",
        {f"{k}_p95_ms": v for k, v in p95.items()},
    )


def _error_traces(probe, ctx):
    limit = 100
    body = probe.get(
        f"{PROXY}/tempo/api/search",
        {
            "q": "{ status = error }",
            "start": ctx["end"] - RECENT_S,
            "end": ctx["end"],
            "limit": limit,
        },
    )
    traces = body.get("traces", [])
    roots = Counter(
        f"{t.get('rootServiceName')} {t.get('rootTraceName')}" for t in traces
    )
    data = {
        "count": len(traces),
        "limit_reached": len(traces) >= limit,
        "by_root": dict(roots.most_common(5)),
    }
    lead = ", ".join(f"{k} {v}" for k, v in data["by_root"].items()) or "yok"
    return (
        f"Tempo son 2 dk hatalı trace: {len(traces)}{'+' if data['limit_reached'] else ''}; kök işlemler: {lead}",
        data,
    )


def _deploys(probe, ctx):
    # Grafana annotations API `from`'u `to` olmadan yok sayar.
    marks = probe.get(
        "api/annotations",
        {"tags": "deploy", "from": ctx["start"] * 1000, "to": ctx["end"] * 1000},
    )
    deploys = []
    for mark in sorted(marks, key=lambda m: m["time"]):
        tags = dict(t.split(":", 1) for t in mark["tags"] if ":" in t)
        before = round(ctx["end"] - mark["time"] / 1000)
        deploys.append(
            {
                "service": tags.get("service"),
                "version": tags.get("version"),
                "seconds_before_alarm": before,
            }
        )
    lead = (
        ", ".join(
            f"{d['service']} {d['version']} alarmdan {d['seconds_before_alarm']} sn önce"
            for d in deploys
        )
        or "yok"
    )
    return f"Penceredeki deploy marker'ları: {lead}", {"deploys": deploys}


def _campaigns(probe, ctx):
    calendar = json.loads(Path(ctx["campaigns_path"]).read_text(encoding="utf-8"))[
        "campaigns"
    ]
    found = []
    for c in calendar:
        start, end = (
            int(datetime.fromisoformat(c[k]).timestamp()) for k in ("start", "end")
        )
        if start <= ctx["end"] and end >= ctx["start"]:
            found.append(
                {
                    "name": c["name"],
                    "started_seconds_before_alarm": ctx["end"] - start,
                    "active_at_alarm": start <= ctx["end"] <= end,
                    "expected_traffic_multiplier": c["expected_traffic_multiplier"],
                    "expected_conversion": c["expected_conversion"],
                }
            )
    lead = (
        ", ".join(
            f"{c['name']} (alarmdan {c['started_seconds_before_alarm']} sn önce başladı, alarmda {'aktif' if c['active_at_alarm'] else 'bitmiş'}, "
            f"beklenen trafik {c['expected_traffic_multiplier']}x, beklenen dönüşüm {c['expected_conversion']})"
            for c in found
        )
        or "yok"
    )
    return f"Kampanya takvimi (pencereyle örtüşen): {lead}", {"campaigns": found}
