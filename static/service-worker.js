self.addEventListener('install', e => {
    e.waitUntil(
        caches.open('ai-extractor-v1').then(cache => {
            return cache.addAll([
                '/',
                '/static/style.css',
                '/static/main.js',
                '/static/icon-192.png',
                '/static/icon-512.png'
            ]);
        })
    );
});

self.addEventListener('fetch', e => {
    e.respondWith(
        caches.match(e.request).then(response => response || fetch(e.request))
    );
});
