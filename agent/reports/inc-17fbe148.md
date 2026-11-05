# inc-17fbe148: Meşru kampanya (legit_campaign), güven yüksek

**Karar:** Alarm anında aktif olan 'Flaş Fırsat Saati' kampanyasıyla örtüşen, çok sayıda istemciye yayılmış ve dönüşümü bozmayan ~5x trafik artışı saldırı değil meşru kampanya trafiğidir. [E01, E03, E07, E08, E13]

Pencere: 2026-11-05T10:02:43.045948+00:00 → 2026-11-05T10:14:43.045948+00:00 (alarm)

## Etki

- Sipariş hızı 3.4/dk'dan 16.3/dk'ya (~4.8x) çıktı, onaylı ödeme 34.9/dk; kampanya satışa dönüştü, dönüşüm oranı 0.0367 ile baseline ile aynı kaldı. [E08, E07]
- Frontend p95 gecikme 68.7 ms'den 437.6 ms'ye (~6.4x) yükseldi; hata üretilmese de ödeme akışında gecikme hissedilmiş olabilir. [E10]
- Kampanya beklenen dönüşümü 0.05 iken gözlenen 0.0367; trafik beklendiği kadar iyi dönüşmüyor, bu ciroya etki eder. [E13, E07]
- 429 reddi yok ve hata traceleri boş; yani hız limiti müşteriyi kapıda çevirmiyor. [E06, E11]

## Zaman çizelgesi

- Alarmdan 120 sn önce 'Flaş Fırsat Saati' kampanyası başladı ve alarm anında hâlâ aktif. [E13]
- Nginx istek hızı son 2 dakikada 1716.5/dk'ya, baseline 353.3/dk'nın 4.9 katına çıktı. [E01]
- Sunulan isteklerde funnel orantılı büyüdü: home 449.0/dk, product 1006.0/dk, cart_add 122.5/dk. [E07]
- Sipariş/dk 3.4'ten 16.3'e çıktı, ödemeler 'approved': 34.9/dk. [E08]
- Frontend p95 gecikme 437.6 ms'ye yükseldi (baseline 68.7 ms), buna karşın 429 ve yakalanmamış uygulama hatası yok. [E10, E06, E09]
- Pencere içinde hiç deploy marker'ı yok. [E12]

## Hipotezler

- Elenen: attack: Tek IP'den L7 flood profili yok: son 2 dakikada 909 farklı istemci var ve en yoğun istemci client-1/2/3 payı yalnızca %0.3; baseline'da en yoğun pay %0.4. Durum kodları değişmedi (2xx %92.9), 429 toplamı 0, hatalı trace yok. Yük artışı istemci çeşitliliğine yayılmış, tek kaynaklı değil. [E03, E04, E05, E02, E06, E11]
- Desteklenen: legit_campaign: Kampanya alarmdan 120 sn önce başladı, beklenen çarpanı 5x ve gözlenen artış 4.9x; funnel kalemleri (home 5.0x, product 4.8x, cart_add 4.8x, checkout_ok 5x) orantılı büyüdü, sipariş 4.8x arttı, dönüşüm baseline ile aynı (0.0367). Zamanlama, büyüklük ve oran tutarlılığı birlikte meşru kampanyayı destekliyor. [E13, E01, E07, E08, E06]
- Elenen: ops_failure: Pencerede deploy marker'ı yok, yakalanmamış uygulama hatası ve hatalı trace yok, durum kodu dağılımı baseline ile aynı. Gecikme artışı hata üretmeden yalnızca hacimle birlikte geldiği için kötü deploy/konfigürasyon arızası tablosuna uymuyor. [E12, E09, E11, E02, E10]
- Elenen: unknown: Kampanya takvimi, trafik çarpanı ve funnel oranları birbirini doğrular nitelikte; sınıflar arasında kararsızlık yaratacak çelişki kalmıyor (yalnızca kapasite/gecikme tarafı izlenmeli). [E13, E01, E07, E08]

## Beni ne yanıltabilir?

- 4.9x trafik artışı tek başına flood gibi görünebilir; ayrımı yapan istemci dağılımı ve durum kodu/429 verisidir. [E01, E03, E06]
- p95 gecikmenin 68.7 ms'den 437.6 ms'ye çıkması 'kötü deploy' şüphesi doğurabilir; ancak deploy marker'ı ve hata kanıtı yok. [E10, E12, E09, E11]
- Dağıtık istemci tablosu (909 farklı IP) botnet ile de karıştırılabilir; fakat çerez/oturum başına 1 oturum ve düşük çerezsiz pay (%10) normal kullanıcı davranışına uyuyor. [E03, E04, E05]
- Kampanya beklenen dönüşümü 0.05 iken gözlenen 0.0367; kampanya etkisinin bir kısmı gerçekleşmemiş olabilir, bu 'kampanya değil' yanılgısına yol açmamalı. [E13, E07]

