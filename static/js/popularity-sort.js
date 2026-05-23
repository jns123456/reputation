(function () {
  function readVoteScore(voteEl) {
    var scoreEl = voteEl.querySelector("[data-vote-score]");
    if (scoreEl) {
      return parseInt(scoreEl.getAttribute("data-vote-score") || "0", 10);
    }
    return 0;
  }

  function sortPopularityList(container) {
    if (!container) return;

    var items = Array.prototype.filter.call(
      container.children,
      function (node) {
        return node.hasAttribute && node.hasAttribute("data-sort-score");
      }
    );
    if (items.length < 2) return;

    items.sort(function (a, b) {
      var scoreA = parseInt(a.getAttribute("data-sort-score") || "0", 10);
      var scoreB = parseInt(b.getAttribute("data-sort-score") || "0", 10);
      if (scoreB !== scoreA) return scoreB - scoreA;

      var repA = parseFloat(a.getAttribute("data-sort-reputation") || "0");
      var repB = parseFloat(b.getAttribute("data-sort-reputation") || "0");
      if (repB !== repA) return repB - repA;

      var popA = parseFloat(a.getAttribute("data-sort-user-popularity") || "0");
      var popB = parseFloat(b.getAttribute("data-sort-user-popularity") || "0");
      if (popB !== popA) return popB - popA;

      var timeA = parseFloat(a.getAttribute("data-sort-time") || "0");
      var timeB = parseFloat(b.getAttribute("data-sort-time") || "0");
      return timeB - timeA;
    });

    items.forEach(function (item) {
      container.appendChild(item);
    });
  }

  window.resortAfterVote = function (voteEl) {
    if (!voteEl) return;

    var sortable = voteEl.closest("[data-sort-score]");
    if (!sortable) return;

    var container = sortable.closest("[data-popularity-sort]");
    if (!container) return;

    sortable.setAttribute("data-sort-score", String(readVoteScore(voteEl)));

    sortPopularityList(container);
  };

  document.body.addEventListener("htmx:afterSwap", function (evt) {
    var target = evt.detail && evt.detail.target;
    if (!target || !target.id || target.id.indexOf("votes-") !== 0) return;
    window.resortAfterVote(target);
  });
})();
