(function () {
  function computeRadarBounds(values, allowNegative) {
    var max = Math.max.apply(null, values.concat([0]));
    var min = Math.min.apply(null, values.concat([0]));

    if (max === 0 && min === 0) {
      return { min: 0, max: 10 };
    }

    var span = Math.max(Math.abs(max), Math.abs(min), 1);
    var padding = Math.ceil(span * 0.1) || 1;

    return {
      min: allowNegative && min < 0 ? min - padding : 0,
      max: max + padding,
    };
  }

  function buildRadarOptions(values, allowNegative) {
    var bounds = computeRadarBounds(values, allowNegative);
    return {
      responsive: true,
      maintainAspectRatio: true,
      scales: {
        r: {
          min: bounds.min,
          max: bounds.max,
          beginAtZero: true,
          ticks: {
            precision: 0,
            stepSize: Math.max(1, Math.ceil((bounds.max - bounds.min) / 5)),
          },
        },
      },
      plugins: {
        legend: { display: false },
      },
    };
  }

  function initProfileRadarCharts(config) {
    if (!window.Chart || !config) return;

    var labels = config.labels || [];
    var reputationValues = config.reputationValues || [];
    var popularityValues = config.popularityValues || [];

    var reputationCanvas = document.getElementById("reputation-radar-chart");
    if (reputationCanvas) {
      new Chart(reputationCanvas, {
        type: "radar",
        data: {
          labels: labels,
          datasets: [
            {
              label: "Reputation",
              data: reputationValues,
              backgroundColor: "rgba(5, 150, 105, 0.2)",
              borderColor: "rgb(5, 150, 105)",
              borderWidth: 2,
              pointBackgroundColor: "rgb(5, 150, 105)",
            },
          ],
        },
        options: buildRadarOptions(reputationValues, true),
      });
    }

    var popularityCanvas = document.getElementById("popularity-radar-chart");
    if (popularityCanvas) {
      new Chart(popularityCanvas, {
        type: "radar",
        data: {
          labels: labels,
          datasets: [
            {
              label: "Popularity",
              data: popularityValues,
              backgroundColor: "rgba(217, 119, 6, 0.2)",
              borderColor: "rgb(217, 119, 6)",
              borderWidth: 2,
              pointBackgroundColor: "rgb(217, 119, 6)",
            },
          ],
        },
        options: buildRadarOptions(popularityValues, false),
      });
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    var root = document.getElementById("profile-radar-config");
    if (!root) return;
    try {
      initProfileRadarCharts(JSON.parse(root.textContent));
    } catch (error) {
      console.error("Failed to init profile radar charts", error);
    }
  });
})();
