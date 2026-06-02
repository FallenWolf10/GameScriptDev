const state = {
  profiles: [],
  selectedProfileId: null,
  selectedRunId: null,
  pollTimer: null,
  runtime: null,
  autoDryRunStartedByProfileId: {},
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

async function validateSelectedProfile() {
  if (!state.selectedProfileId) return null;
  return api(`/api/profiles/${encodeURIComponent(state.selectedProfileId)}/validate`, {
    method: "POST",
  });
}

async function selectProfile(profileId, { autoDryRun = false } = {}) {
  state.selectedProfileId = profileId;
  renderProfiles();
  renderProfileSelect();
  renderProfilePackDetail();
  await refreshReadiness();
  if (!autoDryRun) return;
  if (state.autoDryRunStartedByProfileId[profileId]) return;
  state.autoDryRunStartedByProfileId[profileId] = true;
  try {
    await validateSelectedProfile();
    await refreshProfiles();
    const selectedProfile = state.profiles.find((profile) => profile.id === profileId);
    if (!selectedProfile || !selectedProfile.valid) {
      return;
    }
    await startRun("dry-run", null, { skipValidation: true });
  } catch (error) {
    console.error(error);
  }
}

async function refreshProfiles() {
  await refreshRuntimeStatus();
  const payload = await api("/api/profiles");
  state.profiles = payload.profiles || [];
  if (!state.selectedProfileId && state.profiles.length) {
    state.selectedProfileId = state.profiles[0].id;
  }
  renderProfiles();
  renderProfileSelect();
  renderProfilePackDetail();
  await refreshReadiness();
}

async function refreshRuntimeStatus() {
  const runtime = await api("/api/runtime");
  state.runtime = runtime;
  const container = $("runtime-status");
  const title = $("runtime-status-title");
  const message = $("runtime-status-message");
  const button = $("runtime-admin-button");
  container.className = "runtime-status";
  if (runtime.is_admin) {
    container.classList.add("good");
    title.textContent = "Dashboard running as administrator";
    message.textContent = "Live runs can use background input against elevated targets.";
    button.hidden = true;
    return;
  }
  container.classList.add("warn");
  title.textContent = "Dashboard not running as administrator";
  message.textContent = "Website does not add permission. Live runs still use server process privilege.";
  button.hidden = false;
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
      await selectProfile(profile.id, { autoDryRun: true });
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
  await refreshTargetPreview();
}

async function refreshTargetPreview() {
  const image = $("target-preview-image");
  const empty = $("target-preview-empty");
  const meta = $("target-preview-meta");
  if (!state.selectedProfileId) {
    image.hidden = true;
    empty.hidden = false;
    meta.textContent = "No profile selected";
    return;
  }
  try {
    const preview = await api(`/api/profiles/${encodeURIComponent(state.selectedProfileId)}/target-preview`);
    image.src = preview.data_url;
    image.hidden = false;
    empty.hidden = true;
    meta.textContent = `${preview.title} · ${preview.process_name || "unknown process"} · ${preview.width}x${preview.height}`;
  } catch (error) {
    image.hidden = true;
    image.removeAttribute("src");
    empty.hidden = false;
    empty.textContent = "Target preview unavailable";
    meta.textContent = error.message;
  }
}

function renderProfilePackDetail() {
  const target = $("profile-pack-detail");
  const profile = state.profiles.find((item) => item.id === state.selectedProfileId);
  
  // Save scroll position of existing notes if present to prevent reset
  const existingNotes = target.querySelector(".notes-preview");
  const notesScrollTop = existingNotes ? existingNotes.scrollTop : 0;
  
  target.innerHTML = "";
  if (!profile || !profile.profile_pack) {
    target.textContent = "Not a profile pack";
    target.className = "pack-detail muted";
    return;
  }
  const pack = profile.profile_pack;
  const missing = pack.missing_compatibility_checks || [];
  target.className = "pack-detail";
  target.innerHTML = `
    <dl class="compact-list">
      <div><dt>Game</dt><dd>${escapeHtml(pack.game)}</dd></div>
      <div><dt>Mode</dt><dd>${escapeHtml(pack.game_mode)}</dd></div>
      <div><dt>Detection</dt><dd>${escapeHtml(pack.detection_strategy)}</dd></div>
      <div><dt>Pack Status</dt><dd>${escapeHtml(profile.pack_status)}</dd></div>
    </dl>
    <strong>Missing Evidence</strong>
    <ul class="message-list">
      ${missing.length ? missing.map((item) => `<li>${escapeHtml(item)}</li>`).join("") : "<li>None</li>"}
    </ul>
    <strong>Known Limitations</strong>
    <ul class="message-list">
      ${(pack.known_limitations || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
    </ul>
    <strong>Notes</strong>
    <pre class="notes-preview">${escapeHtml(profile.notes || "No notes.md")}</pre>
  `;
  
  // Restore scroll position of notes preview
  const newNotes = target.querySelector(".notes-preview");
  if (newNotes) {
    newNotes.scrollTop = notesScrollTop;
  }
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

async function startRun(mode, confirmation = null, options = {}) {
  const { skipValidation = false } = options;
  if (!state.selectedProfileId) return;
  if (!skipValidation) {
    await validateSelectedProfile();
    await refreshProfiles();
  }
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

async function stopSelectedRun() {
  if (!state.selectedRunId) return;
  await api(`/api/runs/${encodeURIComponent(state.selectedRunId)}/stop`, {
    method: "POST",
  });
  await refreshRuns();
}

async function relaunchDashboardAsAdmin() {
  const payload = await api("/api/runtime/relaunch-admin", { method: "POST" });
  $("runtime-status-title").textContent = "Administrator relaunch started";
  $("runtime-status-message").textContent = payload.message || "Approve the Windows prompt, then refresh this page.";
  $("runtime-admin-button").hidden = true;
  window.setTimeout(() => window.location.reload(), 2500);
}

async function refreshRuns() {
  const payload = await api("/api/runs");
  const runs = payload.runs || [];
  $("run-count").textContent = `${runs.length} runs`;
  
  const container = $("runs");
  const scrollTop = container.scrollTop;
  
  container.innerHTML = "";
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
    container.appendChild(button);
  }
  
  container.scrollTop = scrollTop;
  
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
  const readiness = await api(`/api/runs/${encodeURIComponent(run.id)}/readiness`);
  renderRunReadiness(readiness);
  const review = await api(`/api/runs/${encodeURIComponent(run.id)}/review`);
  renderRunReview(review.timeline || []);
}

function renderArtifacts(runId, artifacts) {
  const target = $("artifacts");
  const primary = $("primary-artifact");
  target.innerHTML = "";
  primary.innerHTML = "";
  const screenshot = preferredScreenshot(artifacts);
  if (screenshot) {
    const link = document.createElement("a");
    link.id = "latest-screenshot-link";
    link.href = `/api/runs/${encodeURIComponent(runId)}/artifacts/${screenshot.relative_path}`;
    link.textContent = `Latest screenshot: ${screenshot.name}`;
    link.target = "_blank";
    primary.appendChild(link);
  } else {
    const empty = document.createElement("span");
    empty.id = "latest-screenshot-link";
    empty.className = "muted";
    empty.textContent = "Latest screenshot: none";
    primary.appendChild(empty);
  }
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

function preferredScreenshot(artifacts) {
  const screenshots = (artifacts || []).filter((artifact) => (
    String(artifact.name || "").toLowerCase().endsWith(".png")
  ));
  if (!screenshots.length) return null;
  const finalScreenshot = [...screenshots].reverse().find((artifact) => (
    String(artifact.name || "").includes("_final-state-")
      || String(artifact.name || "").startsWith("final-state-")
  ));
  return finalScreenshot || screenshots[screenshots.length - 1];
}

function renderRunReadiness(report) {
  $("run-readiness-badge").textContent = report.live_available ? "Live Ready" : "Blocked";
  $("run-readiness-badge").className = `badge ${report.live_available ? "good" : "bad"}`;
  renderMessages("run-readiness-blockers", report.blockers);
}

function renderRunReview(timeline) {
  const target = $("run-review-timeline");
  target.innerHTML = "";
  for (const event of timeline) {
    const item = document.createElement("li");
    const state = event.state ? ` state=${event.state}` : "";
    const action = event.action_type ? ` action=${event.action_type}` : "";
    const index = Number.isInteger(event.action_index) ? ` #${event.action_index}` : "";
    const summary = event.action_summary ? ` ${event.action_summary}` : "";
    const result = event.result ? ` result=${event.result}` : "";
    const reason = event.failure_reason ? ` reason=${event.failure_reason}` : "";
    item.textContent = `${event.at || ""} ${event.event || "event"}${state}${action}${index}${summary}${result}${reason}`.trim();
    target.appendChild(item);
  }
  if (!timeline.length) {
    const empty = document.createElement("li");
    empty.className = "muted";
    empty.textContent = "No review events";
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
$("dry-run-button").addEventListener("click", () => startRun("dry-run"));
$("live-run-button").addEventListener("click", () => startRun("live"));
$("stop-run-button").addEventListener("click", () => stopSelectedRun());
$("runtime-admin-button").addEventListener("click", async () => {
  try {
    await relaunchDashboardAsAdmin();
  } catch (error) {
    $("runtime-status-title").textContent = "Administrator relaunch failed";
    $("runtime-status-message").textContent = error.message;
  }
});
$("profile-select").addEventListener("change", async (event) => {
  await selectProfile(event.target.value, { autoDryRun: true });
});

refreshProfiles().then(async () => {
  await refreshRuns();
  if (state.selectedProfileId) {
    await selectProfile(state.selectedProfileId, { autoDryRun: true });
  }
});
state.pollTimer = setInterval(() => {
  refreshRuns().catch(() => {});
  refreshReadiness().catch(() => {});
  refreshRuntimeStatus().catch(() => {});
}, 1500);

// Sidebar Toggle Handler with LocalStorage Persistence
const sidebarToggle = $("sidebar-toggle");

if (sidebarToggle) {
  // Load initial sidebar collapsed state
  const isCollapsed = localStorage.getItem("sidebar-collapsed") === "true";
  if (isCollapsed) {
    document.body.classList.add("sidebar-collapsed");
  }

  sidebarToggle.addEventListener("click", () => {
    const collapsed = document.body.classList.toggle("sidebar-collapsed");
    localStorage.setItem("sidebar-collapsed", collapsed);
  });
}
