---
sidebar_label: "Download Statistics"
description: "Real-time PyPI download metrics, historical adoption trajectory, OS platform distribution, and Python version matrix for Zenzic."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Download Statistics & Ecosystem Adoption

Zenzic tracks public PyPI download metrics to provide full transparency on community adoption, operating system distribution, and Python runtime version usage. All data points are updated daily via an automated pipeline respecting PyPI Stats API netiquette.

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

<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; flex-wrap: wrap; gap: 0.5rem;">
  <span style="font-size: 0.9rem; font-weight: 600; color: var(--zz-text-subtle, #a0a0b0);">Interactive Chart View:</span>
  <div style="display: flex; gap: 0.5rem;">
    <button id="btn-chart-area" class="md-button md-button--primary" onclick="setDailyChartType('area')" style="font-size: 0.8rem; padding: 0.25rem 0.75rem; border-radius: 6px;">Area Chart</button>
    <button id="btn-chart-line" class="md-button" onclick="setDailyChartType('line')" style="font-size: 0.8rem; padding: 0.25rem 0.75rem; border-radius: 6px;">Line Chart</button>
    <button id="btn-chart-bar" class="md-button" onclick="setDailyChartType('bar')" style="font-size: 0.8rem; padding: 0.25rem 0.75rem; border-radius: 6px;">Bar Chart</button>
  </div>
</div>

<div id="pypi-chart-container" style="width: 100%; height: 380px; margin-bottom: 2rem; border-radius: 12px; background: var(--zz-surface-card, rgba(255,255,255,0.03)); border: 1px solid var(--zz-border-subtle, rgba(255,255,255,0.08)); padding: 1rem;">
  <div id="pypi-daily-chart" style="width: 100%; height: 100%;"></div>
</div>

## Ecosystem Matrix (OS & Python Versions)

