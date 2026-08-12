---
title: "Download Statistics & Adoption Metrics"
description: "Real-time PyPI download metrics, historical adoption trajectory, and community growth statistics for Zenzic."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Download Statistics & Adoption Metrics

Zenzic tracks public PyPI download metrics to provide full transparency on community adoption, engine usage trends, and release trajectory. All data points are updated daily via an automated, single-endpoint pipeline respecting PyPI Stats API netiquette.

<div class="zz-feature-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; margin: 1.5rem 0;">
  <div class="zz-showcase-card" style="padding: 1.25rem; border-radius: 12px; background: var(--zz-surface-card, rgba(255,255,255,0.03)); border: 1px solid var(--zz-border-subtle, rgba(255,255,255,0.08)); text-align: center;">
    <div style="font-size: 0.85rem; color: var(--zz-text-subtle, #a0a0b0); font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">Total Downloads</div>
    <div id="kpi-total" style="font-size: 2.2rem; font-weight: 800; color: var(--zz-accent-purple, #a855f7); margin-top: 0.4rem;">10,164</div>
  </div>
  <div class="zz-showcase-card" style="padding: 1.25rem; border-radius: 12px; background: var(--zz-surface-card, rgba(255,255,255,0.03)); border: 1px solid var(--zz-border-subtle, rgba(255,255,255,0.08)); text-align: center;">
    <div style="font-size: 0.85rem; color: var(--zz-text-subtle, #a0a0b0); font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">Last 30 Days</div>
    <div id="kpi-30d" style="font-size: 2.2rem; font-weight: 800; color: var(--zz-accent-cyan, #06b6d4); margin-top: 0.4rem;">3,532</div>
  </div>
  <div class="zz-showcase-card" style="padding: 1.25rem; border-radius: 12px; background: var(--zz-surface-card, rgba(255,255,255,0.03)); border: 1px solid var(--zz-border-subtle, rgba(255,255,255,0.08)); text-align: center;">
    <div style="font-size: 0.85rem; color: var(--zz-text-subtle, #a0a0b0); font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">Last 7 Days</div>
    <div id="kpi-7d" style="font-size: 2.2rem; font-weight: 800; color: var(--zz-accent-emerald, #10b981); margin-top: 0.4rem;">482</div>
  </div>
  <div class="zz-showcase-card" style="padding: 1.25rem; border-radius: 12px; background: var(--zz-surface-card, rgba(255,255,255,0.03)); border: 1px solid var(--zz-border-subtle, rgba(255,255,255,0.08)); text-align: center;">
    <div style="font-size: 0.85rem; color: var(--zz-text-subtle, #a0a0b0); font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">Peak Single Day</div>
    <div id="kpi-peak" style="font-size: 2.2rem; font-weight: 800; color: var(--zz-accent-amber, #f59e0b); margin-top: 0.4rem;">660</div>
  </div>
</div>

## Daily Download Trajectory

The chart below renders the daily PyPI download trajectory and adoption curve for the Zenzic Core package (`zenzic`).

<div id="pypi-chart-container" style="width: 100%; height: 380px; margin: 2rem 0; border-radius: 12px; background: var(--zz-surface-card, rgba(255,255,255,0.02)); border: 1px solid var(--zz-border-subtle, rgba(255,255,255,0.08)); padding: 1rem;">
  <div id="pypi-chart" style="width: 100%; height: 100%;"></div>
</div>

<p style="font-size: 0.85rem; color: var(--zz-text-subtle, #888); text-align: right;" id="stats-last-updated">
  Dataset last updated: 2026-08-12 UTC · Source: PyPI Stats API
</p>

## See Also

- [PyPI Package Registry](https://pypi.org/project/zenzic/)
- [Configuration Reference](../reference/configuration-reference.md)
- [System Architecture](../explanation/architecture.md)

<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<script>
document.addEventListener("DOMContentLoaded", function () {
  const chartDom = document.getElementById("pypi-chart");
  if (!chartDom || typeof echarts === "undefined") return;

  const myChart = echarts.init(chartDom);
  
  function getThemeColors() {
    const isDark = document.body.getAttribute("data-md-color-scheme") !== "default";
    return {
      textColor: isDark ? "#e2e8f0" : "#1e293b",
      splitLine: isDark ? "rgba(255, 255, 255, 0.08)" : "rgba(0, 0, 0, 0.08)",
      lineColor: "#a855f7",
      areaGradientStart: isDark ? "rgba(168, 85, 247, 0.45)" : "rgba(168, 85, 247, 0.35)",
      areaGradientEnd: isDark ? "rgba(6, 182, 212, 0.02)" : "rgba(6, 182, 212, 0.02)"
    };
  }

  fetch("../assets/data/pypi-stats.json")
    .then(response => response.json())
    .then(data => {
      if (data.summary) {
        document.getElementById("kpi-total").innerText = data.summary.total_downloads.toLocaleString();
        document.getElementById("kpi-30d").innerText = data.summary.last_month.toLocaleString();
        document.getElementById("kpi-7d").innerText = data.summary.last_week.toLocaleString();
        document.getElementById("kpi-peak").innerText = data.summary.peak_daily.toLocaleString();
        document.getElementById("stats-last-updated").innerText = "Dataset last updated: " + data.last_updated + " · Source: PyPI Stats API";
      }

      const dates = data.daily.map(item => item[0]);
      const downloads = data.daily.map(item => item[1]);

      const colors = getThemeColors();

      const option = {
        tooltip: {
          trigger: "axis",
          backgroundColor: "rgba(15, 23, 42, 0.9)",
          borderColor: "#a855f7",
          textStyle: { color: "#f8fafc" },
          formatter: function (params) {
            const item = params[0];
            return `<strong style="color:#a855f7;">${item.name}</strong><br/>Downloads: <strong>${item.value.toLocaleString()}</strong>`;
          }
        },
        grid: { left: "3%", right: "4%", bottom: "3%", containLabel: true },
        xAxis: {
          type: "category",
          boundaryGap: false,
          data: dates,
          axisLabel: { color: colors.textColor, fontSize: 11 }
        },
        yAxis: {
          type: "value",
          splitLine: { lineStyle: { color: colors.splitLine } },
          axisLabel: { color: colors.textColor, fontSize: 11 }
        },
        series: [
          {
            name: "Downloads",
            type: "line",
            smooth: true,
            symbol: "circle",
            symbolSize: 6,
            itemStyle: { color: colors.lineColor },
            lineStyle: { width: 3, color: colors.lineColor },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: colors.areaGradientStart },
                { offset: 1, color: colors.areaGradientEnd }
              ])
            },
            data: downloads
          }
        ]
      };

      myChart.setOption(option);
      window.addEventListener("resize", function () { myChart.resize(); });
    })
    .catch(err => {
      console.warn("Could not load PyPI stats JSON dataset:", err);
    });
});
</script>
