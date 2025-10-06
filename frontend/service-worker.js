/**
 * SHIOL+ PWA Service Worker
 * Handles caching, offline functionality, and app installation
 * 
 * AUTO-UPDATE STRATEGY:
 * - Increment APP_VERSION manually on each deploy (e.g., 2.0.0 -> 2.0.1)
 * - Service worker auto-updates silently via skipWaiting() + clients.claim()
 * - Old caches are automatically cleaned up
 * - Users receive updates seamlessly without UI prompts
 */

const APP_VERSION = '2.2.4'; // INCREMENT THIS ON EACH DEPLOY
const CACHE_NAME = `shiol-plus-v${APP_VERSION}`;
const OFFLINE_URL = '/';

// Files to cache for offline functionality
const CACHE_FILES = [
  '/',
  '/index.html',
  '/css/styles.css',
  '/js/countdown.js',
  '/js/powerball-utils.js',
  '/js/public.js',
  '/js/ticket-verification.js',
  '/manifest.json',
  '/static/icon-16x16.png',
  '/static/icon-32x32.png',
  '/static/icon-192x192.png',
  '/static/icon-512x512.png',
  '/static/apple-touch-icon.png',
  'https://cdn.tailwindcss.com',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
  'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Poppins:wght@400;500;600;700&display=swap'
];

// Install event - cache initial files
self.addEventListener('install', (event) => {
  console.log('Service Worker installing...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('Caching app shell files');
        return cache.addAll(CACHE_FILES);
      })
      .then(() => {
        console.log('App shell cached successfully');
        return self.skipWaiting();
      })
      .catch((error) => {
        console.error('Failed to cache app shell:', error);
      })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  console.log('Service Worker activating...');
  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames.map((cacheName) => {
            if (cacheName !== CACHE_NAME) {
              console.log('Deleting old cache:', cacheName);
              return caches.delete(cacheName);
            }
          })
        );
      })
      .then(() => {
        console.log('Service Worker activated');
        return self.clients.claim();
      })
  );
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', (event) => {
  // Skip non-GET requests
  if (event.request.method !== 'GET') {
    return;
  }

  // Handle API requests differently
  if (event.request.url.includes('/api/')) {
    event.respondWith(
      fetch(event.request)
        .catch(() => {
          // Return offline response for API calls
          return new Response(
            JSON.stringify({ error: 'Offline', message: 'App is offline' }),
            {
              status: 503,
              statusText: 'Service Unavailable',
              headers: { 'Content-Type': 'application/json' }
            }
          );
        })
    );
    return;
  }

  // Handle app shell requests
  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        // Return cached version if available
        if (response) {
          return response;
        }

        // Otherwise, fetch from network
        return fetch(event.request)
          .then((response) => {
            // Don't cache if it's not a successful response
            if (!response || response.status !== 200 || response.type !== 'basic') {
              return response;
            }

            // Clone the response for caching
            const responseToCache = response.clone();

            caches.open(CACHE_NAME)
              .then((cache) => {
                cache.put(event.request, responseToCache);
              });

            return response;
          })
          .catch(() => {
            // If network fails, return offline page for navigation requests
            if (event.request.mode === 'navigate') {
              return caches.match(OFFLINE_URL);
            }
          });
      })
  );
});

// Handle push notifications (future feature)
self.addEventListener('push', (event) => {
  if (event.data) {
    const data = event.data.json();
    const options = {
      body: data.body,
      icon: '/icon-192x192.png',
      badge: '/icon-192x192.png',
      vibrate: [200, 100, 200],
      data: data.data || {},
      actions: [
        {
          action: 'view',
          title: 'View',
          icon: '/icon-192x192.png'
        },
        {
          action: 'close',
          title: 'Close',
          icon: '/icon-192x192.png'
        }
      ]
    };

    event.waitUntil(
      self.registration.showNotification(data.title, options)
    );
  }
});

// Handle notification clicks
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  if (event.action === 'view') {
    event.waitUntil(
      clients.openWindow('/')
    );
  }
});

console.log('SHIOL+ Service Worker loaded successfully');