<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1.5rem; margin: 1.5rem 0;">
  <div style="padding: 1.25rem; border-radius: 12px; background: var(--zz-surface-card, rgba(255,255,255,0.03)); border: 1px solid var(--zz-border-subtle, rgba(255,255,255,0.08));">
    <h3 style="margin-top: 0; font-size: 1.1rem; text-align: center; color: var(--zz-accent-purple, #a855f7);">Operating System Distribution</h3>
    <div id="pypi-os-chart" style="width: 100%; height: 280px;"></div>
  </div>
  <div style="padding: 1.25rem; border-radius: 12px; background: var(--zz-surface-card, rgba(255,255,255,0.03)); border: 1px solid var(--zz-border-subtle, rgba(255,255,255,0.08));">
    <h3 style="margin-top: 0; font-size: 1.1rem; text-align: center; color: var(--zz-accent-cyan, #06b6d4);">Python Version Matrix</h3>
    <div id="pypi-python-chart" style="width: 100%; height: 280px;"></div>
  </div>
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
(function() {
  let dailyChartInstance = null;
  let osChartInstance = null;
  let pythonChartInstance = null;
  let globalStatsData = null;
  let currentChartType = 'area';

  function getThemeColors() {
    const isDark = document.body.getAttribute("data-md-color-scheme") !== "default";
    return {
      textColor: isDark ? "#e2e8f0" : "#1e293b",
      splitLine: isDark ? "rgba(255, 255, 255, 0.08)" : "rgba(0, 0, 0, 0.08)",
      purple: "#a855f7",
      cyan: "#06b6d4",
      emerald: "#10b981",
      amber: "#f59e0b",
      pink: "#ec4899",
      blue: "#3b82f6",
      gray: "rgba(148, 163, 184, 0.5)",
      areaGradientStart: isDark ? "rgba(168, 85, 247, 0.45)" : "rgba(168, 85, 247, 0.35)",
      areaGradientEnd: isDark ? "rgba(6, 182, 212, 0.02)" : "rgba(6, 182, 212, 0.02)"
    };
  }

  window.setDailyChartType = function(type) {
    currentChartType = type;
    ["area", "line", "bar"].forEach(t => {
      const btn = document.getElementById("btn-chart-" + t);
      if (btn) {
        btn.className = t === type ? "md-button md-button--primary" : "md-button";
      }
    });
    if (globalStatsData) renderDailyChart(globalStatsData);
  };

  function renderDailyChart(data) {
    const container = document.getElementById("pypi-daily-chart");
    if (!container || typeof echarts === "undefined") return;

    if (dailyChartInstance) dailyChartInstance.dispose();
    dailyChartInstance = echarts.init(container);

    const dates = data.daily.map(item => item[0]);
    const downloads = data.daily.map(item => item[1]);
    const colors = getThemeColors();

    const seriesConfig = {
      name: "Downloads",
      data: downloads,
      symbol: "circle",
      symbolSize: 6,
      itemStyle: { color: colors.purple }
    };

    if (currentChartType === 'bar') {
      seriesConfig.type = 'bar';
      seriesConfig.barMaxWidth = 12;
      seriesConfig.itemStyle.borderRadius = [4, 4, 0, 0];
    } else {
      seriesConfig.type = 'line';
      seriesConfig.smooth = true;
      seriesConfig.lineStyle = { width: 3, color: colors.purple };
      if (currentChartType === 'area') {
        seriesConfig.areaStyle = {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: colors.areaGradientStart },
            { offset: 1, color: colors.areaGradientEnd }
          ])
        };
      }
    }

    const option = {
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(15, 23, 42, 0.9)",
        borderColor: colors.purple,
        textStyle: { color: "#f8fafc" },
        formatter: function (params) {
          const item = params[0];
          return `<strong style="color:${colors.purple}">${item.name}</strong><br/>Downloads: <strong>${item.value.toLocaleString()}</strong>`;
        }
      },
      grid: { left: "3%", right: "4%", bottom: "3%", containLabel: true },
      xAxis: {
        type: "category",
        boundaryGap: currentChartType === 'bar',
        data: dates,
        axisLabel: { color: colors.textColor, fontSize: 11 }
      },
      yAxis: {
        type: "value",
        splitLine: { lineStyle: { color: colors.splitLine } },
        axisLabel: { color: colors.textColor, fontSize: 11 }
      },
      series: [seriesConfig]
    };

    dailyChartInstance.setOption(option);
  }

  function renderOSChart(data) {
    const container = document.getElementById("pypi-os-chart");
    if (!container || !data.systems || typeof echarts === "undefined") return;

    if (osChartInstance) osChartInstance.dispose();
    osChartInstance = echarts.init(container);

    const colors = getThemeColors();
    const pieData = Object.entries(data.systems).map(([name, value]) => ({ name, value }));

    const option = {
      tooltip: {
        trigger: "item",
        backgroundColor: "rgba(15, 23, 42, 0.9)",
        borderColor: colors.purple,
        textStyle: { color: "#f8fafc" },
        formatter: "{b}: <strong>{c}</strong> ({d}%)"
      },
      color: [colors.purple, colors.cyan, colors.emerald, colors.amber, colors.gray],
      series: [
        {
          type: "pie",
          radius: ["40%", "70%"],
          avoidLabelOverlap: false,
          itemStyle: { borderRadius: 6, borderColor: "rgba(0,0,0,0.1)", borderWidth: 2 },
          label: { show: true, color: colors.textColor, fontSize: 11 },
          data: pieData
        }
      ]
    };

    osChartInstance.setOption(option);
  }

  function renderPythonChart(data) {
    const container = document.getElementById("pypi-python-chart");
    if (!container || !data.python_versions || typeof echarts === "undefined") return;

    if (pythonChartInstance) pythonChartInstance.dispose();
    pythonChartInstance = echarts.init(container);

    const colors = getThemeColors();
    const pieData = Object.entries(data.python_versions).map(([name, value]) => ({ name, value }));

    const option = {
      tooltip: {
        trigger: "item",
        backgroundColor: "rgba(15, 23, 42, 0.9)",
        borderColor: colors.cyan,
        textStyle: { color: "#f8fafc" },
        formatter: "{b}: <strong>{c}</strong> ({d}%)"
      },
      color: [colors.cyan, colors.purple, colors.emerald, colors.amber, colors.pink, colors.blue, colors.gray],
      series: [
        {
          type: "pie",
          radius: ["40%", "70%"],
          avoidLabelOverlap: false,
          itemStyle: { borderRadius: 6, borderColor: "rgba(0,0,0,0.1)", borderWidth: 2 },
          label: { show: true, color: colors.textColor, fontSize: 11 },
          data: pieData
        }
      ]
    };

    pythonChartInstance.setOption(option);
  }

  function initAllCharts() {
    fetch("../assets/data/pypi-stats.json")
      .then(response => response.json())
      .then(data => {
        globalStatsData = data;
        if (data.summary) {
          document.getElementById("kpi-total").innerText = data.summary.total_downloads.toLocaleString();
          document.getElementById("kpi-30d").innerText = data.summary.last_month.toLocaleString();
          document.getElementById("kpi-7d").innerText = data.summary.last_week.toLocaleString();
          document.getElementById("kpi-peak").innerText = data.summary.peak_daily.toLocaleString();
          document.getElementById("stats-last-updated").innerText = "Dataset last updated: " + data.last_updated + " · Source: PyPI Stats API";
        }
        renderDailyChart(data);
        renderOSChart(data);
        renderPythonChart(data);
      })
      .catch(err => {
        console.warn("Could not load PyPI stats JSON dataset:", err);
      });
  }

  function setupHooks() {
    initAllCharts();
    window.addEventListener("resize", function() {
      if (dailyChartInstance) dailyChartInstance.resize();
      if (osChartInstance) osChartInstance.resize();
      if (pythonChartInstance) pythonChartInstance.resize();
    });
  }

  if (document.readyState === "complete" || document.readyState === "interactive") {
    setupHooks();
  } else {
    document.addEventListener("DOMContentLoaded", setupHooks);
  }

  if (typeof location$ !== "undefined") {
    location$.subscribe(function() {
      setTimeout(setupHooks, 50);
    });
  }
})();
</script>
