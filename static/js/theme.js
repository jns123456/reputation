(function () {
  var STORAGE_KEY = "proofrep-theme";

  function getStoredTheme() {
    try {
      return localStorage.getItem(STORAGE_KEY);
    } catch (_error) {
      return null;
    }
  }

  function getSystemTheme() {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function resolveTheme(stored) {
    if (stored === "dark" || stored === "light") {
      return stored;
    }
    return getSystemTheme();
  }

  function applyTheme(theme) {
    var isDark = theme === "dark";
    document.documentElement.classList.toggle("dark", isDark);
    document.documentElement.dataset.theme = theme;
    window.dispatchEvent(new CustomEvent("proofrep-theme-change", { detail: { theme: theme } }));
  }

  window.proofrepTheme = {
    get: function () {
      return resolveTheme(getStoredTheme());
    },
    set: function (theme) {
      if (theme !== "dark" && theme !== "light") {
        return;
      }
      try {
        localStorage.setItem(STORAGE_KEY, theme);
      } catch (_error) {
        /* ignore storage failures */
      }
      applyTheme(theme);
      return theme;
    },
    toggle: function () {
      var next = this.get() === "dark" ? "light" : "dark";
      return this.set(next);
    },
    init: function () {
      applyTheme(resolveTheme(getStoredTheme()));
    },
  };

  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function (event) {
    if (!getStoredTheme()) {
      applyTheme(event.matches ? "dark" : "light");
    }
  });
})();
