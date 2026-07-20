(function () {
  "use strict";

  function defaultNextUrl() {
    return window.location.pathname + window.location.search + window.location.hash;
  }

  window.openAuthModal = function (options) {
    options = options || {};
    window.dispatchEvent(
      new CustomEvent("auth-modal:open", {
        detail: {
          tab: options.tab || "signup",
          next: options.next || defaultNextUrl(),
          intent: options.intent || "",
        },
      })
    );
  };

  window.authModalState = function () {
    return {
      open: false,
      tab: "signup",
      nextUrl: defaultNextUrl(),
      intent: "",
      openFromEvent(event) {
        var detail = (event && event.detail) || {};
        this.tab = detail.tab === "login" ? "login" : "signup";
        this.nextUrl = detail.next || defaultNextUrl();
        this.intent = detail.intent || "";
        this.open = true;
        document.body.classList.add("pr-auth-modal-open");
        var self = this;
        window.requestAnimationFrame(function () {
          if (window.lucide && window.lucide.createIcons) {
            window.lucide.createIcons();
          }
          if (
            self.tab === "signup" &&
            window.predictStampTurnstile &&
            window.predictStampTurnstile.initDeferredWidgets
          ) {
            window.predictStampTurnstile.initDeferredWidgets();
          }
          var focusId =
            self.tab === "login" ? "auth-modal-username" : "auth-modal-signup-username";
          var input = document.getElementById(focusId);
          if (input) {
            input.focus();
          }
        });
      },
      close() {
        this.open = false;
        document.body.classList.remove("pr-auth-modal-open");
      },
    };
  };
})();
