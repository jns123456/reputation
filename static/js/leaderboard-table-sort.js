(function () {
  function sortValue(row, key) {
    var raw = row.getAttribute("data-sort-" + key);
    if (raw === null || raw === "") {
      return Number.NEGATIVE_INFINITY;
    }
    var num = parseFloat(raw);
    return Number.isFinite(num) ? num : Number.NEGATIVE_INFINITY;
  }

  function updateRankCells(tbody) {
    var rank = 0;
    Array.prototype.forEach.call(tbody.querySelectorAll("[data-leaderboard-row]"), function (row) {
      var rankCell = row.querySelector("[data-leaderboard-rank]");
      if (!rankCell) return;
      if (row.getAttribute("data-leaderboard-qualifies") === "false") {
        rankCell.textContent = "—";
        return;
      }
      rank += 1;
      rankCell.textContent = String(rank);
    });
  }

  function setActiveHeader(table, key) {
    Array.prototype.forEach.call(table.querySelectorAll("[data-leaderboard-sort]"), function (button) {
      var isActive = button.getAttribute("data-leaderboard-sort") === key;
      button.classList.toggle("is-active", isActive);
      button.setAttribute("aria-sort", isActive ? "descending" : "none");
    });
  }

  function sortTable(table, key) {
    var tbody = table.querySelector("tbody");
    if (!tbody) return;

    var rows = Array.prototype.slice.call(tbody.querySelectorAll("[data-leaderboard-row]"));
    if (rows.length < 2) return;

    rows.sort(function (a, b) {
      return sortValue(b, key) - sortValue(a, key);
    });

    rows.forEach(function (row) {
      tbody.appendChild(row);
    });
    updateRankCells(tbody);
    setActiveHeader(table, key);
  }

  function initTable(table) {
    var defaultKey = table.getAttribute("data-default-sort") || "rep-per-forecast";
    sortTable(table, defaultKey);

    Array.prototype.forEach.call(table.querySelectorAll("[data-leaderboard-sort]"), function (button) {
      button.addEventListener("click", function () {
        sortTable(table, button.getAttribute("data-leaderboard-sort"));
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-leaderboard-table]").forEach(initTable);
  });
})();
