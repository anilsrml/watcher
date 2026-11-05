# Holdout (r3), single-shot LLM

Tarih: 2026-11-05T21:17:48+03:00

- **macro-F1: 0.778** (4 koşu; unknown kaçırma sayılır)
- Doğru: 3/4
- Ortalama atıf geçerliliği: %100
- Olay başına ortalama maliyet: bilinmiyor
- Ortalama rapor süresi: 31.4 sn

| Koşu | incident_id | Doğru etiket | Tahmin | Güven | Atıf | Maliyet | Süre (sn) |
|---|---|---|---|---|---|---|---|
| attack-homepage-flood-01-r3 | inc-3d655ccc | attack | attack | high | %100 | ? | 34.4 |
| campaign-flash-sale-01-r3 | inc-82896cc0 | legit_campaign | legit_campaign | high | %100 | ? | 21.6 |
| campaign-rate-limit-01-r3 | inc-41d3d3b2 | legit_campaign | attack ✗ | medium | %100 | ? | 48.6 |
| ops-checkout-deploy-01-r3 | inc-fd5e6961 | ops_failure | ops_failure | high | %100 | ? | 21.2 |
