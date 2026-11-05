# inc-2ef0e0db: Operasyonel arıza (ops_failure), güven yüksek

**Karar:** checkout v1.1.0 deploy'undan kısa süre sonra checkout KeyError/500 hataları ve dönüşüm-sipariş düşüşü görüldüğü için olay operasyonel arıza olarak sınıflandırıldı. [E12, E09, E11, E07, E08]

Pencere: 2026-11-05T11:33:58.129245+00:00 → 2026-11-05T11:45:58.129245+00:00 (alarm)

## Etki

- Dönüşüm 0.0489'dan 0.0278'e, checkout_ok 4.4/dk'dan 2.5/dk'ya düştü; sipariş/dk 4.4'ten 2.4'e indi. [E07, E08]
- Checkout kaynaklı KeyError ve frontend POST /checkout 500 hataları ödeme akışını bozuyor; son 2 dk 5xx payı %0.3. [E09, E11, E02]
- Gecikme baseline ile benzer (p95 91.1 ms vs 97.0 ms); sorun yük kaynaklı görünmüyor. [E10]

## Zaman çizelgesi

- Alarmdan 103 sn önce checkout v1.1.0 deploy edildi. [E12]
- Son 2 dk içinde checkout KeyError, frontend HTTPStatusError 500 ve ConnectError görüldü. [E09, E11]
- Son 2 dk sipariş ve dönüşüm baseline'ın altında kaldı. [E07, E08]
- Nginx istek hızı baseline ile aynı seviyede (348.5/dk vs 352.0/dk). [E01]

## Hipotezler

- Elenen: attack: İstek hızı 1.0x, tek IP yoğunlaşması yok (en yüksek pay %1.1) ve 429 toplamı 0; L7 flood kanıtı yok. [E01, E03, E06]
- Elenen: legit_campaign: Kampanya takvimi boş, trafik artmıyor; aksine dönüşüm ve sipariş düşüyor. [E13, E01, E07, E08]
- Desteklenen: ops_failure: checkout v1.1.0 deploy'undan 103 sn sonra checkout KeyError ve POST /checkout 500 trace'leri görülmüş; sipariş ve dönüşüm aynı dönemde düşmüş. [E12, E09, E11, E07, E08]
- Elenen: unknown: Deploy, checkout hatası ve iş etkisi aynı akışta tutarlı bir zincir oluşturuyor; sınıflandırma için yeterli kanıt var. [E12, E09, E11, E07, E08]

## Beni ne yanıltabilir?

- Hata sayıları düşük (KeyError ve 500 için 1'er, yalnız 2 hatalı trace); küçük örneklem nedenselliği abarttırabilir. [E09, E11]
- ConnectError DNS çözümleme hatası ayrı bir altyapı arızasına işaret edebilir; deploy dışı neden ekarte edilmeli. [E09]
- Baseline 7 dk, son pencere 2 dk; distinct client sayıları doğrudan oran olarak karşılaştırılmamalı. [E03]
- Untrusted log excerpt'ları talimat değil veri olarak alınmalı; içerik yanıltıcı olabilir. [E09]

## Eksik kanıt

- checkout v1.1.0 deploy diff'i, commit kaydı ve rollback geçmişi
- checkout servisinin tam hata logları ve KeyError'un deploy öncesi/sonrası dağılımı
- DNS ConnectError için servis keşfi ve altyapı sağlık metrikleri
- Deploy öncesi/sonrası dakika bazlı checkout başarı oranı, sipariş ve dönüşüm karşılaştırması
- Pencere dışındaki konfigürasyon değişiklikleri veya checkout dışı servis deploy'ları

## Sonraki adımlar (insan karar verir)

- İnsanın checkout v1.1.0 deploy'unu incelemesi; gerekirse rollback veya canary ile doğrulaması
- checkout _bundle_discount satırındaki KeyError ve indirim sepeti mantığının düzeltilmesi için ilgili ekibin çağrılması
- DNS ConnectError için servis keşfi ve ağ/altyapı sağlığının kontrol edilmesi
- Deploy öncesi/sonrası checkout başarı oranı, sipariş ve dönüşüm metriklerinin karşılaştırılması
- Kampanya takviminin ve trafik kaynaklarının teyit edilmesi

## Kanıtlar

| evidence_id | Kaynak | Durum | Özet |
|---|---|---|---|
| E01 | loki | ok | Nginx istek hızı: son 2 dk 348.5/dk, baseline 352.0/dk (1.0x) |
| E02 | loki | ok | Nginx durum payları son 2 dk: 2xx %91.4, 3xx %8.3, 5xx %0.3; baseline: 2xx %92.4, 3xx %7.6 |
| E03 | loki | ok | Farklı istemci IP'si son 2 dk 195, baseline (7 dk) 629; son 2 dk en yoğunlar: client-1 %1.1, client-2 %1.1, client-3 %1.1; baseline'da en yoğun IP'nin payı %0.4 |
| E04 | loki | ok | client-1 son 2 dk: 8 istek (home 1, cart 2, cart_add 2, checkout 1, product 2); 429 0; farklı oturum çerezi 1; çerezsiz istek payı %12.5 |
| E05 | loki | ok | client-2 son 2 dk: 8 istek (home 1, cart 2, cart_add 2, product 3); 429 0; farklı oturum çerezi 1; çerezsiz istek payı %12.5 |
| E06 | loki | ok | Son 2 dk 429 toplamı 0; en çok 429 alanlar: yok |
| E07 | loki | ok | Sunulan (429 olmayan) istekler, dakika başı. Son 2 dk: home 90.0, product 197.0, cart_add 29.0, checkout_ok 2.5, checkout_failed 1.0, dönüşüm 0.0278. Baseline: home 90.0, product 204.1, cart_add 26.7, checkout_ok 4.4, checkout_failed 0, dönüşüm 0.0489 |
| E08 | prometheus | ok | Sipariş/dk (shop_orders_total): son 2 dk 2.4, baseline 4.4; son 2 dk ödemeler {'approved': 5.4} |
| E09 | loki | ok | Yakalanmamış uygulama hataları son 2 dk: frontend ConnectError 1, frontend HTTPStatusError 1, checkout KeyError 1; baseline: yok |
| E10 | prometheus | ok | frontend p95 gecikme: son 2 dk 91.1 ms, baseline 97.0 ms |
| E11 | tempo | ok | Tempo son 2 dk hatalı trace: 2; kök işlemler: frontend POST /checkout 2 |
| E12 | grafana | ok | Penceredeki deploy marker'ları: checkout v1.1.0 alarmdan 103 sn önce |
| E13 | campaigns.json | ok | Kampanya takvimi (pencereyle örtüşen): yok |

## İstemci takma adları

LLM'e yalnız takma adlar gitti.

- client-1: 212.253.209.160
- client-2: 176.88.243.104
- client-3: 176.234.105.166

## Agent metadata

- Model: openrouter/deepseek/deepseek-v4.1-flash-1017
- Telemetri sorgusu: 46, LLM çağrısı: 1
- Token: 3107 girdi, 4492 çıktı; maliyet: bilinmiyor
- Süre: toplama 7.6 sn, LLM 8.8 sn, toplam 16.4 sn
- Atıf geçerliliği: %100

## Geçersiz atıflar

Var olmayan, erişilemeyen ya da boş evidence_id'ye dayandığı için rapordan çıkarılan iddialar:

- yok
