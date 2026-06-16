(function () {
  function renderLucideIcons(root) {
    if (!window.lucide || typeof window.lucide.createIcons !== "function") {
      return;
    }

    var attrs = {
      "stroke-width": 1.75,
      "stroke-linecap": "round",
      "stroke-linejoin": "round",
    };

    window.lucide.createIcons({
      attrs: attrs,
      root: root || document,
    });
  }

  window.proofrepIcons = {
    render: renderLucideIcons,
  };

  document.addEventListener("DOMContentLoaded", function () {
    renderLucideIcons(document);
  });

  document.addEventListener("alpine:initialized", function () {
    window.setTimeout(function () {
      renderLucideIcons(document);
    }, 0);
  });

  function renderLucideIconsAfterHtmx(event) {
    var target = event.detail.target;
    if (!target) {
      return;
    }
    renderLucideIcons(target);
  }

  document.body.addEventListener("htmx:afterSwap", renderLucideIconsAfterHtmx);
  document.body.addEventListener("htmx:afterSettle", renderLucideIconsAfterHtmx);
})();
