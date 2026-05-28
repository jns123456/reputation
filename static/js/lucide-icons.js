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

  document.body.addEventListener("htmx:afterSwap", function (event) {
    renderLucideIcons(event.detail.target);
  });
})();
