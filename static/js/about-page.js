document.addEventListener("alpine:init", function () {
  var i18n = window.ABOUT_PAGE_I18N || {};

  Alpine.store("aboutNav", {
    scrollProgress: 0,
    activeSection: "hero",
    sections: i18n.sections || [
      { id: "hero", label: "Intro" },
      { id: "thesis", label: "Thesis" },
      { id: "proof", label: "Reputation" },
      { id: "platform", label: "Platform" },
      { id: "scores", label: "Scores" },
      { id: "leaderboards", label: "Rankings" },
      { id: "social", label: "Social" },
      { id: "future", label: "Future" },
      { id: "cta", label: "Start" },
    ],
    scrollTo: function (id) {
      var el = document.getElementById("about-" + id);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    },
  });

  Alpine.data("aboutPage", function () {
    return {
      leaderboardMode: "reputation",
      expandedPor: null,
      scoreFocus: "reputation",
      activeDomain: null,
      expandedQuestion: null,
      domains: i18n.domains || [
        "Geopolitics",
        "Sports",
        "Crypto",
        "Elections",
        "Macro",
        "Energy",
        "Tech",
        "Culture",
      ],
      questions: i18n.questions || [
        { id: "why", q: "Why do you believe this?" },
        { id: "conf", q: "How confident are you?" },
        { id: "mind", q: "Did you change your mind?" },
        { id: "early", q: "Were you early or late?" },
        { id: "age", q: "Did your reasoning age well?" },
        { id: "domain", q: "Are you right in this domain?" },
      ],
      moneyPoints: i18n.moneyPoints || [
        "Rewards capital, not necessarily insight",
        "Excludes anyone without funds to wager",
        "One lucky bet can distort the ranking",
      ],
      repPoints: i18n.repPoints || [
        "Accuracy, calibration, early conviction",
        "Performance by topic and over time",
        "Open to anyone — judgment is the entry fee",
      ],
      reputationMetrics: i18n.reputationMetrics || [
        "Accuracy",
        "Calibration",
        "Early conviction",
        "Topic expertise",
      ],
      moneyMetrics: i18n.moneyMetrics || [
        "P&L",
        "Volume traded",
        "Max drawdown",
        "Bankroll size",
      ],
      rankByPrefix: i18n.rankByPrefix || "Rank by ",
      becomeKnownForTemplate: i18n.becomeKnownForTemplate || "Become known for %(domain)s — a living map of who has good judgment.",
      forecastContextHint: i18n.forecastContextHint || "Every forecast captures context — not just yes or no, but why, when, and how confident.",
      init: function () {
        var self = this;
        this._onScroll = function () {
          self.updateScrollState();
        };
        window.addEventListener("scroll", this._onScroll, { passive: true });
        this.updateScrollState();
      },
      becomeKnownFor: function (domain) {
        if (!domain) return "";
        return (this.becomeKnownForTemplate || "").replace("%(domain)s", domain.toLowerCase());
      },
      updateScrollState: function () {
        var nav = Alpine.store("aboutNav");
        var doc = document.documentElement;
        var scrollTop = window.scrollY || doc.scrollTop;
        var maxScroll = doc.scrollHeight - window.innerHeight;
        nav.scrollProgress = maxScroll > 0 ? Math.min(1, scrollTop / maxScroll) : 0;

        var ids = nav.sections.map(function (s) { return s.id; });
        var current = ids[0];
        for (var i = 0; i < ids.length; i++) {
          var el = document.getElementById("about-" + ids[i]);
          if (el && el.getBoundingClientRect().top <= window.innerHeight * 0.35) {
            current = ids[i];
          }
        }
        nav.activeSection = current;
      },
      scrollTo: function (id) {
        Alpine.store("aboutNav").scrollTo(id);
      },
    };
  });
});
