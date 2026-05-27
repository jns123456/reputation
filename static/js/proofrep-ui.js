(function () {
  function observeReveals() {
    var nodes = document.querySelectorAll("[data-pr-reveal], [data-about-reveal]");
    if (!nodes.length) return;

    if (!("IntersectionObserver" in window)) {
      nodes.forEach(function (el) { el.classList.add("is-visible"); });
      return;
    }

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.1, rootMargin: "0px 0px -6% 0px" }
    );

    nodes.forEach(function (el) { observer.observe(el); });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", observeReveals);
  } else {
    observeReveals();
  }

  document.body.addEventListener("htmx:afterSwap", observeReveals);
})();
