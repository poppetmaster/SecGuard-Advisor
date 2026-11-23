#!/usr/bin/env node
import * as echarts from "echarts";

function render(option, width = 920, height = 360) {
  const chart = echarts.init(null, null, { renderer: "svg", ssr: true, width, height });
  try {
    chart.setOption(option);
    return chart.renderToSVGString();
  } finally {
    chart.dispose();
  }
}

const sample = {
  animation: false,
  xAxis: { type: "category", data: ["A", "B"] },
  yAxis: { type: "value" },
  series: [{ type: "bar", data: [1, 2] }],
};

if (process.argv.includes("--check")) {
  const svg = render(sample);
  if (!svg.includes("<svg") || !svg.includes("</svg>")) {
    console.error("ECharts SSR no produjo un SVG válido.");
    process.exit(1);
  }
  console.log(`ECharts SSR OK (${svg.length} bytes)`);
  process.exit(0);
}

let input = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => { input += chunk; });
process.stdin.on("end", () => {
  try {
    const payload = JSON.parse(input || "{}");
    const width = payload.width || 920;
    const height = payload.height || 360;
    const out = {};
    for (const [key, option] of Object.entries(payload.charts || {})) {
      out[key] = render(option, width, height);
    }
    process.stdout.write(JSON.stringify(out));
  } catch (error) {
    console.error(`No se pudieron renderizar las gráficas: ${error.message}`);
    process.exit(1);
  }
});
