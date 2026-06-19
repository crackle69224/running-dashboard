let selectedModel = null;
let pendingThresholdSelect = false;

const urlParams = new URLSearchParams(window.location.search);
const isSettingsRevisit = urlParams.get("settings") === "1";

function showScreen(n) {
  document.querySelectorAll(".onb-screen").forEach(el => {
    el.classList.toggle("active", el.dataset.screen === String(n));
  });
  window.scrollTo(0, 0);
}

if (isSettingsRevisit) {
  showScreen(2);
  document.getElementById("modelContinueBtn").textContent = "Save";
}
if (window.CURRENT_MODEL) {
  selectModelCard(window.CURRENT_MODEL);
}

document.querySelectorAll(".onb-next[data-goto]").forEach(btn => {
  btn.addEventListener("click", () => showScreen(btn.dataset.goto));
});

// --- Screen 2: model selection ---
document.querySelectorAll(".see-research").forEach(btn => {
  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    const panel = document.querySelector(`.research-panel[data-panel="${btn.dataset.research}"]`);
    panel.classList.toggle("open");
    btn.textContent = panel.classList.contains("open") ? "Hide research ▲" : "See research ▾";
  });
});

function selectModelCard(model) {
  document.querySelectorAll(".model-card").forEach(c => c.classList.toggle("selected", c.dataset.model === model));
  selectedModel = model;
  document.getElementById("modelContinueBtn").disabled = false;
}

document.querySelectorAll(".model-card").forEach(card => {
  card.addEventListener("click", (e) => {
    if (e.target.classList.contains("see-research")) return;
    const model = card.dataset.model;
    if (model === "threshold") {
      pendingThresholdSelect = true;
      document.getElementById("thresholdModal").classList.remove("hidden");
    } else {
      selectModelCard(model);
    }
  });
});

document.getElementById("closeThresholdModal").addEventListener("click", () => {
  document.getElementById("thresholdModal").classList.add("hidden");
});
document.getElementById("thresholdGoBack").addEventListener("click", () => {
  document.getElementById("thresholdModal").classList.add("hidden");
});
document.getElementById("thresholdContinueAnyway").addEventListener("click", () => {
  document.getElementById("thresholdModal").classList.add("hidden");
  selectModelCard("threshold");
});

document.getElementById("modelContinueBtn").addEventListener("click", async () => {
  if (!selectedModel) return;
  await fetch("/api/onboarding/model", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model: selectedModel }),
  });
  if (isSettingsRevisit) {
    window.location.href = "/";
  } else {
    showScreen(3);
  }
});

// --- Screen 4: goal setting ---
const daysSlider = document.getElementById("daysPerWeek");
const daysValue = document.getElementById("daysValue");
daysSlider.addEventListener("input", () => { daysValue.textContent = daysSlider.value; });

document.getElementById("goalForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const distance = document.getElementById("goalDistance").value;
  const paceMinRaw = document.getElementById("paceMin").value;
  const paceSecRaw = document.getElementById("paceSec").value;
  const paceUnit = document.getElementById("paceUnit").value;
  const daysPerWeek = parseInt(daysSlider.value, 10);

  const body = {
    distance,
    pace_unit: paceUnit,
    days_per_week: daysPerWeek,
  };
  if (paceMinRaw || paceSecRaw) {
    const mins = parseInt(paceMinRaw, 10) || 0;
    const secs = parseInt(paceSecRaw, 10) || 0;
    body.pace_minutes = mins + secs / 60;
  }

  const res = await fetch("/api/onboarding/goal", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) {
    alert(data.detail || "Something went wrong");
    return;
  }

  const resultBox = document.getElementById("goalResult");
  resultBox.classList.remove("hidden");
  let html = `
    <div class="estimate-label">Estimated timeframe</div>
    <div class="estimate-line">~${data.estimated_weeks} weeks to ${distance} at ${daysPerWeek} days/week</div>
  `;
  if (data.is_unusual) {
    html += `<div class="unusual-flag">This combination is unusual to achieve safely — typically ${distance} goals are paired with at least ${data.min_recommended_days} running days per week. The estimate above still applies, just expect it to take real consistency.</div>`;
  }
  resultBox.innerHTML = html;
  document.getElementById("finishOnboardingBtn").classList.remove("hidden");
});

document.getElementById("finishOnboardingBtn").addEventListener("click", () => {
  window.location.href = "/";
});
