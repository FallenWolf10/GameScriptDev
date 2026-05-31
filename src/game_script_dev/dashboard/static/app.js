const state = {
  profiles: [],
  selectedProfileId: null,
  selectedRunId: null,
  pollTimer: null,
};

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(payload.error || `Request failed: ${response.status}`);
  }
  return payload;
}

async function refreshProfiles() {
  const payload = await api("/api/profiles");
  state.profiles = payload.profiles || [];
  if (!state.selectedProfileId && state.profiles.length) {
    state.selectedProfileId = state.profiles[0].id;
  }
  renderProfiles();
  renderProfileSelect();
  await refreshReadiness();
}

function renderProfiles() {
  $("profiles").innerHTML = "";
  for (const profile of state.profiles) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = profile.id === state.selectedProfileId ? "row active" : "row";
    button.innerHTML = `
      <span>
        <strong>${escapeHtml(profile.name)}</strong>
        <small>${escapeHtml(profile.path)}</small>
      </span>
      <span class="badge ${profile.valid ? "good" : "bad"}">
        ${profile.valid ? "Valid" : "Invalid"}
      </span>
    `;
    button.addEventListener("click", async () => {
      state.selectedProfileId = profile.id;
      renderProfiles();
      renderProfileSelect();
      await refreshReadiness();
    });
    $("profiles").appendChild(button);
  }
}

function renderProfileSelect() {
  const select = $("profile-select");
  select.innerHTML = "";
  for (const profile of state.profiles) {
    const option = document.createElement("option");
    option.value = profile.id;
    option.textContent = profile.name;
    option.selected = profile.id === state.selectedProfileId;
    select.appendChild(option);
  }
}

async function refreshReadiness() {
  if (!state.selectedProfileId) return;
  const report = await api(`/api/profiles/${encodeURIComponent(state.selectedProfileId)}/readiness`);
  $("readiness-badge").textContent = report.live_available ? "Live Ready" : "Blocked";
  $("readiness-badge").className = `badge ${report.live_available ? "good" : "bad"}`;
  $("target-status").textContent = report.target_status;
  $("resolution-status").textContent = report.resolution_status;
  $("compatibility-status").textContent = report.compatibility_status;
  renderMessages("blockers", report.blockers);
  renderMessages("warnings", report.warnings);
}

function renderMessages(id, messages) {
  const list = $(id);
  list.innerHTML = "";
  for (const message of messages || []) {
    const item = document.createElement("li");
    item.textContent = message;
    list.appendChild(item);
  }
  if (!messages || messages.length === 0) {
    const item = document.createElement("li");
    item.className = "muted";
    item.textContent = "None";
    list.appendChild(item);
  }
}

async function startRun(mode, confirmation = null) {
  if (!state.selectedProfileId) return;
  const payload = await api("/api/runs", {
    method: "POST",
    body: JSON.stringify({
      profile_id: state.selectedProfileId,
      mode,
      confirmation,
    }),
  });
  state.selectedRunId = payload.id;
  await refreshRuns();
}

async function refreshRuns() {
  const payload = await api("/api/runs");
  const runs = payload.runs || [];
  $("run-count").textContent = `${runs.length} runs`;
  $("runs").innerHTML = "";
  for (const run of runs) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = run.id === state.selectedRunId ? "run active" : "run";
    button.innerHTML = `
      <span>
        <strong>${escapeHtml(run.profile_id)} ${escapeHtml(run.mode)}</strong>
        <small>${escapeHtml(run.started_at)} · ${escapeHtml(run.status)}</small>
      </span>
      <span class="badge ${run.status === "completed" ? "good" : run.status === "failed" ? "bad" : ""}">
        ${escapeHtml(run.final_result || run.status)}
      </span>
    `;
    button.addEventListener("click", async () => {
      state.selectedRunId = run.id;
      await refreshRunDetail();
      await refreshRuns();
    });
    $("runs").appendChild(button);
  }
  if (state.selectedRunId) {
    await refreshRunDetail();
  }
}

async function refreshRunDetail() {
  if (!state.selectedRunId) return;
  const run = await api(`/api/runs/${encodeURIComponent(state.selectedRunId)}`);
  $("selected-run").textContent = run.id;
  $("current-state").textContent = run.current_state || "idle";
  $("final-result").textContent = run.final_result || run.status;
  const logText = await fetch(`/api/runs/${encodeURIComponent(run.id)}/log`).then((r) => r.text());
  $("log-output").textContent = logText;
  const artifacts = await api(`/api/runs/${encodeURIComponent(run.id)}/artifacts`);
  renderArtifacts(run.id, artifacts.artifacts || []);
}

function renderArtifacts(runId, artifacts) {
  const target = $("artifacts");
  target.innerHTML = "";
  for (const artifact of artifacts) {
    const link = document.createElement("a");
    link.href = `/api/runs/${encodeURIComponent(runId)}/artifacts/${artifact.relative_path}`;
    link.textContent = `${artifact.name} (${artifact.size} bytes)`;
    link.target = "_blank";
    target.appendChild(link);
  }
  if (artifacts.length === 0) {
    const empty = document.createElement("span");
    empty.className = "muted";
    empty.textContent = "No artifacts";
    target.appendChild(empty);
  }
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  })[character]);
}

$("refresh-button").addEventListener("click", refreshProfiles);
$("validate-button").addEventListener("click", async () => {
  if (!state.selectedProfileId) return;
  await api(`/api/profiles/${encodeURIComponent(state.selectedProfileId)}/validate`, { method: "POST" });
  await refreshProfiles();
});
$("dry-run-button").addEventListener("click", () => startRun("dry-run"));
$("live-run-button").addEventListener("click", () => $("live-dialog").showModal());
$("confirm-live-button").addEventListener("click", async (event) => {
  event.preventDefault();
  const confirmation = $("live-confirmation").value;
  $("live-dialog").close();
  await startRun("live", confirmation);
});
$("profile-select").addEventListener("change", async (event) => {
  state.selectedProfileId = event.target.value;
  renderProfiles();
  await refreshReadiness();
});

refreshProfiles().then(refreshRuns);
state.pollTimer = setInterval(() => {
  refreshRuns().catch(() => {});
  refreshReadiness().catch(() => {});
}, 1500);
