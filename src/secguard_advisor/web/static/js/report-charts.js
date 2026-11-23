"use strict";

(function () {
  function initChart(element) {
    if (!window.echarts) return;
    var payload = element.querySelector("[data-chart-data]");
    if (!payload) return;
    var option;
    try {
      option = JSON.parse(payload.textContent || "{}");
    } catch (_error) {
      return;
    }
    var chart = window.echarts.init(element, null, { renderer: "canvas" });
    chart.setOption(option);
    window.addEventListener("resize", function () { chart.resize(); });
  }

  function start() {
    document.querySelectorAll("[data-echarts]").forEach(initChart);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
