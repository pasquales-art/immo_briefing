'use strict';

var CACHE_VERSION = 'morgenbriefing-v1';
var SHELL_CACHE = CACHE_VERSION + '-shell';
var CONTENT_CACHE = CACHE_VERSION + '-content';

var SHELL_ASSETS = [
  './',
  './index.html',
  './manifest.webmanifest',
  './icons/icon-180.png',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/icon-512-maskable.png'
];

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(SHELL_CACHE)
      .then(function (cache) { return cache.addAll(SHELL_ASSETS); })
      .then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys
          .filter(function (key) { return key.indexOf(CACHE_VERSION) !== 0; })
          .map(function (key) { return caches.delete(key); })
      );
    }).then(function () { return self.clients.claim(); })
  );
});

function isContentRequest(url) {
  return url.pathname.indexOf('/posts/') !== -1;
}

// Content (posts index + markdown) is network-first so a new briefing
// shows up immediately when online; falls back to cache when offline.
function networkFirst(request) {
  return fetch(request)
    .then(function (response) {
      if (response && response.ok) {
        var copy = response.clone();
        caches.open(CONTENT_CACHE).then(function (cache) { cache.put(request, copy); });
      }
      return response;
    })
    .catch(function () { return caches.match(request); });
}

// App shell is cache-first for speed, refreshed in the background.
function cacheFirst(request) {
  return caches.match(request).then(function (cached) {
    var fetchPromise = fetch(request).then(function (response) {
      if (response && response.ok) {
        var copy = response.clone();
        caches.open(SHELL_CACHE).then(function (cache) { cache.put(request, copy); });
      }
      return response;
    }).catch(function () { return cached; });
    return cached || fetchPromise;
  });
}

self.addEventListener('fetch', function (event) {
  var request = event.request;
  if (request.method !== 'GET') return;

  var url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (isContentRequest(url)) {
    event.respondWith(networkFirst(request));
    return;
  }

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(function () { return caches.match('./index.html'); })
    );
    return;
  }

  event.respondWith(cacheFirst(request));
});
