self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open('ai-news-store').then((cache) => cache.addAll([
      '/',
      '/static/index.html',
      '/static/manifest.json'
    ])),
  );
});

self.addEventListener('fetch', (e) => {
  e.respondWith(
    caches.match(e.request).then((response) => response || fetch(e.request)),
  );
});
