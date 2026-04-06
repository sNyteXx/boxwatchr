(function () {
  "use strict";

  const COLORS = ["#5d9ee3", "#4878b0", "#2f5c8e", "#7aadd8", "#a8cce8"];
  const GRID_COLOR = "rgba(255, 255, 255, 0.05)";
  const TICK_COLOR = "rgba(255, 255, 255, 0.5)";

  const commonScales = {
    x: {
      ticks: { color: TICK_COLOR, maxRotation: 45 },
      grid: { color: GRID_COLOR },
    },
    y: {
      ticks: { color: TICK_COLOR },
      grid: { color: GRID_COLOR },
      beginAtZero: true,
    },
  };

  const commonOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: commonScales,
  };

  function lineChart(canvasId, labels, data, label) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    new Chart(ctx, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: label,
            data: data,
            borderColor: COLORS[0],
            backgroundColor: "rgba(93, 158, 227, 0.15)",
            fill: true,
            tension: 0.3,
            pointRadius: 2,
          },
        ],
      },
      options: commonOptions,
    });
  }

  function horizontalBarChart(canvasId, labels, data) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            data: data,
            backgroundColor: COLORS,
            borderWidth: 0,
          },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: {
            ticks: { color: TICK_COLOR },
            grid: { color: GRID_COLOR },
            beginAtZero: true,
          },
          y: {
            ticks: { color: TICK_COLOR },
            grid: { color: GRID_COLOR },
          },
        },
      },
    });
  }

  function stackedBarChart(canvasId, labels, datasetsMap) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    const ruleNames = Object.keys(datasetsMap);
    const datasets = ruleNames.map(function (name, i) {
      return {
        label: name,
        data: labels.map(function (d) {
          return datasetsMap[name][d] || 0;
        }),
        backgroundColor: COLORS[i % COLORS.length],
      };
    });
    new Chart(ctx, {
      type: "bar",
      data: { labels: labels, datasets: datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: ruleNames.length > 0,
            labels: { color: TICK_COLOR, boxWidth: 12 },
          },
        },
        scales: {
          x: {
            stacked: true,
            ticks: { color: TICK_COLOR, maxRotation: 45 },
            grid: { color: GRID_COLOR },
          },
          y: {
            stacked: true,
            ticks: { color: TICK_COLOR },
            grid: { color: GRID_COLOR },
            beginAtZero: true,
          },
        },
      },
    });
  }

  function loadTimeline() {
    fetch("/api/stats/timeline")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        lineChart(
          "chart-emails-per-day",
          data.emails_per_day.map(function (d) { return d.date; }),
          data.emails_per_day.map(function (d) { return d.count; }),
          "Emails"
        );

        lineChart(
          "chart-spam-trend",
          data.spam_trend.map(function (d) { return d.date; }),
          data.spam_trend.map(function (d) { return d.avg_score; }),
          "Avg Spam Score"
        );

        var dates = [];
        var rulesMap = {};
        data.rules_per_day.forEach(function (r) {
          if (dates.indexOf(r.date) === -1) dates.push(r.date);
          if (!rulesMap[r.rule_name]) rulesMap[r.rule_name] = {};
          rulesMap[r.rule_name][r.date] = r.count;
        });
        stackedBarChart("chart-rules-over-time", dates, rulesMap);
      })
      .catch(function (err) {
        console.error("Failed to load timeline stats:", err);
      });
  }

  function loadTopSenders() {
    fetch("/api/stats/top-senders")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        horizontalBarChart(
          "chart-top-senders",
          data.top_senders.map(function (d) { return d.sender; }),
          data.top_senders.map(function (d) { return d.count; })
        );

        horizontalBarChart(
          "chart-top-domains",
          data.top_domains.map(function (d) { return d.domain; }),
          data.top_domains.map(function (d) { return d.count; })
        );
      })
      .catch(function (err) {
        console.error("Failed to load top senders:", err);
      });
  }

  loadTimeline();
  loadTopSenders();
})();
