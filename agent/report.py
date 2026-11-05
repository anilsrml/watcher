"""İnceleme raporunu nöbetçi mühendis için Markdown'a çevirir. Her iddianın yanında evidence_id'leri durur."""

LABEL_TEXT = {
    "attack": "Saldırı (attack)",
    "legit_campaign": "Meşru kampanya (legit_campaign)",
    "ops_failure": "Operasyonel arıza (ops_failure)",
    "unknown": "Belirsiz (unknown)",
}
CONFIDENCE_TEXT = {"high": "yüksek", "medium": "orta", "low": "düşük"}


def _cite(claim: dict) -> str:
    return f"{claim['text']} [{', '.join(claim['evidence_ids'])}]"


def _section(title: str, lines: list[str]) -> list[str]:
    return [f"## {title}", "", *([f"- {line}" for line in lines] or ["- yok"]), ""]


def render(report: dict) -> str:
    decision = report["decision"]
    meta = report["metadata"]
    out = [
        f"# {report['incident_id']}: {LABEL_TEXT[report['label']]}, güven {CONFIDENCE_TEXT[report['confidence']]}",
        "",
        f"**Karar:** {_cite(decision) if decision else 'Kanıta bağlı bir karar çıkmadı.'}",
        "",
        f"Pencere: {report['window']['start']} → {report['window']['end']} (alarm)",
        "",
    ]
    if report["abstain_reason"]:
        out += [f"**Çekimser kalındı:** {report['abstain_reason']}", ""]
    hypotheses = [
        f"{'Desteklenen' if h.get('verdict') == 'supported' else 'Elenen'}: {h.get('label')}: {_cite(h)}"
        for h in report["hypotheses"]
    ]
    out += _section("Etki", [_cite(c) for c in report["impact"]])
    out += _section("Zaman çizelgesi", [_cite(c) for c in report["timeline"]])
    out += _section("Hipotezler", hypotheses)
    out += _section(
        "Beni ne yanıltabilir?", [_cite(c) for c in report["could_mislead"]]
    )
    out += _section("Eksik kanıt", report["missing_evidence"])
    out += _section("Sonraki adımlar (insan karar verir)", report["next_steps"])
    out += [
        "## Kanıtlar",
        "",
        "| evidence_id | Kaynak | Durum | Özet |",
        "|---|---|---|---|",
    ]
    out += [
        f"| {e['evidence_id']} | {e['source']} | {e['status']} | {e['summary'].replace('|', '/')} |"
        for e in report["evidence"]
    ]
    out += ["", "## İstemci takma adları", "", "LLM'e yalnız takma adlar gitti.", ""]
    out += [f"- {alias}: {ip}" for alias, ip in report["aliases"].items()] or ["- yok"]
    out += [
        "",
        "## Agent metadata",
        "",
        f"- Model: {meta['model']}",
        f"- Telemetri sorgusu: {meta['queries']}, LLM çağrısı: 1",
        (
            f"- Token: {meta['input_tokens']} girdi, {meta['output_tokens']} çıktı; maliyet: "
            f"{'$' + format(meta['cost_usd'], '.4f') if meta['cost_usd'] is not None else 'bilinmiyor'}"
        ),
        f"- Süre: toplama {meta['collect_seconds']} sn, LLM {meta['llm_seconds']} sn, toplam {meta['total_seconds']} sn",
        f"- Atıf geçerliliği: %{report['citation_validity'] * 100:.0f}",
        "",
        "## Geçersiz atıflar",
        "",
        "Var olmayan, erişilemeyen ya da boş evidence_id'ye dayandığı için rapordan çıkarılan iddialar:",
        "",
    ]
    out += [
        f"- {c.get('text') if isinstance(c, dict) else c} {c.get('evidence_ids') if isinstance(c, dict) else ''}"
        for c in report["invalid_claims"]
    ] or ["- yok"]
    return "\n".join(out) + "\n"
