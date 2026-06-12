(function () {
  var i18n = window.PROOFREP_I18N || {};

  window.copyForumPostLink = function (button) {
    var url = button.getAttribute("data-copy-url");
    if (!url) return;

    var label = button.textContent.trim();
    var copiedLabel = button.getAttribute("data-copied-label") || i18n.linkCopied || "Link copied!";

    function showCopied() {
      button.textContent = copiedLabel;
      setTimeout(function () {
        button.textContent = label;
      }, 2000);
    }

    var copyPrompt = i18n.copyLinkPrompt || "Copy this link:";
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(showCopied).catch(function () {
        window.prompt(copyPrompt, url);
      });
      return;
    }

    window.prompt(copyPrompt, url);
  };

  function sendSharePing(button) {
    var pingUrl = button.getAttribute("data-share-ping");
    if (!pingUrl || button.dataset.sharePinged) return;
    button.dataset.sharePinged = "1";

    var headers = {};
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) headers["X-CSRFToken"] = meta.content;
    fetch(pingUrl, { method: "POST", headers: headers, credentials: "same-origin" }).catch(function () {});
  }

  window.shareForumPost = function (button) {
    sendSharePing(button);

    if (window.openShareSheetFromButton) {
      window.openShareSheetFromButton(button);
      return;
    }

    var url = button.getAttribute("data-share-url");
    var title = button.getAttribute("data-share-title") || i18n.shareForecastTitle || "Forecast on PredictStamp";
    if (!url) return;

    if (navigator.share) {
      navigator.share({ title: title, url: url }).catch(function () {});
      return;
    }

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(function () {
        var original = button.getAttribute("title");
        button.setAttribute("title", i18n.linkCopied || "Link copied!");
        setTimeout(function () {
          button.setAttribute("title", original || i18n.shareForecast || "Share forecast");
        }, 2000);
      });
      return;
    }

    window.prompt(i18n.copyLinkPrompt || "Copy this link:", url);
  };
})();
