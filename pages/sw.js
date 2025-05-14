self.addEventListener('install', event => {
    event.waitUntil(
      caches.open('eterna-cache-v1').then(cache => {
        return cache.addAll([
          '/',
          '/styles-v2.css',
          '/Assets/Eterna Logo 1.jpeg',
          '/Assets/video-poster.jpg',
          '/Assets/49981-459802291.mp4',
          '/Assets/timeline%20temp%201.png',
        ]);
      })
    );
  });
  
  self.addEventListener('fetch', event => {
    if (event.request.url.includes('/memories/')) {
      event.respondWith(
        fetch(event.request)
          .then(response => {
            const clonedResponse = response.clone();
            caches.open('eterna-cache-v1').then(cache => {
              cache.put(event.request, clonedResponse);
            });
            return response;
          })
          .catch(() => caches.match(event.request).then(response => response || new Response('Offline', { status: 503 })))
      );
    } else {
      event.respondWith(
        caches.match(event.request).then(response => response || fetch(event.request))
      );
    }
  });