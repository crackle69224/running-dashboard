const ZONE_COLORS = window.ZONE_COLORS || ["#3a4a63", "#5b8cf7", "#46c98e", "#f5b942", "#f25c54"];
const MAX_HR = window.MAX_HR || 196;
const IS_ADMIN = window.IS_ADMIN || false;

let charts = {};

async function apiFetch(url, options) {
  const res = await fetch(url, options);
  if (res.status === 401) {
    window.location.href = "/login";
    throw new Error("Not authenticated");
  }
  return res;
}

function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) +
    " · " + d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function zoneSegments(run) {
  return [1, 2, 3, 4, 5].map(i => ({
    pct: run[`zone${i}_pct`] || 0,
    color: ZONE_COLORS[i - 1],
  }));
}

function runCard(run) {
  const segs = zoneSegments(run);
  const ownerTag = (IS_ADMIN && run.owner_email) ? `<div class="owner-tag">${run.owner_email}</div>` : "";
  return `
    <div class="run-card" data-id="${run.id}">
      ${ownerTag}
      <div class="run-date">${fmtDate(run.start_time)}</div>
      <div class="run-stats">
        <div class="metric"><div class="m-label">Distance</div><div class="m-value">${(run.distance_km ?? 0).toFixed(2)}<span style="font-size:12px;color:var(--text-dim)"> km</span></div></div>
        <div class="metric"><div class="m-label">Moving Time</div><div class="m-value">${(run.moving_time_min ?? 0).toFixed(1)}<span style="font-size:12px;color:var(--text-dim)"> min</span></div></div>
        <div class="metric"><div class="m-label">Avg HR</div><div class="m-value">${run.avg_hr ?? "—"}<span style="font-size:12px;color:var(--text-dim)"> bpm</span></div></div>
        <div class="metric"><div class="m-label">Max HR</div><div class="m-value">${run.max_hr ?? "—"}<span style="font-size:12px;color:var(--text-dim)"> bpm</span></div></div>
      </div>
      <div class="zone-bar">
        ${segs.map(s => `<div class="seg" style="width:${s.pct}%;background:${s.color}"></div>`).join("")}
      </div>
    </div>
  `;
}

function statBox(label, value, unit) {
  return `<div class="stat-box"><div class="label">${label}</div><div class="value">${value}<span class="unit">${unit}</span></div></div>`;
}

async function loadRuns() {
  const res = await apiFetch("/api/runs");
  const runs = await res.json();
  const grid = document.getElementById("runsGrid");

  if (runs.length === 0) {
    grid.innerHTML = `<div class="empty-state">No runs yet. Upload a .FIT file to get started.</div>`;
  } else {
    grid.innerHTML = runs.map(runCard).join("");
    grid.querySelectorAll(".run-card").forEach(el => {
      el.addEventListener("click", () => openRunModal(el.dataset.id));
    });
  }

  renderSummary(runs);
  return runs;
}

function renderSummary(runs) {
  const summaryRow = document.getElementById("summaryRow");
  if (runs.length === 0) {
    summaryRow.innerHTML = "";
    return;
  }
  const totalDist = runs.reduce((s, r) => s + (r.distance_km || 0), 0);
  const avgHr = runs.filter(r => r.avg_hr).reduce((s, r) => s + r.avg_hr, 0) / (runs.filter(r => r.avg_hr).length || 1);
  const avgZone2 = runs.reduce((s, r) => s + (r.zone2_pct || 0), 0) / runs.length;

  summaryRow.innerHTML = [
    statBox("Total Runs", runs.length, ""),
    statBox("Total Distance", totalDist.toFixed(1), "km"),
    statBox("Avg HR (all runs)", avgHr.toFixed(0), "bpm"),
    statBox("Avg Zone 2 %", avgZone2.toFixed(0), "%"),
  ].join("");
}

async function loadTrends() {
  const res = await apiFetch("/api/trends");
  const data = await res.json();
  const labels = data.labels.map(fmtDate);

  renderLineChart("avgHrChart", labels, data.avg_hr, "Avg HR", "#5b8cf7");
  renderLineChart("zone2Chart", labels, data.zone2_pct, "Zone 2 %", "#46c98e");
  renderZoneStack(data.labels);
}

function renderLineChart(canvasId, labels, values, label, color) {
  const ctx = document.getElementById(canvasId);
  if (charts[canvasId]) charts[canvasId].destroy();
  charts[canvasId] = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [{
        label,
        data: values,
        borderColor: color,
        backgroundColor: color + "33",
        fill: true,
        tension: 0.3,
        pointRadius: 3,
      }],
    },
    options: chartOptions(),
  });
}

async function renderZoneStack(rawLabels) {
  const res = await apiFetch("/api/runs");
  const runs = (await res.json()).slice().sort((a, b) => (a.start_time || "").localeCompare(b.start_time || ""));
  const labels = runs.map(r => fmtDate(r.start_time));

  const datasets = [1, 2, 3, 4, 5].map(i => ({
    label: `Zone ${i}`,
    data: runs.map(r => r[`zone${i}_pct`] || 0),
    backgroundColor: ZONE_COLORS[i - 1],
  }));

  const ctx = document.getElementById("zoneStackChart");
  if (charts.zoneStackChart) charts.zoneStackChart.destroy();
  charts.zoneStackChart = new Chart(ctx, {
    type: "bar",
    data: { labels, datasets },
    options: {
      indexAxis: "y",
      responsive: true,
      scales: {
        x: { stacked: true, max: 100, ticks: { color: "#8b93a3" }, grid: { color: "#1f2530" } },
        y: { stacked: true, ticks: { color: "#8b93a3" }, grid: { display: false } },
      },
      plugins: { legend: { labels: { color: "#e7eaf0" } } },
    },
  });
}

