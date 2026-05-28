(function () {
  function readChartData() {
    var node = document.getElementById("polymarket-multi-chart-data");
    if (!node) return null;
    try {
      return JSON.parse(node.textContent);
    } catch (error) {
      return null;
    }
  }

  function computeYAxisBounds(seriesList) {
    var values = [];
    seriesList.forEach(function (series) {
      (series.points || []).forEach(function (point) {
        if (typeof point.value === "number" && !isNaN(point.value)) {
          values.push(point.value);
        }
      });
    });

    if (!values.length) {
      return { min: 0, max: 100 };
    }

    var minVal = Math.min.apply(null, values);
    var maxVal = Math.max.apply(null, values);
    var range = maxVal - minVal;
    var padding = Math.max(range * 0.15, 1.5);

    if (range < 3) {
      padding = Math.max(padding, 2.5);
    }

    var min = Math.max(0, minVal - padding);
    var max = Math.min(100, maxVal + padding);

    if (max - min < 6) {
      var mid = (minVal + maxVal) / 2;
      min = Math.max(0, mid - 3);
      max = Math.min(100, mid + 3);
    }

    min = Math.floor(min * 2) / 2;
    max = Math.ceil(max * 2) / 2;
    if (max <= min) {
      max = Math.min(100, min + 5);
    }

    return { min: min, max: max };
  }

  function initPolymarketMultiCharts() {
    if (typeof Chart === "undefined") return;

    var data = readChartData();
    if (!data || !data.series || !data.series.length) return;

    document.querySelectorAll("[id^='polymarket-multi-chart-canvas-']").forEach(function (canvas) {
      if (canvas.dataset.initialized === "true") return;
      canvas.dataset.initialized = "true";

      var datasets = data.series.map(function (series) {
        var points = series.points || [];
        return {
          label: series.label,
          data: points.map(function (point) {
            return { x: point.ts, y: point.value };
          }),
          borderColor: series.color,
          backgroundColor: series.fill_color,
          borderWidth: 2,
          pointRadius: points.length > 40 ? 0 : 2,
          pointHoverRadius: 4,
          fill: false,
          tension: 0.25,
        };
      });

      var yBounds = computeYAxisBounds(data.series);

      new Chart(canvas.getContext("2d"), {
        type: "line",
        data: { datasets: datasets },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: "index", intersect: false },
          plugins: {
            legend: {
              display: true,
              position: "bottom",
              labels: {
                boxWidth: 12,
                color: "rgb(100 116 139)",
                font: { size: 11 },
              },
            },
            tooltip: {
              callbacks: {
                label: function (context) {
                  return context.dataset.label + ": " + context.parsed.y.toFixed(1) + "%";
                },
              },
            },
          },
          scales: {
            x: {
              type: "time",
              time: {
                tooltipFormat: "MMM d, yyyy",
                displayFormats: {
                  day: "MMM d",
                  week: "MMM d",
                  month: "MMM yyyy",
                },
              },
              grid: { display: false },
              ticks: {
                maxTicksLimit: 6,
                color: "rgb(100 116 139)",
                font: { size: 11 },
              },
            },
            y: {
              min: yBounds.min,
              max: yBounds.max,
              grid: { color: "rgba(148, 163, 184, 0.25)" },
              ticks: {
                maxTicksLimit: 6,
                callback: function (value) {
                  return value + "%";
                },
                color: "rgb(100 116 139)",
                font: { size: 11 },
              },
            },
          },
        },
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initPolymarketMultiCharts);
  } else {
    initPolymarketMultiCharts();
  }
})();
