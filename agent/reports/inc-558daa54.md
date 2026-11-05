# inc-558daa54: Saldırı (attack), güven yüksek

**Karar:** Tek bir istemcinin (client-1) tüm istekleri ana sayfaya yönelik, çerezsiz ve oturumsuz L7 flood'u; 429'ların %100'ü bu istemciden, bu nedenle karar 'attack'. [E01, E02, E03, E04, E06]

Pencere: 2026-11-05T14:08:08.272818+00:00 → 2026-11-05T14:20:08.272818+00:00 (alarm)

## Etki

- İstek hızı baseline'ın 10.3 katına çıktı (355/dk → 3664/dk) ve isteklerin %76.3'ü 429 ile reddedildi; kapasitenin büyük kısmı tek istemcinin selini emmek için harcandı. [E01, E02, E06]
- Sunulan ana sayfa trafiği 89.9/dk'dan 577.5/dk'ya çıktı; dönüşüm oranı %3.67'den %1.04'e düştü, ancak bu düşüş gerçek bir satış kaybından çok selin payda etkisinden kaynaklanıyor. [E07]
- Sipariş hızı 3.4/dk'dan 6.0/dk'ya, onaylı ödeme 12/dk'ya çıktı; yani iş sonucu tarafında belirgin bir kayıp görünmüyor. [E08]
- Frontend p95 gecikme 72.1 ms'den 103.7 ms'ye yükseldi; hafif bir gecikme etkisi var, uygulama hatası veya hatalı trace yok. [E10, E09, E11]

## Zaman çizelgesi