function chartOptions() {
  return {
    responsive: true,
    plugins: { legend: { display: false } },
    scales: {
      x: { ticks: { color: "#8b93a3" }, grid: { color: "#1f2530" } },
      y: { ticks: { color: "#8b93a3" }, grid: { color: "#1f2530" } },
    },
  };
}

async function openRunModal(id) {
  const res = await apiFetch(`/api/runs/${id}`);
  const run = await res.json();
  const modal = document.getElementById("runModal");
  const body = document.getElementById("modalBody");

  const segs = zoneSegments(run);
  body.innerHTML = `
    <div class="modal-title">${fmtDate(run.start_time)}</div>
    <div class="modal-sub">${run.filename}</div>
    <div class="run-stats" style="grid-template-columns:repeat(4,1fr);margin-bottom:18px;">
      <div class="metric"><div class="m-label">Distance</div><div class="m-value">${(run.distance_km ?? 0).toFixed(2)} km</div></div>
      <div class="metric"><div class="m-label">Moving Time</div><div class="m-value">${(run.moving_time_min ?? 0).toFixed(1)} min</div></div>
      <div class="metric"><div class="m-label">Avg HR</div><div class="m-value">${run.avg_hr ?? "—"} bpm</div></div>
      <div class="metric"><div class="m-label">Max HR</div><div class="m-value">${run.max_hr ?? "—"} bpm</div></div>
    </div>
    <div class="zone-bar" style="height:14px;margin-bottom:8px;">
      ${segs.map(s => `<div class="seg" style="width:${s.pct}%;background:${s.color}"></div>`).join("")}
    </div>
    <div class="zone-legend">
      ${segs.map((s, i) => `<div class="lg-item"><span class="dot" style="background:${s.color}"></span>Zone ${i + 1}: ${s.pct}%</div>`).join("")}
    </div>
    <h3 style="margin-top:24px;font-size:13px;color:var(--text-dim);text-transform:uppercase;">HR over Distance</h3>
    <canvas id="hrDistChart" height="180"></canvas>
    <button id="deleteRunBtn" style="margin-top:18px;background:none;border:1px solid var(--z5);color:var(--z5);padding:8px 14px;border-radius:6px;cursor:pointer;font-family:var(--sans);font-size:13px;">Delete this run</button>
  `;

  modal.classList.remove("hidden");

  const points = run.records.filter(r => r.heart_rate != null && r.distance_km != null);
  const ctx = document.getElementById("hrDistChart");
  if (charts.hrDistChart) charts.hrDistChart.destroy();
  charts.hrDistChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: points.map(p => p.distance_km.toFixed(2)),
      datasets: [{
        label: "Heart Rate",
        data: points.map(p => p.heart_rate),
        borderColor: "#5b8cf7",
        backgroundColor: "#5b8cf733",
        pointRadius: 0,
        borderWidth: 1.5,
        fill: true,
        tension: 0.15,
      }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { title: { display: true, text: "Distance (km)", color: "#8b93a3" }, ticks: { color: "#8b93a3", maxTicksLimit: 10 }, grid: { color: "#1f2530" } },
        y: { title: { display: true, text: "HR (bpm)", color: "#8b93a3" }, ticks: { color: "#8b93a3" }, grid: { color: "#1f2530" } },
      },
    },
  });

  document.getElementById("deleteRunBtn").onclick = async () => {
    if (!confirm("Delete this run permanently?")) return;
    await apiFetch(`/api/runs/${id}`, { method: "DELETE" });
    modal.classList.add("hidden");
    await refreshAll();
  };
}

document.getElementById("closeModal").addEventListener("click", () => {
  document.getElementById("runModal").classList.add("hidden");
});
document.getElementById("runModal").addEventListener("click", (e) => {
  if (e.target.id === "runModal") e.target.classList.add("hidden");
});

document.getElementById("uploadBtn").addEventListener("click", () => {
  document.getElementById("fitInput").click();
});

document.getElementById("logoutBtn").addEventListener("click", async () => {
  await fetch("/api/logout", { method: "POST" });
  window.location.href = "/login";
});

document.getElementById("fitInput").addEventListener("change", async (e) => {
  const files = Array.from(e.target.files || []);
  if (files.length === 0) return;
  const status = document.getElementById("uploadStatus");
  status.textContent = `Uploading ${files.length} file(s)…`;
  status.className = "upload-status";

  const formData = new FormData();
  files.forEach(f => formData.append("files", f));

  try {
    const res = await apiFetch("/api/upload", { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Upload failed");

    const uploaded = data.uploaded || [];
    const errors = data.errors || [];

    if (uploaded.length && !errors.length) {
      status.textContent = `Added ${uploaded.length} run(s)`;
      status.className = "upload-status success";
    } else if (uploaded.length && errors.length) {
      status.textContent = `Added ${uploaded.length} run(s), ${errors.length} failed`;
      status.className = "upload-status error";
    } else {
      status.textContent = errors.map(e => e.error).join("; ") || "Upload failed";
      status.className = "upload-status error";
    }
    await refreshAll();
  } catch (err) {
    status.textContent = err.message;
    status.className = "upload-status error";
  } finally {
    e.target.value = "";
  }
});

async function refreshAll() {
  await loadRuns();
  await loadTrends();
}

refreshAll();
