/*
 * Gráficas del panel de uso de IA con Apache ECharts.
 *
 * Los datos llegan como JSON del servidor. Este archivo solo construye opciones
 * de presentación, inicializa una instancia por contenedor y libera las
 * instancias cuando HTMX reemplaza el fragmento. No consulta proveedores.
 */
(function () {
  "use strict";

  if (window.__secguardUsageCharts) {
    return;
  }
  window.__secguardUsageCharts = true;

  var SELECTOR = "[data-echarts]";
  var instances = new Map();
  var resizeObserver = null;
  var reduceMotion =
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var PROVIDER_COLORS = {
    ollama: "#2563eb",
    deepseek: "#7c3aed",
    anthropic: "#ea580c",
  };
  var RESULT_COLORS = {
    approved: "#16a34a",
    failed: "#dc2626",
    blocked: "#d97706",
  };

  function payloadOf(element) {
    var script = element.querySelector("script[data-chart-data]");
    if (!script) {
      return null;
    }
    try {
      return JSON.parse(script.textContent);
    } catch (_error) {
      return null;
    }
  }

  function money(value) {
    return Number(value).toFixed(6) + " USD";
  }

  function number(value) {
    return new Intl.NumberFormat("es-CO").format(value);
  }

  function tooltip() {
    return {
      renderMode: "richText",
      confine: true,
      enterable: false,
      backgroundColor: "#0f172a",
      borderWidth: 0,
      padding: [8, 10],
      textStyle: { color: "#f8fafc", fontSize: 12 },
    };
  }

  function baseOption(extra) {
    var option = {
      animation: !reduceMotion,
      animationDuration: 280,
      animationEasing: "cubicOut",
      textStyle: { fontFamily: "inherit" },
      grid: { left: 52, right: 24, top: 58, bottom: 34, containLabel: true },
      legend: {
        top: 0,
        left: 0,
        type: "scroll",
        itemWidth: 12,
        itemHeight: 8,
        textStyle: { color: "#475569", fontSize: 11 },
      },
      toolbox: {
        right: 0,
        top: 0,
        itemSize: 14,
        iconStyle: { borderColor: "#64748b" },
        feature: {
          saveAsImage: {
            title: "Exportar PNG",
            name: "secguard-uso-ia",
            pixelRatio: 2,
            backgroundColor: "#ffffff",
          },
        },
      },
    };
    Object.keys(extra || {}).forEach(function (key) {
      option[key] = extra[key];
    });
    return option;
  }

  function categoryAxis(labels) {
    return {
      type: "category",
      data: labels,
      boundaryGap: true,
      axisTick: { show: false },
      axisLine: { lineStyle: { color: "#e2e8f0" } },
      axisLabel: { color: "#64748b", fontSize: 11, hideOverlap: true },
    };
  }

  function valueAxis(name, formatter) {
    return {
      type: "value",
      name: name,
      nameTextStyle: { color: "#64748b", fontSize: 11 },
      axisLabel: { color: "#64748b", fontSize: 11, formatter: formatter },
      splitLine: { lineStyle: { color: "#f1f5f9" } },
    };
  }

  function buildConsumptionCost(data) {
    var series = data.series.map(function (item) {
      return {
        name: item.name,
        type: "line",
        smooth: false,
        connectNulls: false,
        symbol: "circle",
        symbolSize: 6,
        lineStyle: { width: 2 },
        itemStyle: { color: item.color || PROVIDER_COLORS[item.key] },
        data: item.data.map(function (point) {
          if (point === null) {
            return null;
          }
          return { value: point.value, coverage: point.coverage };
        }),
      };
    });
    return baseOption({
      tooltip: Object.assign(tooltip(), {
        trigger: "axis",
        formatter: function (params) {
          var lines = [params[0].axisValueLabel];
          params.forEach(function (item) {
            if (item.value === null || item.value === undefined) {
              return;
            }
            var coverage = item.data && item.data.coverage ? " (" + item.data.coverage + ")" : "";
            lines.push(item.seriesName + ": " + money(item.value) + coverage);
          });
          return lines.join("\n");
        },
      }),
      xAxis: categoryAxis(data.labels),
      yAxis: valueAxis("USD", function (value) {
        return "$" + Number(value).toFixed(6);
      }),
      series: series,
    });
  }

  function buildConsumptionRequests(data) {
    var series = data.series.map(function (item) {
      return {
        name: item.name,
        type: "bar",
        stack: "total",
        barMaxWidth: 26,
        itemStyle: { color: item.color || PROVIDER_COLORS[item.key] },
        emphasis: { focus: "series" },
        data: item.data,
      };
    });
    return baseOption({
      tooltip: Object.assign(tooltip(), {
        trigger: "axis",
        formatter: function (params) {
          var total = 0;
          var lines = [params[0].axisValueLabel];
          params.forEach(function (item) {
            total += Number(item.value) || 0;
            lines.push(item.seriesName + ": " + number(item.value));
          });
          lines.push("Total: " + number(total));
          return lines.join("\n");
        },
      }),
      xAxis: categoryAxis(data.labels),
      yAxis: valueAxis("Intentos", function (value) {
        return number(value);
      }),
      series: series,
    });
  }

  function buildConsumptionTokens(data) {
    return baseOption({
      tooltip: Object.assign(tooltip(), {
        trigger: "axis",
        formatter: function (params) {
          var lines = [params[0].axisValueLabel];
          params.forEach(function (item) {
            lines.push(item.seriesName + ": " + number(item.value));
          });
          return lines.join("\n");
        },
      }),
      xAxis: categoryAxis(
        data.providers.map(function (item) {
          return item.name;
        })
      ),
      yAxis: valueAxis("Tokens", function (value) {
        return number(value);
      }),
      series: [
        {
          name: "Entrada",
          type: "bar",
          stack: "tokens",
          barMaxWidth: 42,
          itemStyle: { color: "#2563eb" },
          data: data.providers.map(function (item) {
            return item.input;
          }),
        },
        {
          name: "Salida",
          type: "bar",
          stack: "tokens",
          barMaxWidth: 42,
          itemStyle: { color: "#f59e0b" },
          data: data.providers.map(function (item) {
            return item.output;
          }),
        },
      ],
    });
  }

  function buildComparisonLatency(data) {
    return baseOption({
      tooltip: Object.assign(tooltip(), {
        trigger: "axis",
        formatter: function (params) {
          var item = params[0];
          var point = data[item.dataIndex];
          return point.name + "\n" + Number(point.seconds).toFixed(3) + " s\n" + point.coverage;
        },
      }),
      xAxis: categoryAxis(
        data.map(function (item) {
          return item.name;
        })
      ),
      yAxis: valueAxis("Segundos", function (value) {
        return Number(value).toFixed(1) + " s";
      }),
      series: [
        {
          type: "bar",
          barMaxWidth: 44,
          data: data.map(function (item) {
            return {
              value: item.seconds,
              itemStyle: { color: PROVIDER_COLORS[item.key] },
              coverage: item.coverage,
            };
          }),
          label: {
            show: true,
            position: "top",
            color: "#475569",
            fontSize: 11,
            formatter: function (params) {
              return params.value.toFixed(2) + " s";
            },
          },
        },
      ],
    });
  }

  function buildComparisonResults(data) {
    var keys = ["approved", "failed", "blocked"];
    var labels = { approved: "Aprobado", failed: "Fallido", blocked: "Bloqueado" };
    return baseOption({
      tooltip: Object.assign(tooltip(), {
        trigger: "axis",
        formatter: function (params) {
          var lines = [params[0].axisValueLabel];
          params.forEach(function (item) {
            lines.push(labels[keys[item.seriesIndex]] + ": " + number(item.value));
          });
          return lines.join("\n");
        },
      }),
      xAxis: categoryAxis(
        data.map(function (item) {
          return item.name;
        })
      ),
      yAxis: valueAxis("Escenarios", function (value) {
        return number(value);
      }),
      series: keys.map(function (key) {
        return {
          name: labels[key],
          type: "bar",
          stack: "result",
          barMaxWidth: 42,
          itemStyle: { color: RESULT_COLORS[key] },
          data: data.map(function (item) {
            return item[key];
          }),
        };
      }),
    });
  }

  function buildComparisonCost(data) {
    return baseOption({
      tooltip: Object.assign(tooltip(), {
        trigger: "axis",
        formatter: function (params) {
          var item = params[0];
          var point = data[item.dataIndex];
          return (
            point.name +
            "\n" +
            money(point.value) +
            " / escenario\n" +
            point.coverage
          );
        },
      }),
      xAxis: categoryAxis(
        data.map(function (item) {
          return item.name;
        })
      ),
      yAxis: valueAxis("USD / escenario", function (value) {
        return "$" + Number(value).toFixed(4);
      }),
      series: [
        {
          type: "bar",
          barMaxWidth: 44,
          data: data.map(function (item) {
            return {
              value: item.value,
              itemStyle: { color: PROVIDER_COLORS[item.key] },
              coverage: item.coverage,
            };
          }),
          label: {
            show: true,
            position: "top",
            color: "#475569",
            fontSize: 11,
            formatter: function (params) {
              return money(params.value);
            },
          },
        },
      ],
    });
  }

  function buildComparisonMatrix(data) {
    var providerNames = data.provider_names;
    var scenarios = data.scenarios;
    var cells = data.cells.map(function (cell) {
      return {
        value: [cell.provider_index, cell.scenario_index, cell.duration_ms || 0],
        result: cell.result,
        duration_ms: cell.duration_ms,
        model: cell.model,
        scenario: cell.scenario,
        provider: cell.provider,
        itemStyle: {
          color: RESULT_COLORS[cell.result] || "#94a3b8",
          borderColor: "#ffffff",
          borderWidth: 1,
        },
      };
    });
    return baseOption({
      animation: false,
      grid: { left: 64, right: 24, top: 24, bottom: 34, containLabel: true },
      tooltip: Object.assign(tooltip(), {
        trigger: "item",
        formatter: function (params) {
          var point = params.data;
          var duration =
            point.duration_ms === null || point.duration_ms === undefined
              ? "duración no disponible"
              : number(point.duration_ms) + " ms";
          return (
            point.scenario +
            "\n" +
            point.provider +
            " · " +
            point.model +
            "\nResultado: " +
            point.result +
            "\nDuración: " +
            duration
          );
        },
      }),
      xAxis: {
        type: "category",
        data: providerNames,
        position: "top",
        axisTick: { show: false },
        axisLine: { show: false },
        axisLabel: { color: "#475569", fontSize: 11 },
      },
      yAxis: {
        type: "category",
        data: scenarios,
        inverse: true,
        axisTick: { show: false },
        axisLine: { show: false },
        axisLabel: { color: "#475569", fontSize: 11 },
      },
      series: [
        {
          type: "heatmap",
          data: cells,
          label: {
            show: true,
            color: "#ffffff",
            fontSize: 10,
            formatter: function (params) {
              return params.data.result === "approved"
                ? "OK"
                : params.data.result === "blocked"
                  ? "BLOQ"
                  : "FALLO";
            },
          },
        },
      ],
    });
  }

  function buildOption(type, data) {
    switch (type) {
      case "consumption-cost":
        return buildConsumptionCost(data);
      case "consumption-requests":
        return buildConsumptionRequests(data);
      case "consumption-tokens":
        return buildConsumptionTokens(data);
      case "comparison-latency":
        return buildComparisonLatency(data);
      case "comparison-results":
        return buildComparisonResults(data);
      case "comparison-cost":
        return buildComparisonCost(data);
      case "comparison-matrix":
        return buildComparisonMatrix(data);
      default:
        return null;
    }
  }

  function dispose(element) {
    var chart = instances.get(element);
    if (chart) {
      chart.dispose();
      instances.delete(element);
    }
    element.removeAttribute("data-chart-ready");
    if (resizeObserver) {
      resizeObserver.unobserve(element);
    }
  }

  function initOne(element) {
    if (!window.echarts || element.getAttribute("data-chart-ready") === "true") {
      return;
    }
    var payload = payloadOf(element);
    var option = buildOption(element.getAttribute("data-echarts"), payload);
    if (!option) {
      return;
    }
    dispose(element);
    var chart = window.echarts.init(element, null, { renderer: "canvas" });
    chart.setOption(option, true);
    instances.set(element, chart);
    element.setAttribute("data-chart-ready", "true");
    if (resizeObserver) {
      resizeObserver.observe(element);
    }
  }

  function initWithin(root) {
    if (!root || !root.querySelectorAll) {
      return;
    }
    Array.prototype.forEach.call(root.querySelectorAll(SELECTOR), initOne);
  }

  function disposeWithin(root) {
    if (!root || !root.querySelectorAll) {
      return;
    }
    Array.prototype.forEach.call(root.querySelectorAll(SELECTOR), dispose);
  }

  function ensureObserver() {
    if (!window.ResizeObserver || resizeObserver) {
      return;
    }
    resizeObserver = new ResizeObserver(function (entries) {
      entries.forEach(function (entry) {
        var chart = instances.get(entry.target);
        if (chart) {
          chart.resize();
        }
      });
    });
  }

  function resizeAll() {
    instances.forEach(function (chart) {
      chart.resize();
    });
  }

  document.addEventListener("click", function (event) {
    var button = event.target.closest("[data-export-chart]");
    if (!button) {
      return;
    }
    var target = document.getElementById(button.getAttribute("data-export-chart"));
    var chart = target ? instances.get(target) : null;
    if (!chart) {
      return;
    }
    event.preventDefault();
    var link = document.createElement("a");
    link.download = "secguard-" + target.id + ".png";
    link.href = chart.getDataURL({
      type: "png",
      pixelRatio: 2,
      backgroundColor: "#ffffff",
    });
    document.body.appendChild(link);
    link.click();
    link.remove();
  });

  document.addEventListener("htmx:beforeSwap", function (event) {
    disposeWithin(event.detail && event.detail.target);
  });

  document.addEventListener("htmx:afterSettle", function () {
    // HTMX puede conservar la referencia al nodo reemplazado; se inicializa el
    // documento actual para no depender de un target detached.
    initWithin(document);
    resizeAll();
  });

  document.addEventListener("DOMContentLoaded", function () {
    ensureObserver();
    initWithin(document);
  });

  window.addEventListener("resize", function () {
    window.clearTimeout(window.__secguardUsageResize);
    window.__secguardUsageResize = window.setTimeout(resizeAll, 120);
  });

  if (document.readyState !== "loading") {
    ensureObserver();
    initWithin(document);
  }
})();
