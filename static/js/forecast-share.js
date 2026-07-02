(function () {
  var i18n = window.PROOFREP_I18N || {};

  function showToast(message) {
    var existing = document.getElementById("pr-share-toast");
    if (existing) existing.remove();
    var toast = document.createElement("div");
    toast.id = "pr-share-toast";
    toast.className = "pr-share-toast";
    toast.setAttribute("role", "status");
    toast.textContent = message;
    document.body.appendChild(toast);
    window.setTimeout(function () {
      toast.remove();
    }, 2200);
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    return Promise.reject(new Error("clipboard unavailable"));
  }

  window.copyPredictionCardLink = function (button) {
    var url = button.getAttribute("data-copy-card-url");
    if (!url) return;
    copyText(url)
      .then(function () {
        showToast(i18n.predictionCardCopied || "Prediction card link copied!");
      })
      .catch(function () {
        window.prompt(i18n.copyLinkPrompt || "Copy this link:", url);
      });
  };

  window.copyPredictionEmbed = function (button) {
    var id = button.getAttribute("data-embed-id");
    if (!id) return;
    var origin = window.location.origin || "https://predictstamp.com";
    var html =
      '<iframe src="' +
      origin +
      "/p/" +
      id +
      '/embed/" width="400" height="520" frameborder="0" title="PredictStamp forecast" loading="lazy"></iframe>';
    copyText(html)
      .then(function () {
        showToast(i18n.embedCopied || "Embed code copied!");
      })
      .catch(function () {
        window.prompt(i18n.copyLinkPrompt || "Copy embed code:", html);
      });
  };
})();
