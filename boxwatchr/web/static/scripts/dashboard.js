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

  function loadFolders() {
    fetch("/api/stats/folders")
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        var loading = document.getElementById("folder-loading");
        var list = document.getElementById("folder-list");
        var empty = document.getElementById("folder-empty");

        if (!data || !data.folders || data.folders.length === 0) {
          if (loading) loading.classList.add("d-none");
          if (empty) empty.classList.remove("d-none");
          return;
        }

        var tbody = document.getElementById("folder-tbody");
        data.folders.forEach(function (f) {
          var tr = document.createElement("tr");
          var nameCell = document.createElement("td");
          nameCell.textContent = f.name;
          if (f.is_watched) {
            var badge = document.createElement("span");
            badge.className = "badge text-bg-primary ms-2";
            badge.textContent = "watched";
            nameCell.appendChild(badge);
          }
          var imapCell = document.createElement("td");
          imapCell.textContent = f.imap_count !== null && f.imap_count !== undefined ? f.imap_count : "—";
          var countCell = document.createElement("td");
          countCell.textContent = f.email_count;
          var linkCell = document.createElement("td");
          if (f.email_count > 0) {
            var a = document.createElement("a");
            a.href = "/emails?folder=" + encodeURIComponent(f.name);
            a.className = "small";
            a.textContent = "View emails \u2192";
            linkCell.appendChild(a);
          }
          tr.appendChild(nameCell);
          tr.appendChild(imapCell);
          tr.appendChild(countCell);
          tr.appendChild(linkCell);
          tbody.appendChild(tr);
        });

        if (loading) loading.classList.add("d-none");
        list.classList.remove("d-none");
      })
      .catch(function () {
        var loading = document.getElementById("folder-loading");
        if (loading) loading.textContent = "Failed to load folders.";
      });
  }

  function loadHourlyStats() {
    fetch("/api/stats/hourly")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.hourly && data.hourly.length > 0) {
          lineChart(
            "chart-hourly-volume",
            data.hourly.map(function (d) { return d.hour.split(" ")[1] || d.hour; }),
            data.hourly.map(function (d) { return d.count; }),
            "Emails/hour"
          );
        }
      })
      .catch(function (err) { console.error("Failed to load hourly stats:", err); });
  }

  function loadRspamdSymbols() {
    fetch("/api/stats/rspamd-symbols")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var loading = document.getElementById("rspamd-symbols-loading");
        var list = document.getElementById("rspamd-symbols-list");
        var empty = document.getElementById("rspamd-symbols-empty");
        if (!data.symbols || data.symbols.length === 0) {
          if (loading) loading.classList.add("d-none");
          if (empty) empty.classList.remove("d-none");
          return;
        }
        var tbody = document.getElementById("rspamd-symbols-tbody");
        data.symbols.forEach(function (sym) {
          var tr = document.createElement("tr");
          var nameCell = document.createElement("td");
          nameCell.className = "small font-monospace";
          nameCell.textContent = sym.symbol;
          var countCell = document.createElement("td");
          countCell.className = "small";
          countCell.textContent = sym.count;
          var scoreCell = document.createElement("td");
          scoreCell.className = "small";
          var avg = Number(sym.avg_score).toFixed(2);
          scoreCell.textContent = avg;
          if (Number(avg) > 0) scoreCell.classList.add("text-danger");
          else if (Number(avg) < 0) scoreCell.classList.add("text-success");
          tr.appendChild(nameCell);
          tr.appendChild(countCell);
          tr.appendChild(scoreCell);
          tbody.appendChild(tr);
        });
        if (loading) loading.classList.add("d-none");
        list.classList.remove("d-none");
      })
      .catch(function (err) {
        console.error("Failed to load rspamd symbols:", err);
        var loading = document.getElementById("rspamd-symbols-loading");
        if (loading) loading.textContent = "Failed to load symbols.";
      });
  }

  loadHourlyStats();
  loadRspamdSymbols();
  loadTimeline();
  loadTopSenders();
  loadFolders();
})();