- Baseline döneminde istek hızı 355/dk ve trafik dağınık; en yoğun tek IP'nin payı yalnızca %0.4. [E01, E03]
- Alarmdan önceki son 2 dakikada istek hızı 3664/dk'ya fırladı; farklı istemci sayısı 629'dan 195'e düştü, yani trafik dağınıklıktan tek kaynağa yoğunlaştı. [E01, E03]
- client-1 son 2 dakikada 6567 istek attı (trafiğin %89.6'sı), tamamı home sayfasına, %100 çerezsiz ve 0 oturumla; bu istemcinin 5592 isteği 429 aldı. [E03, E04]
- Son 2 dakikadaki 5592 adet 429'un %100'ü client-1'e ait; client-2 gibi normal istemciler oturum çerezli ve çerezli/çerezsiz karışık normal akışta (home, product, cart_add, checkout) ilerliyor. [E06, E05]
- Pencerede deploy marker'ı ve kampanya kaydı yok; yakalanmamış uygulama hatası ve hatalı trace de yok. [E12, E13, E09, E11]

## Hipotezler

- Desteklenen: attack: Trafiğin %89.6'sı tek istemciden, tamamı ana sayfaya, %100 çerezsiz ve 0 oturumla geliyor; baseline'da en yoğun IP payı %0.4 iken bu, tek kaynaklı bir L7 flood'a işaret ediyor. 429'ların %100'ünün bu istemciden olması da rate limit'in hedefini doğruluyor. [E03, E04, E06, E02]
- Elenen: legit_campaign: Kampanya takviminde pencereyle örtüşen kayıt yok; ayrıca meşru kampanya trafiği tek IP'de toplanmaz, oturum çerezi taşır ve ana sayfa dışındaki ürün/sepet adımlarına yayılır. client-1'in 0 oturumu ve %100 çerezsizliği kampanya profiliyle çelişiyor. [E13, E04, E05, E03]
- Elenen: ops_failure: Pencerede deploy marker'ı yok, yakalanmamış uygulama hatası yok ve hatalı trace yok; 429'lar arıza değil, rate limit'in devreye girmesidir. Sipariş ve onaylı ödeme sayıları artmış durumda, bu da bir arıza tablosuyla uyuşmuyor. [E12, E09, E11, E08]
- Elenen: unknown: İstemci dağılımı, oturum/çerez profili ve 429 dağılımı tek kaynaklı flood tablosunu net biçimde çiziyor; sınıflar arasında kararsızlık gerektirecek bir kanıt boşluğu yok. [E03, E04, E06]

## Beni ne yanıltabilir?

- Sipariş ve onaylı ödeme sayılarının artması, trafiğin tamamı meşruymuş gibi okunabilir; oysa bu artış selin dışında kalan normal istemcilerden geliyor olabilir. [E08, E07]
- 429 oranının yüksek olması, arıza veya rate limit yanlış yapılandırması izlenimi verebilir; ancak 429'ların tamamı tek istemcide toplanmış. [E02, E06]
- client-1 dışındaki istemcilerin sayısının baseline'a göre düşmesi (629 → 195), gerçek kullanıcı kaybı gibi görünebilir; kısa 2 dakikalık pencere ve selin örneklemi domine etmesi bu karşılaştırmayı yanıltabilir. [E03]
- Tek IP'lik flood, IP rotasyonlu dağıtık bir denemenin yalnızca ilk ayağı olabilir; engelleme sonrası yeni IP'ler görünmezse karar eksik kalır. [E03, E04]

## Eksik kanıt

- client-1'in tam IP'si, ASN/coğrafi bilgisi ve user-agent imzası
- client-1'in home dışında denediği yol/protokol detayı ve istek zamanlaması (sabit aralık mı, burst mü)
- Daha uzun pencerede (alarm sonrası 10-30 dk) yeni istemcilerin belirip belirmediği
- WAF/edge katmanındaki bot ve rate limit kural logları
- Aynı saatlerdeki geçmiş günlerin baseline'ı (mevsimsel/saatlik normalin doğrulanması)
- 429 alan isteklerin backend'e hiç ulaşıp ulaşmadığına dair doğrulama

## Sonraki adımlar (insan karar verir)

- client-1'i edge/WAF katmanında geçici olarak blokla veya sıkı throttle uygula; uygulama katmanına dokunma.
- Engelleme sonrası 10-15 dakika izle: istek hızı baseline'a dönüyor mu, yeni istemciler öne çıkıyor mu kontrol et.
- client-1'in IP, ASN ve user-agent imzasını kayıt altına al; benzer desenli diğer istemcileri geriye dönük tara.
- Sipariş ve onaylı ödeme metriklerinin sel sonrası da korunduğunu doğrula; dönüşüm oranını sel sonrası normalize edilmiş trafikle yeniden hesapla.
- Rate limit eşiklerinin ana sayfa için bu senaryoda yeterli olduğunu gözden geçir; gerekiyorsa insan onayıyla sıkılaştırma öner.

## Kanıtlar

| evidence_id | Kaynak | Durum | Özet |
|---|---|---|---|
| E01 | loki | ok | Nginx istek hızı: son 2 dk 3664.0/dk, baseline 355.0/dk (10.3x) |
| E02 | loki | ok | Nginx durum payları son 2 dk: 2xx %22.8, 3xx %0.8, 429 %76.3; baseline: 2xx %92.9, 3xx %7.1 |
| E03 | loki | ok | Farklı istemci IP'si son 2 dk 195, baseline (7 dk) 629; son 2 dk en yoğunlar: client-1 %89.6, client-2 %0.1, client-3 %0.1; baseline'da en yoğun IP'nin payı %0.4 |
| E04 | loki | ok | client-1 son 2 dk: 6567 istek (home 6567); 429 5592; farklı oturum çerezi 0; çerezsiz istek payı %100.0 |
| E05 | loki | ok | client-2 son 2 dk: 9 istek (home 1, cart 2, cart_add 2, checkout 1, product 3); 429 0; farklı oturum çerezi 1; çerezsiz istek payı %11.1 |
| E06 | loki | ok | Son 2 dk 429 toplamı 5592; en çok 429 alanlar: client-1 5592 (%100.0) |
| E07 | loki | ok | Sunulan (429 olmayan) istekler, dakika başı. Son 2 dk: home 577.5, product 222.5, cart_add 31.0, checkout_ok 6.0, checkout_failed 0, dönüşüm 0.0104. Baseline: home 89.9, product 211.3, cart_add 25.3, checkout_ok 3.3, checkout_failed 0, dönüşüm 0.0367 |
| E08 | prometheus | ok | Sipariş/dk (shop_orders_total): son 2 dk 6.0, baseline 3.4; son 2 dk ödemeler {'approved': 12.0} |
| E09 | loki | ok | Yakalanmamış uygulama hataları son 2 dk: yok; baseline: yok |
| E10 | prometheus | ok | frontend p95 gecikme: son 2 dk 103.7 ms, baseline 72.1 ms |
| E11 | tempo | ok | Tempo son 2 dk hatalı trace: 0; kök işlemler: yok |
| E12 | grafana | ok | Penceredeki deploy marker'ları: yok |
| E13 | campaigns.json | ok | Kampanya takvimi (pencereyle örtüşen): yok |

## İstemci takma adları

LLM'e yalnız takma adlar gitti.

- client-1: 45.142.120.18
- client-2: 212.253.66.31
- client-3: 176.88.248.162

## Agent metadata

- Model: openrouter/deepseek/deepseek-v4.1-flash-1017
- Telemetri sorgusu: 46, LLM çağrısı: 1
- Token: 2682 girdi, 3080 çıktı; maliyet: bilinmiyor
- Süre: toplama 9.3 sn, LLM 13.6 sn, toplam 22.9 sn
- Atıf geçerliliği: %100

## Geçersiz atıflar

Var olmayan, erişilemeyen ya da boş evidence_id'ye dayandığı için rapordan çıkarılan iddialar:

- yok
