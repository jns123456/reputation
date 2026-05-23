(function () {
  window.shareForumPost = function (button) {
    var url = button.getAttribute("data-share-url");
    var title = button.getAttribute("data-share-title") || "Forecast on Reputation";
    if (!url) return;

    if (navigator.share) {
      navigator.share({ title: title, url: url }).catch(function () {});
      return;
    }

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(function () {
        var original = button.getAttribute("title");
        button.setAttribute("title", "Link copied!");
        setTimeout(function () {
          button.setAttribute("title", original || "Share forecast");
        }, 2000);
      });
      return;
    }

    window.prompt("Copy this link:", url);
  };
})();
