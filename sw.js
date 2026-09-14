/* 投资实证工作台 · 离线缓存
   目标：装到手机主屏 / 桌面之后，断网也能打开，数据仍可读写（数据在
   localStorage 或桌面版的 data\save.json，都不依赖网络）。 */
var CACHE = 'invest-v2';
var ASSETS = [
  './', './index.html', './manifest.webmanifest',
  './icon-512.png', './apple-touch-icon.png', './stocks_data.js'
];

self.addEventListener('install', function (e) {
  e.waitUntil(
    caches.open(CACHE).then(function (c) {
      /* 逐个加，单个失败不影响整体（stocks_data.js 快 1MB，失败也不该卡住安装） */
      return Promise.all(ASSETS.map(function (u) {
        return c.add(new Request(u, { cache: 'reload' })).catch(function () {});
      }));
    }).then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (e) {
  e.waitUntil(
    caches.keys().then(function (ks) {
      return Promise.all(ks.filter(function (k) { return k !== CACHE; })
        .map(function (k) { return caches.delete(k); }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET') return;
  var url = new URL(req.url);

  /* 本地数据接口永远走网络，不缓存 */
  if (url.pathname.indexOf('/api/') === 0) return;

  /* 行情接口不缓存（要实时） */
  if (/gtimg\.cn|eastmoney\.com|sinajs\.cn/.test(url.host)) return;

  /* 页面导航：网络优先，断网回退缓存 —— 这样更新能及时拿到 */
  if (req.mode === 'navigate') {
    e.respondWith(
      fetch(req).then(function (r) {
        var cp = r.clone();
        caches.open(CACHE).then(function (c) { c.put('./index.html', cp); });
        return r;
      }).catch(function () {
        return caches.match('./index.html').then(function (r) {
          return r || caches.match('./');
        });
      })
    );
    return;
  }

  /* 静态资源：缓存优先，同时在后台更新 */
  e.respondWith(
    caches.match(req).then(function (hit) {
      var net = fetch(req).then(function (r) {
        if (r && r.status === 200 && r.type === 'basic') {
          var cp = r.clone();
          caches.open(CACHE).then(function (c) { c.put(req, cp); });
        }
        return r;
      }).catch(function () { return hit; });
      return hit || net;
    })
  );
});
