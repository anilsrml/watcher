# Geliştirme seti (r1, r2), single-shot LLM

Tarih: 2026-11-05T21:15:05+03:00

- **macro-F1: 1.000** (8 koşu; unknown kaçırma sayılır)
- Doğru: 8/8
- Ortalama atıf geçerliliği: %100
- Olay başına ortalama maliyet: bilinmiyor
- Ortalama rapor süresi: 27.1 sn

| Koşu | incident_id | Doğru etiket | Tahmin | Güven | Atıf | Maliyet | Süre (sn) |
|---|---|---|---|---|---|---|---|
| attack-homepage-flood-01-r1 | inc-6af22b72 | attack | attack | high | %100 | ? | 28.7 |
| attack-homepage-flood-01-r2 | inc-558daa54 | attack | attack | high | %100 | ? | 22.9 |
| campaign-flash-sale-01-r1 | inc-17fbe148 | legit_campaign | legit_campaign | high | %100 | ? | 27.8 |
| campaign-flash-sale-01-r2 | inc-175be149 | legit_campaign | legit_campaign | high | %100 | ? | 22.7 |
| campaign-rate-limit-01-r1 | inc-537b4c41 | legit_campaign | legit_campaign | medium | %100 | ? | 34.8 |
| campaign-rate-limit-01-r2 | inc-6a11e6f7 | legit_campaign | legit_campaign | medium | %100 | ? | 42.0 |
| ops-checkout-deploy-01-r1 | inc-2ef0e0db | ops_failure | ops_failure | high | %100 | ? | 16.4 |
| ops-checkout-deploy-01-r2 | inc-fa383e33 | ops_failure | ops_failure | high | %100 | ? | 21.9 |
