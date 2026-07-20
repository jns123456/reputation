(function () {
  "use strict";

  function forEachWidget(callback) {
    document.querySelectorAll(".cf-turnstile[data-sitekey]").forEach(callback);
  }

  function renderWidget(container) {
    if (!window.turnstile || container.dataset.widgetId) {
      return;
    }
    var sitekey = container.dataset.sitekey;
    if (!sitekey) {
      return;
    }
    container.dataset.widgetId = window.turnstile.render(container, {
      sitekey: sitekey,
      callback: function () {
        container.dataset.turnstileReady = "1";
      },
      "error-callback": function () {
        delete container.dataset.turnstileReady;
      },
      "expired-callback": function () {
        delete container.dataset.turnstileReady;
      },
    });
  }

  function resetWidgets() {
    if (!window.turnstile) {
      return;
    }
    forEachWidget(function (container) {
      if (container.dataset.widgetId) {
        window.turnstile.reset(container.dataset.widgetId);
      }
      delete container.dataset.turnstileReady;
    });
  }

  function bindSubmitGuard() {
    forEachWidget(function (container) {
      var form = container.closest("form");
      if (!form || form.dataset.turnstileGuardBound) {
        return;
      }
      form.dataset.turnstileGuardBound = "1";
      form.addEventListener("submit", function (event) {
        if (container.dataset.turnstileReady === "1") {
          return;
        }
        var tokenField = form.querySelector('[name="cf-turnstile-response"]');
        if (tokenField && tokenField.value) {
          return;
        }
        event.preventDefault();
      });
    });
  }

  function initVisibleWidgets() {
    forEachWidget(function (container) {
      if (container.dataset.turnstileRender === "deferred") {
        return;
      }
      renderWidget(container);
    });
    bindSubmitGuard();
  }

  function initDeferredWidgets() {
    forEachWidget(function (container) {
      if (container.dataset.turnstileRender !== "deferred") {
        return;
      }
      renderWidget(container);
    });
    bindSubmitGuard();
  }

  window.predictStampTurnstile = {
    initDeferredWidgets: initDeferredWidgets,
    resetWidgets: resetWidgets,
  };

  function onReady() {
    initVisibleWidgets();
    if (document.querySelector("[data-human-verification-error]")) {
      resetWidgets();
    }
  }

  if (window.turnstile) {
    window.turnstile.ready(onReady);
  } else {
    var attempts = 0;
    var poll = window.setInterval(function () {
      if (!window.turnstile) {
        attempts += 1;
        if (attempts > 100) {
          window.clearInterval(poll);
        }
        return;
      }
      window.clearInterval(poll);
      window.turnstile.ready(onReady);
    }, 100);
  }
})();
