(function () {
  var PORTAL_ID = "weekly-contest-events-portal";

  function closeSheet(portal) {
    if (!portal) return;
    portal.innerHTML = "";
    document.removeEventListener("keydown", portal._weeklyContestEscapeHandler);
    delete portal._weeklyContestEscapeHandler;
  }

  function bindSheet(portal) {
    var sheet = portal.querySelector(".pr-vote-sheet");
    if (!sheet) return;

    function onClose() {
      closeSheet(portal);
    }

    portal.querySelectorAll("[data-sheet-close]").forEach(function (button) {
      button.addEventListener("click", onClose);
    });

    if (portal._weeklyContestEscapeHandler) {
      document.removeEventListener("keydown", portal._weeklyContestEscapeHandler);
    }
    portal._weeklyContestEscapeHandler = function (event) {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", portal._weeklyContestEscapeHandler);

    var closeBtn = portal.querySelector(".pr-vote-sheet-close");
    if (closeBtn) closeBtn.focus();
    if (window.refreshLucideIcons) window.refreshLucideIcons();
  }

  document.body.addEventListener("htmx:afterSwap", function (event) {
    var portal = document.getElementById(PORTAL_ID);
    if (!portal || event.detail.target !== portal) return;
    bindSheet(portal);
  });
})();
