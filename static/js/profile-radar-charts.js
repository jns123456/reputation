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

  /**
   * Zeros plotted at the exact center collapse the polygon and break fill.
   * Map zero categories to a small inner ring so spokes connect and the area fills.
   */
  function prepareRadarDisplayValues(values, bounds) {
    var hasNonZero = values.some(function (v) {
      return v !== 0;
    });
    if (!hasNonZero) {
      return values.slice();
    }

    var floor =
      bounds.min + Math.max((bounds.max - bounds.min) * 0.04, 0.05);

    return values.map(function (v) {
      return v === 0 ? floor : v;
    });
  }

  function buildDataset(label, values, actualValues, colors, bounds, allowNegative) {
    var displayValues = prepareRadarDisplayValues(values, bounds);
    return {
      label: label,
      data: displayValues,
      actualValues: actualValues,
      fill: true,
      tension: 0,
      borderWidth: 2,
      borderJoinStyle: "round",
      pointRadius: 4,
      pointHoverRadius: 6,
      backgroundColor: colors.fill,
      borderColor: colors.stroke,
      pointBackgroundColor: colors.stroke,
      pointBorderColor: "#fff",
      pointBorderWidth: 1,
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
            backdropColor: "transparent",
          },
          grid: {
            circular: false,
          },
          angleLines: {
            display: true,
          },
          pointLabels: {
            font: { size: 11 },
          },
        },
      },
      elements: {
        line: {
          fill: true,
          tension: 0,
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: function (ctx) {
              var actual = ctx.dataset.actualValues[ctx.dataIndex];
              return ctx.label + ": " + actual;
            },
          },
        },
      },
    };
  }

  function createRadarChart(canvas, dataset, values, allowNegative) {
    return new Chart(canvas, {
      type: "radar",
      data: {
        labels: dataset.labels,
        datasets: [dataset.config],
      },
      options: buildRadarOptions(values, allowNegative),
    });
  }

  function initProfileRadarCharts(config) {
    if (!window.Chart || !config) return;

    var labels = config.labels || [];
    var reputationValues = config.reputationValues || [];
    var popularityValues = config.popularityValues || [];

    var repBounds = computeRadarBounds(reputationValues, true);
    var popBounds = computeRadarBounds(popularityValues, false);

    var reputationCanvas = document.getElementById("reputation-radar-chart");
    if (reputationCanvas) {
      createRadarChart(
        reputationCanvas,
        {
          labels: labels,
          config: buildDataset(
            "Reputation",
            reputationValues,
            reputationValues,
            {
              fill: "rgba(5, 150, 105, 0.25)",
              stroke: "rgb(5, 150, 105)",
            },
            repBounds,
            true
          ),
        },
        reputationValues,
        true
      );
    }

    var popularityCanvas = document.getElementById("popularity-radar-chart");
    if (popularityCanvas) {
      createRadarChart(
        popularityCanvas,
        {
          labels: labels,
          config: buildDataset(
            "Popularity",
            popularityValues,
            popularityValues,
            {
              fill: "rgba(217, 119, 6, 0.25)",
              stroke: "rgb(217, 119, 6)",
            },
            popBounds,
            false
          ),
        },
        popularityValues,
        false
      );
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
