# inc-fd5e6961: Operasyonel arıza (ops_failure), güven yüksek

**Karar:** Kötü deploy kaynaklı operasyonel arıza: checkout v1.1.0 sonrası checkout hataları ve dönüşüm düşüşü var; saldırı veya kampanya kanıtı yok. [E07, E08, E09, E11, E12, E13]

Pencere: 2026-11-05T16:56:04.162744+00:00 → 2026-11-05T17:08:04.162744+00:00 (alarm)

## Etki

- Sipariş/dk 3.5'ten 1.1'e, dönüşüm 0.0411'den 0.0167'ye düştü; checkout_failed 0'dan 2.0/dk'ya çıktı. [E07, E08]
- Checkout POST isteklerinde 500 ve KeyError hataları oluştu; frontend p95 gecikmesi 68.2 ms'den 74.0 ms'ye hafifçe arttı. [E09, E10, E11]

## Zaman çizelgesi

- Alarmdan 104 sn önce checkout v1.1.0 deploy edildi. [E12]
- Son 2 dakikada checkout KeyError 3, frontend HTTPStatusError 3 ve frontend ConnectError 1 kaydedildi; baseline'da bu hatalar yok. [E09]
- Son 2 dakikada 4 hatalı trace'in tamamı frontend POST /checkout kök işlemiydi. [E11]
- Checkout başarıları 3.7/dk'dan 1.5/dk'ya düşerken checkout hataları 0'dan 2.0/dk'ya çıktı. [E07]
- Sipariş hızı 3.5/dk'dan 1.1/dk'ya geriledi. [E08]

## Hipotezler

- Elenen: attack: Tek IP'den L7 flood yok: istek hızı baseline ile aynı (1.0x), en yoğun istemci payı yalnızca %1.3 ve 429 toplamı 0. [E01, E03, E06]
- Elenen: legit_campaign: Pencereyle örtüşen kampanya yok; trafik hacmi baseline seviyesinde ve dönüşüm düşerken siparişler azalıyor. [E01, E07, E08, E13]
- Desteklenen: ops_failure: Alarmdan 104 sn önce checkout v1.1.0 deploy edilmiş; ardından checkout KeyError, frontend 500 ve checkout POST hataları görülmüş, dönüşüm ve siparişler düşmüştür. [E07, E08, E09, E11, E12]
- Elenen: unknown: Deploy zamanlaması, checkout'a özgü hata örüntüsü ve trafikte saldırı/kampanya sinyali olmaması birlikte operasyonel arızayı destekliyor. [E01, E07, E09, E11, E12, E13]

## Beni ne yanıltabilir?

- client-1 ve client-2'nin birebir aynı 10 istek profili otomasyon şüphesi doğurabilir; ancak tekil IP payları çok küçük ve 429 yok, bu tek başına saldırı kanıtı değildir. [E03, E04, E05, E06]
- Deploy marker'ı tek başına nedensellik kanıtlamaz; yine de checkout KeyError ve 500 zamanlaması deploy sonrası hata örüntüsüyle uyumludur. [E09, E12]

## Eksik kanıt

- checkout v1.1.0 deploy diff/changelog ve varsa rollback/canary kayıtları
- KeyError: 3 hatasına yol açan örnek checkout isteği ve giriş verisi
- Hata oranının checkout v1.1.0 öncesi ve sonrası sürüm bazında karşılaştırması
- frontend ConnectError'un checkout servis kesintisi mi yoksa ağ hatası mı olduğunu gösteren servis durum/restart logları

## Sonraki adımlar (insan karar verir)

- checkout v1.1.0 deploy'unu ve özellikle _bundle_discount çevresindeki değişikliği inceleyin; gerekirse rollback kararı için insan onayı alın.
- Checkout KeyError ve 500 hatalarının sürüm öncesi/sonrası oranlarını doğrulayın.
- Frontend ConnectError için checkout servisinin ayakta olup olmadığını ve restart/kesinti loglarını kontrol edin.
- Rollback veya düzeltme sonrası sipariş/dk, dönüşüm ve checkout hata oranlarını izleyin.

## Kanıtlar

| evidence_id | Kaynak | Durum | Özet |
|---|---|---|---|
| E01 | loki | ok | Nginx istek hızı: son 2 dk 376.0/dk, baseline 361.1/dk (1.0x) |
| E02 | loki | ok | Nginx durum payları son 2 dk: 2xx %91.6, 3xx %7.8, 5xx %0.5; baseline: 2xx %91.9, 3xx %8.1 |
| E03 | loki | ok | Farklı istemci IP'si son 2 dk 191, baseline (7 dk) 630; son 2 dk en yoğunlar: client-1 %1.3, client-2 %1.3, client-3 %1.3; baseline'da en yoğun IP'nin payı %0.4 |
| E04 | loki | ok | client-1 son 2 dk: 10 istek (home 1, cart 2, cart_add 2, checkout 1, product 4); 429 0; farklı oturum çerezi 1; çerezsiz istek payı %10.0 |
| E05 | loki | ok | client-2 son 2 dk: 10 istek (home 1, cart 2, cart_add 2, checkout 1, product 4); 429 0; farklı oturum çerezi 1; çerezsiz istek payı %10.0 |
| E06 | loki | ok | Son 2 dk 429 toplamı 0; en çok 429 alanlar: yok |
| E07 | loki | ok | Sunulan (429 olmayan) istekler, dakika başı. Son 2 dk: home 90.0, product 223.5, cart_add 29.5, checkout_ok 1.5, checkout_failed 2.0, dönüşüm 0.0167. Baseline: home 90.0, product 209.1, cart_add 29.1, checkout_ok 3.7, checkout_failed 0, dönüşüm 0.0411 |
| E08 | prometheus | ok | Sipariş/dk (shop_orders_total): son 2 dk 1.1, baseline 3.5; son 2 dk ödemeler {'approved': 2.2} |
| E09 | loki | ok | Yakalanmamış uygulama hataları son 2 dk: frontend HTTPStatusError 3, checkout KeyError 3, frontend ConnectError 1; baseline: yok |
| E10 | prometheus | ok | frontend p95 gecikme: son 2 dk 74.0 ms, baseline 68.2 ms |
| E11 | tempo | ok | Tempo son 2 dk hatalı trace: 4; kök işlemler: frontend POST /checkout 4 |
| E12 | grafana | ok | Penceredeki deploy marker'ları: checkout v1.1.0 alarmdan 104 sn önce |
| E13 | campaigns.json | ok | Kampanya takvimi (pencereyle örtüşen): yok |

## İstemci takma adları

LLM'e yalnız takma adlar gitti.

- client-1: 85.96.19.242
- client-2: 176.88.121.195
- client-3: 176.88.130.217

## Agent metadata

- Model: openrouter/deepseek/deepseek-v4.1-flash-1017
- Telemetri sorgusu: 46, LLM çağrısı: 1
- Token: 3111 girdi, 2719 çıktı; maliyet: bilinmiyor
- Süre: toplama 8.1 sn, LLM 13.1 sn, toplam 21.2 sn
- Atıf geçerliliği: %100

## Geçersiz atıflar

Var olmayan, erişilemeyen ya da boş evidence_id'ye dayandığı için rapordan çıkarılan iddialar:

- yok
