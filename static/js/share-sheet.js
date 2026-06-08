(function () {
  var i18n = window.PROOFREP_I18N || {};

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    return Promise.reject(new Error("clipboard unavailable"));
  }

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

  function socialIcon(id) {
    var icons = {
      copy:
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>',
      whatsapp:
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.435 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>',
      x:
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>',
      telegram:
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/></svg>',
      email:
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4-8 5-8-5V6l8 5 8-5v2z"/></svg>',
      more:
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7c.05-.23.09-.46.09-.7s-.04-.47-.09-.7l7.05-4.11c.54.5 1.25.81 2.04.81 1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3c0 .24.04.47.09.7L8.04 9.81C7.5 9.31 6.79 9 6 9c-1.66 0-3 1.34-3 3s1.34 3 3 3c.79 0 1.5-.31 2.04-.81l7.12 4.16c-.05.21-.08.43-.08.65 0 1.61 1.31 2.92 2.92 2.92s2.92-1.31 2.92-2.92-1.31-2.92-2.92-2.92z"/></svg>',
      forecast:
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-7 14H7v-2h5v2zm5-4H7v-2h10v2zm0-4H7V7h10v2z"/></svg>',
    };
    return icons[id] || icons.copy;
  }

  function buildChannels(options) {
    var url = options.url;
    var text = options.text || options.title || "";
    var shareLine = text ? text + " " + url : url;
    var channels = [
      {
        id: "copy",
        label: i18n.shareCopyLink || "Copy link",
        tone: "neutral",
        action: function () {
          copyText(url)
            .then(function () {
              showToast(i18n.linkCopied || "Link copied!");
            })
            .catch(function () {
              window.prompt(i18n.copyLinkPrompt || "Copy this link:", url);
            });
        },
      },
      {
        id: "whatsapp",
        label: "WhatsApp",
        tone: "whatsapp",
        action: function () {
          window.open("https://wa.me/?text=" + encodeURIComponent(shareLine), "_blank", "noopener,noreferrer");
        },
      },
      {
        id: "x",
        label: "X",
        tone: "x",
        action: function () {
          window.open(
            "https://twitter.com/intent/tweet?url=" +
              encodeURIComponent(url) +
              "&text=" +
              encodeURIComponent(text),
            "_blank",
            "noopener,noreferrer"
          );
        },
      },
      {
        id: "telegram",
        label: "Telegram",
        tone: "telegram",
        action: function () {
          window.open(
            "https://t.me/share/url?url=" + encodeURIComponent(url) + "&text=" + encodeURIComponent(text),
            "_blank",
            "noopener,noreferrer"
          );
        },
      },
      {
        id: "email",
        label: i18n.shareEmail || "Email",
        tone: "email",
        action: function () {
          window.location.href =
            "mailto:?subject=" +
            encodeURIComponent(options.title || "PredictStamp") +
            "&body=" +
            encodeURIComponent(shareLine);
        },
      },
    ];

    if (navigator.share) {
      channels.push({
        id: "more",
        label: i18n.shareMore || "More",
        tone: "more",
        action: function () {
          navigator.share({ title: options.title, text: text, url: url }).catch(function () {});
        },
      });
    }

    return channels;
  }

  function closeSheet(root) {
    if (!root || !root.parentNode) return;
    root.parentNode.removeChild(root);
    document.documentElement.classList.remove("pr-share-sheet-open");
  }

  window.openShareSheet = function (options) {
    if (!options || !options.url) return;

    var portal = document.getElementById("share-sheet-portal");
    if (!portal) return;

    closeSheet(portal.querySelector(".pr-share-sheet"));

    var sheetTitle = options.sheetTitle || i18n.shareEvent || "Share event";
    var sectionLabel = i18n.shareSection || "Share";
    var channels = buildChannels(options);
    var primaryLabel = options.primaryLabel;
    var primaryAction = options.primaryAction;

    if (!primaryLabel && options.showForecastCta) {
      primaryLabel = i18n.sharePlaceForecast || "Place a forecast";
      primaryAction = function () {
        closeSheet(portal.querySelector(".pr-share-sheet"));
        var target = document.getElementById("place-forecast");
        if (target) {
          target.scrollIntoView({ behavior: "smooth", block: "start" });
          window.setTimeout(function () {
            var focusable = target.querySelector("textarea, input, button, select");
            if (focusable) focusable.focus();
          }, 350);
        }
      };
    }

    var channelMarkup = channels
      .map(function (channel) {
        return (
          '<button type="button" class="pr-share-sheet-channel" data-channel="' +
          channel.id +
          '">' +
          '<span class="pr-share-sheet-channel-icon pr-share-sheet-channel-icon--' +
          channel.tone +
          '">' +
          socialIcon(channel.id) +
          "</span>" +
          '<span class="pr-share-sheet-channel-label">' +
          escapeHtml(channel.label) +
          "</span>" +
          "</button>"
        );
      })
      .join("");

    var primaryMarkup = "";
    if (primaryLabel && primaryAction) {
      primaryMarkup =
        '<div class="pr-share-sheet-primary-wrap">' +
        '<button type="button" class="pr-share-sheet-primary" data-share-primary>' +
        escapeHtml(primaryLabel) +
        "</button>" +
        "</div>";
    }

    var root = document.createElement("div");
    root.className = "pr-share-sheet";
    root.setAttribute("role", "dialog");
    root.setAttribute("aria-modal", "true");
    root.innerHTML =
      '<button type="button" class="pr-share-sheet-backdrop" aria-label="' +
      escapeHtml(i18n.shareClose || "Close") +
      '"></button>' +
      '<div class="pr-share-sheet-panel">' +
      '<div class="pr-share-sheet-handle" aria-hidden="true"></div>' +
      '<div class="pr-share-sheet-header">' +
      '<h2 class="pr-share-sheet-title">' +
      escapeHtml(sheetTitle) +
      "</h2>" +
      '<button type="button" class="pr-share-sheet-close" aria-label="' +
      escapeHtml(i18n.shareClose || "Close") +
      '">' +
      '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path fill="currentColor" d="M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>' +
      "</button>" +
      "</div>" +
      primaryMarkup +
      '<div class="pr-share-sheet-divider" aria-hidden="true"></div>' +
      '<p class="pr-share-sheet-section-label">' +
      escapeHtml(sectionLabel) +
      "</p>" +
      '<div class="pr-share-sheet-channels-wrap">' +
      '<div class="pr-share-sheet-channels" role="list">' +
      channelMarkup +
      "</div>" +
      "</div>" +
      "</div>";

    portal.appendChild(root);
    document.documentElement.classList.add("pr-share-sheet-open");

    var closeButtons = root.querySelectorAll(".pr-share-sheet-backdrop, .pr-share-sheet-close");
    closeButtons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        closeSheet(root);
      });
    });

    root.addEventListener("keydown", function (event) {
      if (event.key === "Escape") closeSheet(root);
    });

    channels.forEach(function (channel) {
      var button = root.querySelector('[data-channel="' + channel.id + '"]');
      if (!button) return;
      button.addEventListener("click", function () {
        channel.action();
        if (channel.id !== "copy") closeSheet(root);
      });
    });

    var primaryBtn = root.querySelector("[data-share-primary]");
    if (primaryBtn && primaryAction) {
      primaryBtn.addEventListener("click", primaryAction);
    }

    var focusTarget = primaryBtn || root.querySelector(".pr-share-sheet-close");
    if (focusTarget) focusTarget.focus();
  };

  window.openShareSheetFromButton = function (button) {
    if (!button) return;
    var url = button.getAttribute("data-share-url");
    if (!url) return;

    window.openShareSheet({
      url: url,
      title: button.getAttribute("data-share-title") || i18n.shareEventTitle || "Event on PredictStamp",
      text: button.getAttribute("data-share-text") || "",
      sheetTitle: button.getAttribute("data-share-sheet-title") || i18n.shareEvent || "Share event",
      showForecastCta: button.getAttribute("data-share-forecastable") === "true",
    });
  };
})();