## Eksik kanıt

- Veritabanı, cache ve uygulama sunucusu doygunluk (CPU/bellek/bağlantı havuzu) metrikleri
- Kampanya sayfası/URL bazlı trafik atfı ve kampanya kaynağı (e-posta, push, reklam) kırılımı
- Saniye/dakika çözünürlüklü trafik yükselme eğrisi (kampanya başlangıcı 10:00:43 ile uyum kontrolü)
- Gerçek kullanıcı izleme (RUM) ve checkout adım süreleri; gecikmenin dönüşüme etkisi
- Kapasite eşikleri ve hız limiti yapılandırması (429'un neden hiç tetiklenmediği)
- Ödeme sağlayıcı tarafında onay oranı ve gecikmesi

## Sonraki adımlar (insan karar verir)

- Pazarlama sahibiyle 'Flaş Fırsat Saati' kampanyasının başlangıç saati ve beklenen hacmini doğrula.
- Gecikme artışının kaynağını bulmak için DB/cache/bağlantı havuzu doygunluğunu ve autoscale durumunu incele; kapasite artışı gerekiyorsa insan onayıyla uygula.
- p95 gecikme için geçici SLO uyarısı tanımla; 437 ms seviyesi kampanya boyunca sürerse checkout terk oranını izle.
- Kampanya sonrası dönemde dönüşümün 0.05 beklentisine yaklaşıp yaklaşmadığını karşılaştır; sapma varsa funnel adımlarını ayrıca incele.
- Aynı pencere için istemci dağılımını tekrar kontrol ederek tek IP yoğunlaşması oluşursa alarmı yeniden değerlendir.

## Kanıtlar

| evidence_id | Kaynak | Durum | Özet |
|---|---|---|---|
| E01 | loki | ok | Nginx istek hızı: son 2 dk 1716.5/dk, baseline 353.3/dk (4.9x) |
| E02 | loki | ok | Nginx durum payları son 2 dk: 2xx %92.9, 3xx %7.1; baseline: 2xx %92.8, 3xx %7.2 |
| E03 | loki | ok | Farklı istemci IP'si son 2 dk 909, baseline (7 dk) 630; son 2 dk en yoğunlar: client-1 %0.3, client-2 %0.3, client-3 %0.3; baseline'da en yoğun IP'nin payı %0.4 |
| E04 | loki | ok | client-1 son 2 dk: 10 istek (home 1, cart 2, cart_add 2, checkout 1, product 4); 429 0; farklı oturum çerezi 1; çerezsiz istek payı %10.0 |
| E05 | loki | ok | client-2 son 2 dk: 10 istek (home 1, cart 2, cart_add 2, checkout 1, product 4); 429 0; farklı oturum çerezi 1; çerezsiz istek payı %10.0 |
| E06 | loki | ok | Son 2 dk 429 toplamı 0; en çok 429 alanlar: yok |
| E07 | loki | ok | Sunulan (429 olmayan) istekler, dakika başı. Son 2 dk: home 449.0, product 1006.0, cart_add 122.5, checkout_ok 16.5, checkout_failed 0, dönüşüm 0.0367. Baseline: home 90.0, product 209.4, cart_add 25.3, checkout_ok 3.3, checkout_failed 0, dönüşüm 0.0367 |
| E08 | prometheus | ok | Sipariş/dk (shop_orders_total): son 2 dk 16.3, baseline 3.4; son 2 dk ödemeler {'approved': 34.9} |
| E09 | loki | ok | Yakalanmamış uygulama hataları son 2 dk: yok; baseline: yok |
| E10 | prometheus | ok | frontend p95 gecikme: son 2 dk 437.6 ms, baseline 68.7 ms |
| E11 | tempo | ok | Tempo son 2 dk hatalı trace: 0; kök işlemler: yok |
| E12 | grafana | ok | Penceredeki deploy marker'ları: yok |
| E13 | campaigns.json | ok | Kampanya takvimi (pencereyle örtüşen): Flaş Fırsat Saati (alarmdan 120 sn önce başladı, alarmda aktif, beklenen trafik 5x, beklenen dönüşüm 0.05) |

## İstemci takma adları

LLM'e yalnız takma adlar gitti.

- client-1: 176.88.34.84
- client-2: 95.70.44.46
- client-3: 85.96.182.59

## Agent metadata

- Model: openrouter/deepseek/deepseek-v4.1-flash-1017
- Telemetri sorgusu: 46, LLM çağrısı: 1
- Token: 2779 girdi, 3602 çıktı; maliyet: bilinmiyor
- Süre: toplama 8.2 sn, LLM 19.6 sn, toplam 27.8 sn
- Atıf geçerliliği: %100

## Geçersiz atıflar

Var olmayan, erişilemeyen ya da boş evidence_id'ye dayandığı için rapordan çıkarılan iddialar:

- yok
