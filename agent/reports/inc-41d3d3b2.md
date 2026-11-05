# inc-41d3d3b2: Saldırı (attack), güven orta

**Karar:** client-1 ve client-2 kaynaklı, neredeyse aynı desenli, dönüşümü düşük yüksek hacimli trafik L7 bot/flood saldırısı olarak değerlendirildi; aktif kampanya trafik artışının bir kısmını açıklasa da iki istemcinin baskınlığını ve dönüşüm uyumsuzluğunu açıklamıyor. [E01, E03, E04, E05, E06, E07, E13]

Pencere: 2026-11-05T15:55:18.948073+00:00 → 2026-11-05T16:07:18.948073+00:00 (alarm)

## Etki

- İstek hızı baseline'a göre 4x arttı (362.3/dk → 1444.5/dk), p95 gecikme 78.2 ms → 200.8 ms oldu; 264 429 ile bazı istemciler ret/gecikme yaşadı. [E01, E06, E10]
- Sipariş/dk 3.8 → 6.0 ve onaylı ödeme 12/dk görünse de dönüşüm 0.0446 → 0.0132'ye düştü; yüksek hacimli trafik funnel'ı şişiriyor olabilir. [E07, E08]

## Zaman çizelgesi

- Hafta Sonu İndirimi kampanyası alarmdan 120 sn önce başladı ve alarm anında aktifti. [E13]
- Son 2 dakikada Nginx istek hızı baseline'ın 4 katına çıktı. [E01]
- client-1 ve client-2 son 2 dakikadaki trafiğin yaklaşık %74'ünü oluşturdu; baseline'da en yoğun IP payı %0.4 idi. [E03]
- Son 2 dakikada 264 adet 429 oluştu; bunun %53.8'i client-1, %46.2'si client-2 kaynaklıydı. [E06]
- Dönüşüm oranı baseline 0.0446'den son 2 dakikada 0.0132'ye geriledi. [E07]
- Pencerede deploy marker'ı yok; yakalanmamış uygulama hatası ve hatalı trace de yok. [E09, E11, E12]

## Hipotezler

- Desteklenen: attack: client-1 ve client-2'nin neredeyse aynı istek dağılımı, 245'er oturum, yüksek ve birbirine yakın 429 sayıları ile düşük dönüşümü koordineli bot/L7 flood davranışıyla uyumlu; baseline'da bu istemciler baskın değildi. [E03, E04, E05, E06, E07]
- Elenen: legit_campaign: Kampanya aktif ve trafik 4x olsa da beklenen dönüşüm 0.05 iken gerçekleşen 0.0132; ayrıca trafik iki istemcide toplanmış ve baseline'da en yoğun IP payı yalnızca %0.4. Kampanya tek başına bu dağılımı açıklamıyor. [E13, E01, E03, E07]
- Elenen: ops_failure: Deploy marker'ı yok, uygulama hatası ve hatalı trace yok; gecikme artışı uygulama arızasından çok yük kaynaklı görünüyor. [E12, E09, E11, E10]
- Elenen: unknown: İki istemcinin koordineli anormal davranışı ve kampanya beklentisiyle dönüşüm uyumsuzluğu birlikte değerlendirildiğinde sınıflandırma için yeterli kanıt var. [E03, E04, E05, E07, E13]

## Beni ne yanıltabilir?

- Aktif kampanya, 4x trafik artışını meşru talep gibi gösterebilir; kampanya alarmdan yalnızca 120 sn önce başlamıştı. [E13, E01]
- 429 ve 2xx oranları tek başına saldırı/meşru ayrımı yapmaz; rate limit meşru kampanya trafiğini de etkileyebilir. [E02, E06]
- Sipariş/dk ve onaylı ödeme artışı, gerçek talebin de sürdüğünü göstererek saldırı yorumunu zayıflatabilir. [E08]
- V1'deki tek IP L7 flood tanımı, iki baskın istemci nedeniyle attack yerine unknown düşünülmesine yol açabilir; ancak iki istemcinin deseni koordineli bot davranışına işaret ediyor. [E03, E04, E05]

## Eksik kanıt

