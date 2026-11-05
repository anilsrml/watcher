# inc-3d655ccc: Saldırı (attack), güven yüksek

**Karar:** Kanıtlar, client-1 kaynaklı tek istemcili L7 home flood'u ve buna bağlı 429 birikimini gösteriyor; olay attack olarak sınıflanır. [E01, E02, E03, E04, E06, E12, E13]

Pencere: 2026-11-05T16:25:42.930668+00:00 → 2026-11-05T16:37:42.930668+00:00 (alarm)

## Etki

- İstek hızı baseline'a göre 10.3x artmış; toplam trafiğin %89.4'ü client-1'den gelmiş ve 429'ların %100'ü yine client-1'e ait. [E01, E03, E06]
- Son 2 dakikada 429 oranı %76.1'e çıkmış, 2xx oranı %93.0'dan %23.0'a gerilemiş; bu, rate limit'in bot trafiğini büyük ölçüde absorbe ettiğini gösteriyor. [E02, E06]
- Dönüşüm oranı 0.0434'ten 0.0087'ye düşmüş görünüyor; ancak sipariş/dk 5.4 ile baseline 3.9'un üzerinde ve checkout_ok 5.0 ile baseline 3.9'un üzerinde, bu nedenle dönüşüm düşüşü en azından kısmen bot kaynaklı home trafiğinin paydayı şişirmesiyle uyumlu. [E07, E08]
- frontend p95 gecikme 70.7 ms'den 97.3 ms'ye çıkmış; belirgin bir kesinti veya hata patlaması görünmüyor. [E10, E09, E11]

## Zaman çizelgesi

- Baseline döneminde istek hızı 355.9/dk, 2xx oranı %93.0 ve en yoğun tek istemci payı %0.4 seviyesinde. [E01, E02, E03]
- Alarmdan önceki son 2 dakikada istek hızı 3653.0/dk'ya çıkarak baseline'ın 10.3 katına ulaşmış. [E01]
- client-1 son 2 dakikada 6533 istek göndermiş; tamamı home sayfasına, %100 çerezsiz ve 0 farklı oturum çereziyle gelmiş. [E04]
- Aynı dönemde toplam 5563 429 yanıtı oluşmuş ve tamamı client-1'e ait; genel 429 oranı %76.1. [E02, E06]
- client-2 gibi düşük hacimli istemcilerde 10 istek, 1 oturum ve home/product/cart/checkout akışı görülüyor; 429 almamış. [E05]
- Pencerede deploy marker'ı ve örtüşen kampanya kaydı yok; uygulama hatası ve hatalı trace de yok. [E09, E11, E12, E13]

## Hipotezler

- Desteklenen: attack: Tek istemci client-1, son 2 dakikadaki trafiğin %89.4'ünü üretmiş; yalnız home sayfasına 6533 istek atmış, %100 çerezsiz ve 0 oturumla gelmiş, 429'ların %100'ünü almış. Bu tablo, V1 kapsamında tek IP'den gelen L7 flood ile uyumlu. [E01, E02, E03, E04, E06]
- Elenen: legit_campaign: Kampanya takviminde pencereyle örtüşen kayıt yok. Ayrıca client-1 trafiği kampanya kullanıcısı gibi home/product/cart/checkout akışı izlemiyor; tamamen home, çerezsiz ve oturumsuz. client-2'de görülen gerçek alışveriş akışı düşük hacimli ve 429 almamış. [E04, E05, E13]
- Elenen: ops_failure: Pencerede deploy marker'ı yok, yakalanmamış uygulama hatası yok ve Tempo'da hatalı trace yok. Baskın durum 5xx değil, client-1'e ait 429'lar; bu operasyonel arızadan çok rate limit etkisine işaret ediyor. [E02, E06, E09, E11, E12]
- Elenen: unknown: Trafik artışının kaynağı, istemci konsantrasyonu, çerezsiz/oturumsuz erişim paterni ve 429 dağılımı birlikte değerlendirildiğinde sınıflandırma için yeterli kanıt var; çekimser kalmayı gerektiren bir belirsizlik görünmüyor. [E01, E02, E03, E04, E06]

## Beni ne yanıltabilir?

- Tek istemci IP'si NAT/proxy arkasında çok sayıda meşru kullanıcıyı temsil edebilir; ancak %100 çerezsiz ve 0 oturum bu ihtimali zayıflatıyor. [E03, E04]
- Kampanya takvimi boş olsa da kayıt dışı bir kampanya veya duyuru trafiği olabilir; fakat client-1'in yalnız home'a gitmesi ve oturum üretmemesi kampanya trafiğiyle uyumsuz. [E04, E13]
- Yüksek 429 oranı bir altyapı arızası gibi görünebilir; oysa 429'ların tamamı client-1'e ait ve uygulama hatası/hatalı trace yok. [E02, E06, E09, E11]
- Dönüşüm oranındaki düşüş gerçek kullanıcı kaybı gibi yorumlanabilir; ancak sipariş ve checkout_ok baseline üzerinde olduğu için bu düşüş botun home istekleriyle paydayı şişirmesinden kaynaklanıyor olabilir. [E07, E08]

