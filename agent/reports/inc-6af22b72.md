# inc-6af22b72: Saldırı (attack), güven yüksek

**Karar:** V1 kapsamında tek istemci client-1'den gelen, home sayfasına yönelik, çerezsiz ve oturumsuz L7 flood; 429'ların tamamı client-1 kaynaklı. [E01, E02, E03, E04, E06]

Pencere: 2026-11-05T11:03:28.451574+00:00 → 2026-11-05T11:15:28.451574+00:00 (alarm)

## Etki

- İstek hızı baseline'a göre 10.1x artarken 429 oranı %76.5'e çıkmış, 2xx payı %22.7'ye gerilemiş; dönüşüm 0.0601'den 0.0078'e düşmüş. [E01, E02, E07]
- Sipariş/dk 4.9 ile baseline 5.3 civarında; checkout_ok 4.5 ile baseline 5.4’e yakın, yani ciddi sipariş kesintisi görünmüyor. [E07, E08]
- Uygulama hataları ve hatalı trace yok; p95 gecikme 74 ms ile baseline 81 ms altında, operasyonel sağlık normal görünüyor. [E09, E10, E11]

## Zaman çizelgesi

- Pencere başlangıcından alarmdan 5 dk öncesine kadar baseline: 361.9 istek/dk, 2xx %91.7, en yoğun IP payı %0.4. [E01, E02, E03]
- Alarmdan önceki son 2 dakikada istek hızı 3648.0/dk ile 10.1x artmış; 429 oranı %76.5 olmuş. [E01, E02]
- Aynı dönemde client-1 6558 istek atmış; tamamı home, 5584'ü 429 almış, 0 oturum ve %100 çerezsiz istek var. [E04, E06]
- Son 2 dakikada sipariş/dk 4.9, uygulama hatası yok, hatalı trace yok, p95 74 ms. [E08, E09, E10, E11]

## Hipotezler

- Desteklenen: attack: client-1 trafiğin %89.9'unu oluşturuyor; 6558 isteğin tamamı home, 5584'ü 429, oturum yok ve çerezsiz pay %100. Bu tablo tek IP'den L7 flood ile uyumlu. [E01, E02, E03, E04, E06]
- Elenen: legit_campaign: Kampanya takvimi boş; ayrıca client-1 tek IP, oturumsuz ve yalnızca home isteğiyle legit kampanya davranışından ayrışıyor, dönüşüm de düşük. [E03, E04, E07, E13]
- Elenen: ops_failure: Pencerede deploy yok, uygulama hatası yok, hatalı trace yok ve gecikme normal; operasyonel arıza sinyali yok. [E09, E10, E11, E12]
- Elenen: unknown: Kanıtlar tek bir istemcinin aşırı home trafiğine ve 429 yoğunluğuna tutarlı biçimde işaret ediyor; sınıflar arasında kararsızlık gerektiren çelişki yok. [E01, E02, E03, E04, E06]

## Beni ne yanıltabilir?

- client-1 bir NAT/proxy veya izleme sistemi olabilir; tek IP'nin çok sayıda gerçek kullanıcıyı temsil etmesi ihtimali user-agent/ASN görülmeden tamamen dışlanamaz. [E03, E04]
- Kampanya takvimi boş olsa da kayıt dışı kampanya olabilir; ancak oturumsuz ve sadece home trafiği bu ihtimali zayıflatıyor. [E04, E13]
- 429 oranı yüksek olduğu için gerçek kullanıcı trafiği de bastırılmış olabilir; 2xx düşüşü saldırı dışı bir nedenle karışabilir. [E02, E07]

## Eksik kanıt

- client-1 için ASN, user-agent, ters DNS ve IP itibarı/geo bilgisi
- WAF/rate-limit kuralı ve eşik değişiklik geçmişi
- client-1 isteklerinin path, query, method ve payload ayrıntıları
- Kampanya takvimi dışındaki pazarlama/duyuru kayıtları
- 429'ların gerçek kullanıcıları etkileyip etkilemediğine dair oturum bazlı etki analizi

