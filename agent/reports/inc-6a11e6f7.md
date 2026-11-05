# inc-6a11e6f7: Meşru kampanya (legit_campaign), güven orta

**Karar:** Trafik artışı alarmdan 120 sn önce başlayan ve 5x beklenen Kasım Fırsatları kampanyasıyla örtüşüyor; 429 ve gecikme kapasite etkisi gibi görünüyor, siparişler artıyor ve saldırıya özgü hata/iz yok. [E13, E01, E02, E08, E09, E11, E12]

Pencere: 2026-11-05T13:37:45.842845+00:00 → 2026-11-05T13:49:45.842845+00:00 (alarm)

## Etki

- Sipariş/dk 12.0 ile baseline 4.7'nin üzerinde; ödemelerde approved 22.9 görülüyor, yani kampanya satış üretiyor. [E08]
- Dönüşüm 0.0282'e düşmüş; baseline 0.0523 ve kampanya beklentisi 0.05 altında, kısmen 429 ve kapasite etkisi olabilir. [E07, E13, E02]
- Son 2 dakikada 429 oranı %10.1 ve frontend p95 gecikme 207.0 ms; baseline 70.4 ms, kullanıcı deneyimi ve checkout akışı yavaşlamış olabilir. [E02, E10]

## Zaman çizelgesi

- Kasım Fırsatları kampanyası alarmdan 120 sn önce başladı ve alarm anında aktifti; beklenen trafik çarpanı 5x, beklenen dönüşüm 0.05. [E13]
- Son 2 dakikada Nginx istek hızı 1465.5/dk oldu; baseline 363.4/dk, yani 4.0x artış. [E01]
- Aynı son 2 dakikada durum payları 2xx %85.1, 3xx %4.8, 429 %10.1; baseline 2xx %92.4 ve 3xx %7.6. [E02]
- Son 2 dakikada sipariş/dk 12.0 ve ödemelerde approved 22.9 kaydedildi; baseline sipariş 4.7/dk. [E08]

## Hipotezler

- Elenen: attack: Kampanya penceresiyle tam örtüşme, 2xx oranının yüksek kalması, sipariş ve ödemelerin artması, uygulama hatası ve hatalı trace olmaması saldırıyı desteklemiyor. Ayrıca V1 saldırı sınıfı tek IP L7 flood iken burada iki istemci öne çıkıyor; yine de client-1/client-2 yoğunluğu tek başına yeterli saldırı kanıtı değil. [E13, E01, E02, E08, E09, E11, E03]
- Desteklenen: legit_campaign: Alarmdan 120 sn önce başlayan ve alarmda aktif olan kampanya 5x trafik bekliyor; gözlenen 4.0x artış buna yakın. Siparişler ve ödemeler artmış, 429'lar kapasite/rate limit etkisiyle açıklanabilir, deploy veya uygulama hatası yok. [E13, E01, E02, E07, E08, E09, E11, E12]
- Elenen: ops_failure: Pencerede deploy marker'ı yok, yakalanmamış uygulama hatası yok ve Tempo'da hatalı trace yok. Gecikme artışı daha çok trafik hacmi ve 429 ile uyumlu. [E12, E09, E11, E10, E02]
- Elenen: unknown: Kampanya takvimi, trafik artışı, siparişler ve hata/deploy yokluğu birlikte bir sınıfa işaret ediyor; çekimser kalmayı gerektirecek kadar çelişki yok. Ancak iki istemci yoğunluğu güveni medium seviyesinde tutuyor. [E13, E01, E08, E03, E09, E12]

## Beni ne yanıltabilir?

- client-1 ve client-2'nin son 2 dakikadaki trafiğin yaklaşık %74.4'ünü üretmesi bot veya L7 flood gibi görünebilir; NAT/proxy veya kampanya yönlendirmesi de olabilir. [E03, E04, E05]
- Her iki istemcide çerezsiz istek payının yaklaşık %33 olması otomasyon şüphesi yaratabilir; fakat tek başına saldırı kanıtı değildir. [E04, E05]
- Dönüşümün beklenen 0.05 altında 0.0282 olması ve %10.1 429 oranı saldırı veya operasyonel sorun izlenimi verebilir; kampanya yükü ve rate limit ile de uyumludur. [E07, E13, E02]
- p95 gecikmenin 70.4 ms'den 207.0 ms'ye çıkması kötü deploy gibi düşünülebilir; ancak deploy marker'ı ve hata izi yok. [E10, E12, E09, E11]

## Eksik kanıt