- client-1 ve client-2 için user-agent, ASN/veri merkezi bilgisi, path sıralaması ve zamanlama örüntüsü
- Kampanya kanal/affiliate dağılımı ve beklenen trafik kaynakları
- WAF/bot skoru, IP itibarı ve CAPTCHA/JS challenge sonuçları
- 429 sonrası gerçek kullanıcı oturumları ve checkout tamamlama davranışı
- Daha uzun baseline ve kampanya öncesi/sonrası karşılaştırma

## Sonraki adımlar (insan karar verir)

- client-1 ve client-2 IP/ASN'lerini bot yönetimi kapsamında incele; challenge veya geçici blok için insan onayına sun.
- Kampanya sahibiyle beklenen 5x trafik ve 0.05 dönüşümün neden tutmadığını doğrula.
- Kampanya süresince 429 oranını ve gerçek kullanıcı dönüşümünü izle; rate limit eşiklerini gözden geçir.
- İki istemcinin diğer IP'lerle ilişkisini ve istek zamanlamasını incele; koordineli bot kanıtını teyit et.
- Saldırı teyit edilirse trafik kaynağını sınırla; meşru çıkarsa kampanya için rate limiti ayarla.

## Kanıtlar

| evidence_id | Kaynak | Durum | Özet |
|---|---|---|---|
| E01 | loki | ok | Nginx istek hızı: son 2 dk 1444.5/dk, baseline 362.3/dk (4.0x) |
| E02 | loki | ok | Nginx durum payları son 2 dk: 2xx %85.7, 3xx %5.1, 429 %9.1; baseline: 2xx %92.0, 3xx %8.0 |
| E03 | loki | ok | Farklı istemci IP'si son 2 dk 193, baseline (7 dk) 628; son 2 dk en yoğunlar: client-1 %37.5, client-2 %36.6, client-3 %0.3; baseline'da en yoğun IP'nin payı %0.4 |
| E04 | loki | ok | client-1 son 2 dk: 1084 istek (home 363, cart 46, cart_add 56, checkout 5, product 614); 429 142; farklı oturum çerezi 245; çerezsiz istek payı %33.5 |
| E05 | loki | ok | client-2 son 2 dk: 1057 istek (home 349, cart 45, cart_add 51, checkout 4, product 608); 429 122; farklı oturum çerezi 245; çerezsiz istek payı %33.0 |
| E06 | loki | ok | Son 2 dk 429 toplamı 264; en çok 429 alanlar: client-1 142 (%53.8), client-2 122 (%46.2) |
| E07 | loki | ok | Sunulan (429 olmayan) istekler, dakika başı. Son 2 dk: home 417.0, product 750.0, cart_add 74.0, checkout_ok 5.5, checkout_failed 0, dönüşüm 0.0132. Baseline: home 89.7, product 210.6, cart_add 29.0, checkout_ok 4.0, checkout_failed 0, dönüşüm 0.0446 |
| E08 | prometheus | ok | Sipariş/dk (shop_orders_total): son 2 dk 6.0, baseline 3.8; son 2 dk ödemeler {'approved': 12.0} |
| E09 | loki | ok | Yakalanmamış uygulama hataları son 2 dk: yok; baseline: yok |
| E10 | prometheus | ok | frontend p95 gecikme: son 2 dk 200.8 ms, baseline 78.2 ms |
| E11 | tempo | ok | Tempo son 2 dk hatalı trace: 0; kök işlemler: yok |
| E12 | grafana | ok | Penceredeki deploy marker'ları: yok |
| E13 | campaigns.json | ok | Kampanya takvimi (pencereyle örtüşen): Hafta Sonu İndirimi (alarmdan 120 sn önce başladı, alarmda aktif, beklenen trafik 5x, beklenen dönüşüm 0.05) |

## İstemci takma adları

LLM'e yalnız takma adlar gitti.

- client-1: 176.40.12.19
- client-2: 176.40.12.7
- client-3: 176.88.55.30

## Agent metadata

- Model: openrouter/deepseek/deepseek-v4.1-flash-1017
- Telemetri sorgusu: 46, LLM çağrısı: 1
- Token: 2880 girdi, 8774 çıktı; maliyet: bilinmiyor
- Süre: toplama 7.3 sn, LLM 41.3 sn, toplam 48.6 sn
- Atıf geçerliliği: %100

## Geçersiz atıflar

Var olmayan, erişilemeyen ya da boş evidence_id'ye dayandığı için rapordan çıkarılan iddialar:

- yok
