"""Root-scoped PWA assets: service worker + web app manifest.

The service worker must be served from the site root (not /static/) so its
scope covers every page; that's why these are plain views with explicit
content types instead of static files.
"""

from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import cache_control

_SERVICE_WORKER_JS = """\
// PredictStamp service worker — web push + notification clicks.
self.addEventListener('install', function (event) { self.skipWaiting(); });
self.addEventListener('activate', function (event) {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('push', function (event) {
  var data = {};
  try { data = event.data ? event.data.json() : {}; } catch (e) { data = {}; }
  var title = data.title || 'PredictStamp';
  var options = {
    body: data.body || '',
    tag: data.tag || 'predictstamp',
    data: { url: data.url || '/' },
    renotify: false
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', function (event) {
  event.notification.close();
  var url = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (list) {
      for (var i = 0; i < list.length; i++) {
        var client = list[i];
        if ('focus' in client) { client.navigate(url); return client.focus(); }
      }
      if (self.clients.openWindow) { return self.clients.openWindow(url); }
    })
  );
});
"""


@cache_control(max_age=3600)
def service_worker(request):
    response = HttpResponse(_SERVICE_WORKER_JS, content_type="application/javascript")
    # Allow root scope even though served via a view.
    response["Service-Worker-Allowed"] = "/"
    return response


@cache_control(max_age=3600)
def webmanifest(request):
    manifest = {
        "name": "PredictStamp",
        "short_name": "PredictStamp",
        "description": "The social layer for prediction markets.",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0f172a",
        "theme_color": "#4f46e5",
        "icons": [],
    }
    return JsonResponse(manifest, content_type="application/manifest+json")