- client-1 ve client-2 IP'lerinin NAT/proxy mi yoksa bot/otomasyon mu olduğunu gösteren user-agent, ASN, coğrafya ve oturum davranışı verisi
- Kampanya kaynaklı beklenen trafik dağılımı ve bu iki istemcinin kampanya yönlendirmesiyle ilişkisi
- 429 alan ve almayan kullanıcıların checkout başarı oranı karşılaştırması
- Ödeme approved metriklerinin gerçek kullanıcı mı yoksa test/otomasyon kaynaklı mı olduğunu gösteren ayrım
- Rate limit kuralı, kapasite eşiği ve kampanya için önceden planlanan ölçeklendirme bilgisi

## Sonraki adımlar (insan karar verir)

- Kampanya ekibiyle Kasım Fırsatları başlangıç zamanı ve beklenen 5x trafik profili teyit edilmeli.
- client-1 ve client-2 için IP/ASN, user-agent, çerez ve oturum davranışı incelenmeli; NAT/proxy olup olmadığı doğrulanmalı.
- 429 oranı ve checkout funnel'ı kampanya süresince izlenmeli; kapasite artırımı veya rate limit gevşetmesi insan onayıyla değerlendirilmeli.
- Sipariş ve ödeme onaylarının gerçek kullanıcı kaynaklı olduğu örneklemle doğrulanmalı.
- Trafik artışı kampanya dışına taşarsa veya tek IP L7 flood kriterleri oluşursa alarm yeniden sınıflandırılmalı.

## Kanıtlar

| evidence_id | Kaynak | Durum | Özet |
|---|---|---|---|
| E01 | loki | ok | Nginx istek hızı: son 2 dk 1465.5/dk, baseline 363.4/dk (4.0x) |
| E02 | loki | ok | Nginx durum payları son 2 dk: 2xx %85.1, 3xx %4.8, 429 %10.1; baseline: 2xx %92.4, 3xx %7.6 |
| E03 | loki | ok | Farklı istemci IP'si son 2 dk 192, baseline (7 dk) 629; son 2 dk en yoğunlar: client-1 %37.3, client-2 %37.1, client-3 %0.3; baseline'da en yoğun IP'nin payı %0.4 |
| E04 | loki | ok | client-1 son 2 dk: 1092 istek (home 353, cart 51, cart_add 66, checkout 8, product 614); 429 151; farklı oturum çerezi 248; çerezsiz istek payı %32.3 |
| E05 | loki | ok | client-2 son 2 dk: 1086 istek (home 360, cart 38, cart_add 46, checkout 5, product 637); 429 145; farklı oturum çerezi 254; çerezsiz istek payı %33.1 |
| E06 | loki | ok | Son 2 dk 429 toplamı 296; en çok 429 alanlar: client-1 151 (%51.0), client-2 145 (%49.0) |
| E07 | loki | ok | Sunulan (429 olmayan) istekler, dakika başı. Son 2 dk: home 408.5, product 764.0, cart_add 71.0, checkout_ok 11.5, checkout_failed 0, dönüşüm 0.0282. Baseline: home 89.9, product 213.4, cart_add 27.7, checkout_ok 4.7, checkout_failed 0, dönüşüm 0.0523 |
| E08 | prometheus | ok | Sipariş/dk (shop_orders_total): son 2 dk 12.0, baseline 4.7; son 2 dk ödemeler {'approved': 22.9} |
| E09 | loki | ok | Yakalanmamış uygulama hataları son 2 dk: yok; baseline: yok |
| E10 | prometheus | ok | frontend p95 gecikme: son 2 dk 207.0 ms, baseline 70.4 ms |
| E11 | tempo | ok | Tempo son 2 dk hatalı trace: 0; kök işlemler: yok |
| E12 | grafana | ok | Penceredeki deploy marker'ları: yok |
| E13 | campaigns.json | ok | Kampanya takvimi (pencereyle örtüşen): Kasım Fırsatları (alarmdan 120 sn önce başladı, alarmda aktif, beklenen trafik 5x, beklenen dönüşüm 0.05) |

## İstemci takma adları

LLM'e yalnız takma adlar gitti.

- client-1: 176.40.12.7
- client-2: 176.40.12.19
- client-3: 78.160.183.134

## Agent metadata

- Model: openrouter/deepseek/deepseek-v4.1-flash-1017
- Telemetri sorgusu: 46, LLM çağrısı: 1
- Token: 2876 girdi, 6299 çıktı; maliyet: bilinmiyor
- Süre: toplama 7.0 sn, LLM 35.0 sn, toplam 42.0 sn
- Atıf geçerliliği: %100

## Geçersiz atıflar

Var olmayan, erişilemeyen ya da boş evidence_id'ye dayandığı için rapordan çıkarılan iddialar:

- yok