## Eksik kanıt

- client-1 için user-agent, ASN/ISP, referrer, TLS/JA3 parmak izi ve istek parametreleri.
- WAF/bot yönetimi ve rate-limit yapılandırmasının ayrıntıları.
- client-1'in 429 almayan isteklerinin hangi durum kodlarını ve sayfaları gördüğü.
- NAT/proxy arkasında meşru kullanıcı olup olmadığını gösterecek oturum veya kullanıcı bazlı kanıt.
- Kayıt dışı kampanya/duyuru olup olmadığına dair kampanya ekibi teyidi.

## Sonraki adımlar (insan karar verir)

- İnsan incelemesi için client-1'in IP/ASN, user-agent ve istek parametreleri çıkarılmalı.
- Rate limit'in NAT/proxy arkasındaki meşru kullanıcıları etkileyip etkilemediği kontrol edilmeli.
- Bot/insan ayrımı için WAF veya JS challenge davranışı doğrulanmalı; kalıcı kural değişikliği insan onayıyla yapılmalı.
- Kampanya ekibiyle pencerede kayıt dışı kampanya olup olmadığı teyit edilmeli.
- Dönüşüm panosunda bot kaynaklı home trafiğinin paydayı bozup bozmadığı ayrıştırılmalı.

## Kanıtlar

| evidence_id | Kaynak | Durum | Özet |
|---|---|---|---|
| E01 | loki | ok | Nginx istek hızı: son 2 dk 3653.0/dk, baseline 355.9/dk (10.3x) |
| E02 | loki | ok | Nginx durum payları son 2 dk: 2xx %23.0, 3xx %0.9, 429 %76.1; baseline: 2xx %93.0, 3xx %7.0 |
| E03 | loki | ok | Farklı istemci IP'si son 2 dk 192, baseline (7 dk) 629; son 2 dk en yoğunlar: client-1 %89.4, client-2 %0.1, client-3 %0.1; baseline'da en yoğun IP'nin payı %0.4 |
| E04 | loki | ok | client-1 son 2 dk: 6533 istek (home 6533); 429 5563; farklı oturum çerezi 0; çerezsiz istek payı %100.0 |
| E05 | loki | ok | client-2 son 2 dk: 10 istek (home 1, cart 2, cart_add 2, checkout 1, product 4); 429 0; farklı oturum çerezi 1; çerezsiz istek payı %10.0 |
| E06 | loki | ok | Son 2 dk 429 toplamı 5563; en çok 429 alanlar: client-1 5563 (%100.0) |
| E07 | loki | ok | Sunulan (429 olmayan) istekler, dakika başı. Son 2 dk: home 575.0, product 228.5, cart_add 31.5, checkout_ok 5.0, checkout_failed 0, dönüşüm 0.0087. Baseline: home 89.9, product 212.1, cart_add 25.0, checkout_ok 3.9, checkout_failed 0, dönüşüm 0.0434 |
| E08 | prometheus | ok | Sipariş/dk (shop_orders_total): son 2 dk 5.4, baseline 3.9; son 2 dk ödemeler {'approved': 10.9} |
| E09 | loki | ok | Yakalanmamış uygulama hataları son 2 dk: yok; baseline: yok |
| E10 | prometheus | ok | frontend p95 gecikme: son 2 dk 97.3 ms, baseline 70.7 ms |
| E11 | tempo | ok | Tempo son 2 dk hatalı trace: 0; kök işlemler: yok |
| E12 | grafana | ok | Penceredeki deploy marker'ları: yok |
| E13 | campaigns.json | ok | Kampanya takvimi (pencereyle örtüşen): yok |

## İstemci takma adları

LLM'e yalnız takma adlar gitti.

- client-1: 45.142.120.18
- client-2: 176.88.17.72
- client-3: 85.96.89.232

## Agent metadata

- Model: openrouter/deepseek/deepseek-v4.1-flash-1017
- Telemetri sorgusu: 46, LLM çağrısı: 1
- Token: 2682 girdi, 4579 çıktı; maliyet: bilinmiyor
- Süre: toplama 8.5 sn, LLM 25.8 sn, toplam 34.4 sn
- Atıf geçerliliği: %100

## Geçersiz atıflar

Var olmayan, erişilemeyen ya da boş evidence_id'ye dayandığı için rapordan çıkarılan iddialar:

- yok
