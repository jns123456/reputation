document.addEventListener("alpine:init", function () {
  var i18n = window.MONETIZE_PAGE_I18N || {};

  Alpine.store("monetizeNav", {
    scrollProgress: 0,
    activeSection: "hero",
    sections: i18n.sections || [
      { id: "hero", label: "Start" },
      { id: "value", label: "Why" },
      { id: "estimate", label: "Earnings" },
      { id: "network", label: "Growth" },
      { id: "creators", label: "Creators" },
      { id: "trust", label: "Trust" },
      { id: "tools", label: "Tools" },
      { id: "cta", label: "Go" },
    ],
    scrollTo: function (id) {
      var el = document.getElementById("monetize-" + id);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    },
  });

  Alpine.data("monetizePage", function () {
    var subscriberSteps = [50, 100, 200, 400, 800, 2000, 5000, 10000, 50000];
    var priceSteps = [5, 7, 10, 15, 30, 75];

    return {
      subscriberIndex: 3,
      priceIndex: 0,
      creatorShare: 0.9,
      perMonthLabel: i18n.perMonthLabel || "per month",
      subscriberSteps: subscriberSteps,
      priceSteps: priceSteps,
      get subscribers() {
        return subscriberSteps[this.subscriberIndex];
      },
      get monthlyPrice() {
        return priceSteps[this.priceIndex];
      },
      get estimatedEarnings() {
        var gross = this.subscribers * this.monthlyPrice * this.creatorShare;
        return Math.round(gross).toLocaleString();
      },
      formatSubscribers: function (n) {
        if (n >= 1000) {
          return (n / 1000).toLocaleString() + "k";
        }
        return String(n);
      },
      init: function () {
        var self = this;
        this._onScroll = function () {
          self.updateScrollState();
        };
        window.addEventListener("scroll", this._onScroll, { passive: true });
        this.updateScrollState();
      },
      updateScrollState: function () {
        var nav = Alpine.store("monetizeNav");
        var doc = document.documentElement;
        var scrollTop = window.scrollY || doc.scrollTop;
        var maxScroll = doc.scrollHeight - window.innerHeight;
        nav.scrollProgress = maxScroll > 0 ? Math.min(1, scrollTop / maxScroll) : 0;

        var ids = nav.sections.map(function (s) {
          return s.id;
        });
        var current = ids[0];
        for (var i = 0; i < ids.length; i++) {
          var el = document.getElementById("monetize-" + ids[i]);
          if (el && el.getBoundingClientRect().top <= window.innerHeight * 0.35) {
            current = ids[i];
          }
        }
        nav.activeSection = current;
      },
      scrollTo: function (id) {
        Alpine.store("monetizeNav").scrollTo(id);
      },
    };
  });
});
