// Watcher lab yükü: baştan sona normal alışverişçiler, ortada senaryonun olayı.
// scenarios/runner.py çalıştırır; olay türü, süreler ve IP'ler ortam değişkeniyle gelir.
// İsteklerde k6'yı ele veren iz yok: User-Agent gerçek tarayıcı, istemci IP'si X-Forwarded-For'da.
import http from 'k6/http';
import { sleep } from 'k6';

const BASE = `http://${__ENV.LAB_BIND_IP}`;
const INCIDENT = __ENV.INCIDENT || 'none'; // none | campaign | nat_campaign | flood
const BASELINE_S = Number(__ENV.BASELINE_S || 600);
const INCIDENT_S = Number(__ENV.INCIDENT_S || 900);
const RECOVERY_S = Number(__ENV.RECOVERY_S || 300);
const SHOPPERS_PER_S = Number(__ENV.SHOPPERS_PER_S || 1.5);
const CAMPAIGN_MULTIPLIER = Number(__ENV.CAMPAIGN_MULTIPLIER || 5);
const FLOOD_RPS = Number(__ENV.FLOOD_RPS || 55);
const ATTACKER_IP = __ENV.ATTACKER_IP;
const NAT_IPS = (__ENV.NAT_IPS || '').split(',');
const PRODUCT_IDS = [1, 2, 3, 4, 5, 6];

const USER_AGENTS = [
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0',
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/19.0 Safari/605.1.15',
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
  'Mozilla/5.0 (iPhone; CPU iPhone OS 19_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/19.0 Mobile/15E148 Safari/604.1',
  'Mozilla/5.0 (Linux; Android 15; SM-S921B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/537.36',
  'Mozilla/5.0 (Linux; Android 14; Redmi Note 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0',
];
// Normal ziyaretçi IP'leri geniş erişim ağlarına benzeyen bloklardan rastgele seçilir; tekrar eden IP nadirdir.
const BLOCKS = ['78.160', '78.173', '85.96', '85.105', '88.224', '88.238', '95.70', '176.88', '176.234', '212.253'];

function pick(list) {
  return list[Math.floor(Math.random() * list.length)];
}

function octet() {
  return 1 + Math.floor(Math.random() * 254);
}

function think() {
  sleep(1 + Math.random() * 4);
}

function arrivals(rate, startS, durationS, exec, vusPerArrival) {
  return {
    executor: 'constant-arrival-rate',
    rate: Math.round(rate * 60), // k6 tam sayı ister; 1,5/sn = 90/dk
    timeUnit: '1m',
    startTime: `${startS}s`,
    duration: `${durationS}s`,
    preAllocatedVUs: Math.ceil(rate * vusPerArrival),
    maxVUs: Math.ceil(rate * vusPerArrival * 3),
    exec,
  };
}

// Bir alışveriş oturumu ~15 sn sürer; aynı anda ~15 VU/varış gerekir.
const scenarios = {
  shoppers: arrivals(SHOPPERS_PER_S, 0, BASELINE_S + INCIDENT_S + RECOVERY_S, 'shopper', 15),
};
const extraShoppers = SHOPPERS_PER_S * (CAMPAIGN_MULTIPLIER - 1);
if (INCIDENT === 'campaign') scenarios.incident = arrivals(extraShoppers, BASELINE_S, INCIDENT_S, 'shopper', 15);
if (INCIDENT === 'nat_campaign') scenarios.incident = arrivals(extraShoppers, BASELINE_S, INCIDENT_S, 'natShopper', 15);
if (INCIDENT === 'flood') scenarios.incident = arrivals(FLOOD_RPS, BASELINE_S, INCIDENT_S, 'flooder', 0.5);

export const options = { scenarios, discardResponseBodies: true };

// Funnel: %80 ürüne bakar, bakanların %30'u sepete ekler (%30'u iki farklı ürün), ekleyenlerin %21'i öder → dönüşüm ~%5.
function visit(ip) {
  const params = { jar: new http.CookieJar(), headers: { 'X-Forwarded-For': ip, 'User-Agent': pick(USER_AGENTS) } };
  const ok = (response) => response.status < 400; // hata alan alışverişçi siteden çıkar
  if (!ok(http.get(`${BASE}/`, params)) || Math.random() < 0.2) return;
  const views = 2 + Math.floor(Math.random() * 3);
  for (let i = 0; i < views; i++) {
    think();
    if (!ok(http.get(`${BASE}/product/${pick(PRODUCT_IDS)}`, params))) return;
  }
  if (Math.random() >= 0.3) return;
  const first = pick(PRODUCT_IDS);
  const items = Math.random() < 0.3 ? [first, (first % PRODUCT_IDS.length) + 1] : [first];
  for (const id of items) {
    think();
    if (!ok(http.post(`${BASE}/cart/add`, { product_id: String(id) }, params))) return;
  }
  if (Math.random() >= 0.21) return;
  think();
  http.post(`${BASE}/checkout`, null, params);
}

export function shopper() {
  visit(`${pick(BLOCKS)}.${octet()}.${octet()}`);
}

// Mobil operatör NAT'ı: çok sayıda gerçek kullanıcı az sayıda IP'nin arkasında.
export function natShopper() {
  visit(pick(NAT_IPS));
}

// Flood botu çerez tutmaz; her istek yeni, oturumsuz bir istemci gibi görünür.
export function flooder() {
  http.get(`${BASE}/`, {
    jar: new http.CookieJar(),
    headers: { 'X-Forwarded-For': ATTACKER_IP, 'User-Agent': pick(USER_AGENTS) },
  });
}
