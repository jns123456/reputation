(function () {
  var MENTION_TAIL_RE = /(?:^|[\s(\[])(@([A-Za-z0-9][A-Za-z0-9_.\-]{0,149}))$/;
  var config = window.PROOFREP_MENTION || {};
  var suggestionsUrl = config.suggestionsUrl || "";

  function getMentionContext(textarea) {
    var pos = textarea.selectionStart || 0;
    var before = textarea.value.slice(0, pos);
    var match = before.match(MENTION_TAIL_RE);
    if (!match) {
      return null;
    }
    return {
      start: pos - match[1].length,
      query: match[2] || "",
    };
  }

  function closeDropdown(state) {
    state.open = false;
    state.activeIndex = -1;
    if (state.dropdown) {
      state.dropdown.classList.add("hidden");
      state.dropdown.innerHTML = "";
    }
  }

  function setActiveItem(state, index) {
    if (!state.dropdown) {
      return;
    }
    var items = state.dropdown.querySelectorAll(".pr-mention-item");
    state.activeIndex = index;
    for (var i = 0; i < items.length; i += 1) {
      items[i].classList.toggle("is-active", i === index);
    }
    if (index >= 0 && items[index]) {
      items[index].scrollIntoView({ block: "nearest" });
    }
  }

  function insertMention(textarea, state, username) {
    var ctx = getMentionContext(textarea);
    if (!ctx) {
      closeDropdown(state);
      return;
    }
    var end = textarea.selectionStart || 0;
    var before = textarea.value.slice(0, ctx.start);
    var after = textarea.value.slice(end);
    var insertion = "@" + username + " ";
    textarea.value = before + insertion + after;
    var newPos = before.length + insertion.length;
    textarea.setSelectionRange(newPos, newPos);
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
    closeDropdown(state);
    textarea.focus();
  }

  function bindDropdown(state, textarea) {
    if (!state.dropdown) {
      return;
    }
    state.dropdown.querySelectorAll(".pr-mention-item").forEach(function (button, index) {
      button.addEventListener("mousedown", function (event) {
        event.preventDefault();
        insertMention(textarea, state, button.getAttribute("data-username"));
      });
      button.addEventListener("mouseenter", function () {
        setActiveItem(state, index);
      });
    });
    setActiveItem(state, state.dropdown.querySelector(".pr-mention-item") ? 0 : -1);
  }

  function fetchSuggestions(textarea, state) {
    if (!suggestionsUrl) {
      return;
    }
    var ctx = getMentionContext(textarea);
    if (!ctx) {
      closeDropdown(state);
      return;
    }
    state.mentionStart = ctx.start;
    state.query = ctx.query;

    if (state.debounceTimer) {
      clearTimeout(state.debounceTimer);
    }
    state.debounceTimer = setTimeout(function () {
      var url = suggestionsUrl + "?q=" + encodeURIComponent(ctx.query);
      fetch(url, { credentials: "same-origin", headers: { "X-Requested-With": "XMLHttpRequest" } })
        .then(function (response) {
          if (!response.ok) {
            throw new Error("mention suggestions failed");
          }
          return response.text();
        })
        .then(function (html) {
          if (!state.dropdown || !getMentionContext(textarea)) {
            closeDropdown(state);
            return;
          }
          state.dropdown.innerHTML = html;
          state.dropdown.classList.remove("hidden");
          state.open = true;
          bindDropdown(state, textarea);
        })
        .catch(function () {
          closeDropdown(state);
        });
    }, 180);
  }

  function onKeydown(event, textarea, state) {
    if (!state.open || !state.dropdown) {
      return;
    }
    var items = state.dropdown.querySelectorAll(".pr-mention-item");
    if (!items.length) {
      if (event.key === "Escape") {
        closeDropdown(state);
      }
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      var next = state.activeIndex + 1;
      if (next >= items.length) {
        next = 0;
      }
      setActiveItem(state, next);
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      var prev = state.activeIndex - 1;
      if (prev < 0) {
        prev = items.length - 1;
      }
      setActiveItem(state, prev);
      return;
    }
    if (event.key === "Enter" || event.key === "Tab") {
      if (state.activeIndex >= 0 && items[state.activeIndex]) {
        event.preventDefault();
        insertMention(textarea, state, items[state.activeIndex].getAttribute("data-username"));
      }
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      closeDropdown(state);
    }
  }

  function initTextarea(textarea) {
    if (!textarea || textarea.dataset.mentionAutocompleteInit === "1") {
      return;
    }
    textarea.dataset.mentionAutocompleteInit = "1";

    var wrapper = textarea.closest(".pr-mention-wrap");
    if (!wrapper) {
      wrapper = document.createElement("div");
      wrapper.className = "pr-mention-wrap";
      textarea.parentNode.insertBefore(wrapper, textarea);
      wrapper.appendChild(textarea);
    }

    var dropdown = wrapper.querySelector(".pr-mention-dropdown");
    if (!dropdown) {
      dropdown = document.createElement("div");
      dropdown.className = "pr-mention-dropdown hidden";
      wrapper.appendChild(dropdown);
    }

    var state = {
      dropdown: dropdown,
      open: false,
      activeIndex: -1,
      debounceTimer: null,
      mentionStart: -1,
      query: "",
    };

    textarea.addEventListener("input", function () {
      if (getMentionContext(textarea)) {
        fetchSuggestions(textarea, state);
      } else {
        closeDropdown(state);
      }
    });

    textarea.addEventListener("keydown", function (event) {
      onKeydown(event, textarea, state);
    });

    textarea.addEventListener("blur", function () {
      setTimeout(function () {
        closeDropdown(state);
      }, 150);
    });
  }

  function initAll(root) {
    if (!suggestionsUrl) {
      return;
    }
    (root || document).querySelectorAll("[data-mention-autocomplete]").forEach(initTextarea);
  }

  document.addEventListener("DOMContentLoaded", function () {
    initAll(document);
  });

  document.body.addEventListener("htmx:afterSwap", function (event) {
    initAll(event.target);
  });

  window.proofrepMentionAutocomplete = { initAll: initAll };
})();
