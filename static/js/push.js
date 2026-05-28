// PredictStamp web push client.
// Registers the service worker and, when the user opts in, subscribes to push
// and stores the subscription server-side. No-ops when push is unsupported or
// the server reports push as disabled (no VAPID keys configured).
(function () {
  "use strict";

  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    return;
  }

  function getCookie(name) {
    var match = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return match ? decodeURIComponent(match.pop()) : "";
  }

  function urlBase64ToUint8Array(base64String) {
    var padding = "=".repeat((4 - (base64String.length % 4)) % 4);
    var base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
    var raw = window.atob(base64);
    var output = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; ++i) {
      output[i] = raw.charCodeAt(i);
    }
    return output;
  }

  function postJson(url, body) {
    return fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken")
      },
      credentials: "same-origin",
      body: JSON.stringify(body || {})
    });
  }

  var registrationPromise = navigator.serviceWorker
    .register("/sw.js")
    .catch(function (err) {
      console.warn("SW registration failed", err);
      return null;
    });

  function fetchConfig() {
    return fetch("/accounts/push/vapid-key/", { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .catch(function () { return { enabled: false }; });
  }

  function subscribe() {
    return Promise.all([registrationPromise, fetchConfig()]).then(function (results) {
      var registration = results[0];
      var config = results[1];
      if (!registration || !config.enabled || !config.publicKey) {
        return false;
      }
      return registration.pushManager
        .getSubscription()
        .then(function (existing) {
          if (existing) {
            return existing;
          }
          return registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(config.publicKey)
          });
        })
        .then(function (subscription) {
          return postJson("/accounts/push/subscribe/", {
            subscription: subscription.toJSON()
          }).then(function () { return true; });
        });
    });
  }

  // Expose an opt-in trigger for a settings button.
  window.PredictStampPush = {
    enable: function () {
      if (Notification.permission === "granted") {
        return subscribe();
      }
      return Notification.requestPermission().then(function (permission) {
        if (permission === "granted") {
          return subscribe();
        }
        return false;
      });
    },
    isGranted: function () {
      return Notification.permission === "granted";
    }
  };

  // Auto-resubscribe silently for users who already granted permission.
  if (Notification.permission === "granted") {
    subscribe();
  }
})();
