# inc-fa383e33: Operasyonel arıza (ops_failure), güven yüksek

**Karar:** Trafik hacmi ve istemci dağılımı normal; alarmdan 106 sn önce yapılan checkout v1.1.0 deploy'u sonrası checkout'ta KeyError ve frontend'de 500 zinciri oluşmuş, dönüşüm ve sipariş düşmüş — olay kötü bir deploy kaynaklı operasyonel arıza. [E01, E03, E06, E09, E11, E12, E07, E08]

Pencere: 2026-11-05T14:38:27.397843+00:00 → 2026-11-05T14:50:27.397843+00:00 (alarm)

## Etki

- Dönüşüm oranı %4.0'ten %2.78'e geriledi (~%30 bağıl düşüş). [E07]
- Sipariş hızı 3.5/dk'dan 2.1/dk'ya düştü (~%40 düşüş). [E08]
- Başarılı checkout 3.6/dk'dan 2.5/dk'ya inerken başarısız checkout 0'dan 1.0/dk'ya çıktı. [E07]
- Uygulama hataları baseline'da yokken son 2 dk'da checkout KeyError 2 ve frontend HTTPStatusError 2 olarak göründü; Nginx 5xx payı %0.3. [E09, E02]
- Gecikme etkilenmedi (p95 73.3 ms vs 71.9 ms); sorun kapasite değil, hata kaynaklı. [E10]

## Zaman çizelgesi

- Alarmdan 106 sn önce checkout v1.1.0 deploy marker'ı pencereye düştü. [E12]
- Son 2 dk'da checkout servisinde _bundle_discount içinde KeyError: 1 hatası ve frontend'te checkout'a giden POST /checkout'ta HTTP 500 kaynaklı HTTPStatusError oluştu. [E09]
- Tempo'da son 2 dk'da 2 hatalı trace, kök işlem frontend POST /checkout. [E11]
- Aynı 2 dakikada başarısız checkout 1.0/dk'ya çıkarken dönüşüm ve sipariş hızı baseline'ın altına indi. [E07, E08]
- İstek hızı baseline ile aynı (375.5/dk vs 360.0/dk, 1.0x) ve 429 sayısı sıfır kaldı. [E01, E06]

## Hipotezler

- Elenen: attack: İstek hızı baseline'ın 1.0 katı, tek istemci payı en fazla %1.2, 429 toplamı sıfır; tek IP'den L7 flood veya yoğunlaşmış kötü niyetli trafik yok. Farklı istemci IP sayısı hatta baseline'ın altında (193 vs 628). [E01, E03, E06]
- Elenen: legit_campaign: Pencereyle örtüşen kampanya kaydı yok; trafik artışı yok, aksine hata ve dönüşüm düşüşü var, bu kampanya davranışına uymaz. [E13, E01, E07]
- Desteklenen: ops_failure: Alarmdan 106 sn önceki checkout deploy'unu takiben _bundle_discount içinde KeyError: 1, frontend'te checkout'a giden isteklerde 500 ve hatalı trace'ler oluştu; başarısız checkout artarken dönüşüm/sipariş düştü. Trafik ve gecikme sabit olduğundan tablo kötü deploy ile uyumlu. [E12, E09, E11, E07, E08, E10]
- Elenen: unknown: Deploy zamanlaması, hata tipi (kod satırına işaret eden KeyError), etkilenen uç nokta ve dönüşüm/sipariş düşüşü aynı nedene işaret ediyor; karar vermeye yetecek kanıt mevcut. [E12, E09, E11, E07, E08]

## Beni ne yanıltabilir?

- client-1, client-2 ve client-3'ün birebir aynı istek dağılımı (9 istek; home 1, cart 2, cart_add 2, product 4) ve %11.1 çerezsiz payı bot/script izlenimi verebilir; ancak her biri toplamın yalnızca %1.2'si ve 429 yok, flood tanımını karşılamıyor. [E04, E05, E03, E06]
- Son 2 dk farklı istemci IP sayısının baseline'a göre düşük görünmesi (193 vs 628) ama baseline'ın 7 dakikalık pencereyi kapsaması, oranları yanlış yorumlamaya yol açabilir. [E03]
- Product isteklerinin 209.7/dk'dan 229.0/dk'ya hafif çıkması dikkat dağıtabilir; toplam hacim ve hata profili deploy kaynaklı arızayı destekliyor. [E07, E01]
- Nginx 5xx payının yalnızca %0.3 görünmesi, frontend'in checkout hatalarını kısmen yutması nedeniyle etkiyi olduğundan küçük gösterebilir. [E02, E09]

## Eksik kanıt

