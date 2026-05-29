(function () {
  function readChartData() {
    var node = document.getElementById("kalshi-chart-data");
    if (!node) return null;
    try {
      return JSON.parse(node.textContent);
    } catch (error) {
      return null;
    }
  }

  function initKalshiCharts() {
    if (typeof Chart === "undefined") return;

    var data = readChartData();
    if (!data || !data.values || !data.values.length) return;

    document.querySelectorAll("[id^='kalshi-chart-canvas-']").forEach(function (canvas) {
      if (canvas.dataset.initialized === "true") return;
      canvas.dataset.initialized = "true";

      var yesLabel = data.yes_label || "Yes";
      var priceSuffix = data.price_suffix || "price";
      var labels = data.labels || [];
      var values = data.values || [];

      new Chart(canvas.getContext("2d"), {
        type: "line",
        data: {
          labels: labels,
          datasets: [
            {
              label: yesLabel + " " + priceSuffix,
              data: values,
              borderColor: "rgb(5 150 105)",
              backgroundColor: "rgba(16, 185, 129, 0.12)",
              borderWidth: 2,
              pointRadius: values.length > 40 ? 0 : 2,
              pointHoverRadius: 4,
              fill: true,
              tension: 0.25,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: "index", intersect: false },
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: function (context) {
                  return yesLabel + ": " + context.parsed.y.toFixed(1) + "%";
                },
              },
            },
          },
          scales: {
            x: {
              grid: { display: false },
              ticks: {
                maxTicksLimit: 6,
                color: "rgb(100 116 139)",
                font: { size: 11 },
              },
            },
            y: {
              min: 0,
              max: 100,
              grid: { color: "rgba(148, 163, 184, 0.25)" },
              ticks: {
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
    document.addEventListener("DOMContentLoaded", initKalshiCharts);
  } else {
    initKalshiCharts();
  }
})();