## Sonraki adımlar (insan karar verir)

- client-1'in ASN, user-agent, ters DNS ve IP itibarı kontrol edilerek bot/proxy/NAT ayrımı yapılmalı.
- Kampanya ve duyuru kayıtları ikinci bir kaynaktan doğrulanmalı.
- 429'ların gerçek kullanıcıları etkileyip etkilemediği normal akıştaki istemcilerle karşılaştırılmalı.
- Gerekirse client-1 için rate-limit/block uygulaması insan onayıyla değerlendirilmeli; sonrasında sipariş, dönüşüm ve 429 oranı izlenmeli.
- Deploy/config değişikliği olmadığı teyit edilerek operasyonel arıza ihtimali kapatılmalı.

## Kanıtlar

| evidence_id | Kaynak | Durum | Özet |
|---|---|---|---|
| E01 | loki | ok | Nginx istek hızı: son 2 dk 3648.0/dk, baseline 361.9/dk (10.1x) |
| E02 | loki | ok | Nginx durum payları son 2 dk: 2xx %22.7, 3xx %0.7, 429 %76.5; baseline: 2xx %91.7, 3xx %8.3 |
| E03 | loki | ok | Farklı istemci IP'si son 2 dk 191, baseline (7 dk) 629; son 2 dk en yoğunlar: client-1 %89.9, client-2 %0.1, client-3 %0.1; baseline'da en yoğun IP'nin payı %0.4 |
| E04 | loki | ok | client-1 son 2 dk: 6558 istek (home 6558); 429 5584; farklı oturum çerezi 0; çerezsiz istek payı %100.0 |
| E05 | loki | ok | client-2 son 2 dk: 10 istek (home 1, cart 2, cart_add 2, checkout 1, product 4); 429 0; farklı oturum çerezi 1; çerezsiz istek payı %10.0 |
| E06 | loki | ok | Son 2 dk 429 toplamı 5584; en çok 429 alanlar: client-1 5584 (%100.0) |
| E07 | loki | ok | Sunulan (429 olmayan) istekler, dakika başı. Son 2 dk: home 577.0, product 221.5, cart_add 26.5, checkout_ok 4.5, checkout_failed 0, dönüşüm 0.0078. Baseline: home 89.9, product 206.9, cart_add 29.9, checkout_ok 5.4, checkout_failed 0, dönüşüm 0.0601 |
| E08 | prometheus | ok | Sipariş/dk (shop_orders_total): son 2 dk 4.9, baseline 5.3; son 2 dk ödemeler {'approved': 9.8} |
| E09 | loki | ok | Yakalanmamış uygulama hataları son 2 dk: yok; baseline: yok |
| E10 | prometheus | ok | frontend p95 gecikme: son 2 dk 74.0 ms, baseline 81.0 ms |
| E11 | tempo | ok | Tempo son 2 dk hatalı trace: 0; kök işlemler: yok |
| E12 | grafana | ok | Penceredeki deploy marker'ları: yok |
| E13 | campaigns.json | ok | Kampanya takvimi (pencereyle örtüşen): yok |

## İstemci takma adları

LLM'e yalnız takma adlar gitti.

- client-1: 45.142.120.18
- client-2: 176.88.181.110
- client-3: 176.88.24.91

## Agent metadata

- Model: openrouter/deepseek/deepseek-v4.1-flash-1017
- Telemetri sorgusu: 46, LLM çağrısı: 1
- Token: 2683 girdi, 4233 çıktı; maliyet: bilinmiyor
- Süre: toplama 8.4 sn, LLM 20.3 sn, toplam 28.7 sn
- Atıf geçerliliği: %100

## Geçersiz atıflar

Var olmayan, erişilemeyen ya da boş evidence_id'ye dayandığı için rapordan çıkarılan iddialar:

- yok