- checkout v1.1.0 deploy diff/changelog: _bundle_discount ve prices sözlüğü değişikliğinin bu sürümde olup olmadığı
- Deploy öncesi (baseline) checkout KeyError veya 500 loglarının olmadığını doğrulayan log kopyası
- Hatalı checkout'ların zaman içindeki dağılımı (deploy sonrası saniye bazlı hata oranı) ve hata sonrası toparlanma eğrisi
- KeyError'ı tetikleyen sepet içeriği/indirim kombinasyonu örnekleri (prices sözlüğünde eksik anahtar 1)
- Alarmın tam tanımı ve eşiği (hangi metrik tetikledi)
- Etkilenen oturum/istek sayısı ve ciro bazında gelir kaybı tahmini
- frontend 5xx'lerin hâlâ sürüp sürmediğine dair alarm anı sonrası veri

## Sonraki adımlar (insan karar verir)

- checkout v1.1.0 sürümünü geri almayı veya _bundle_discount'taki prices[int(cheapest)] erişimine eksik anahtar koruması ekleyen acil düzeltmeyi insan onayıyla değerlendir.
- Deploy diff'ini inceleyip KeyError: 1'i tetikleyen indirim/sepet kombinasyonunu yeniden üret.
- Düzeltme sonrası dönüşüm, checkout_failed ve sipariş hızının baseline'a dönüşünü izle.
- Alarmın hangi metrikle tetiklendiğini doğrula; trafik tabanlı alarm ise eşiğin gözden geçirilmesini öner.
- Benzer deploy'lar için checkout hata oranı üzerine deploy-sonrası otomatik kontrol (canary/health check) önerisi hazırla.

## Kanıtlar

| evidence_id | Kaynak | Durum | Özet |
|---|---|---|---|
| E01 | loki | ok | Nginx istek hızı: son 2 dk 375.5/dk, baseline 360.0/dk (1.0x) |
| E02 | loki | ok | Nginx durum payları son 2 dk: 2xx %92.7, 3xx %7.1, 5xx %0.3; baseline: 2xx %92.1, 3xx %7.9 |
| E03 | loki | ok | Farklı istemci IP'si son 2 dk 193, baseline (7 dk) 628; son 2 dk en yoğunlar: client-1 %1.2, client-2 %1.2, client-3 %1.2; baseline'da en yoğun IP'nin payı %0.4 |
| E04 | loki | ok | client-1 son 2 dk: 9 istek (home 1, cart 2, cart_add 2, product 4); 429 0; farklı oturum çerezi 1; çerezsiz istek payı %11.1 |
| E05 | loki | ok | client-2 son 2 dk: 9 istek (home 1, cart 2, cart_add 2, product 4); 429 0; farklı oturum çerezi 1; çerezsiz istek payı %11.1 |
| E06 | loki | ok | Son 2 dk 429 toplamı 0; en çok 429 alanlar: yok |
| E07 | loki | ok | Sunulan (429 olmayan) istekler, dakika başı. Son 2 dk: home 90.0, product 229.0, cart_add 26.5, checkout_ok 2.5, checkout_failed 1.0, dönüşüm 0.0278. Baseline: home 89.9, product 209.7, cart_add 28.4, checkout_ok 3.6, checkout_failed 0, dönüşüm 0.04 |
| E08 | prometheus | ok | Sipariş/dk (shop_orders_total): son 2 dk 2.1, baseline 3.5; son 2 dk ödemeler {'approved': 4.4} |
| E09 | loki | ok | Yakalanmamış uygulama hataları son 2 dk: frontend HTTPStatusError 2, checkout KeyError 2; baseline: yok |
| E10 | prometheus | ok | frontend p95 gecikme: son 2 dk 73.3 ms, baseline 71.9 ms |
| E11 | tempo | ok | Tempo son 2 dk hatalı trace: 2; kök işlemler: frontend POST /checkout 2 |
| E12 | grafana | ok | Penceredeki deploy marker'ları: checkout v1.1.0 alarmdan 106 sn önce |
| E13 | campaigns.json | ok | Kampanya takvimi (pencereyle örtüşen): yok |

## İstemci takma adları

LLM'e yalnız takma adlar gitti.

- client-1: 78.173.20.122
- client-2: 85.96.59.5
- client-3: 78.160.30.127

## Agent metadata

- Model: openrouter/deepseek/deepseek-v4.1-flash-1017
- Telemetri sorgusu: 46, LLM çağrısı: 1
- Token: 2974 girdi, 3018 çıktı; maliyet: bilinmiyor
- Süre: toplama 7.2 sn, LLM 14.7 sn, toplam 21.9 sn
- Atıf geçerliliği: %100

## Geçersiz atıflar

Var olmayan, erişilemeyen ya da boş evidence_id'ye dayandığı için rapordan çıkarılan iddialar:

- yok
