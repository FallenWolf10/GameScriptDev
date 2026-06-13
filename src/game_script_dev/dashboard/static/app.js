const state = {
  profiles: [],
  runs: [],
  selectedProfileId: null,
  selectedRunId: null,
  selectedRunSummary: null,
  pollTimer: null,
  pollCount: 0,
  runtime: null,
  autoDryRunStartedByProfileId: {},
  lastPreviewRefreshAt: 0,
  runLogOffsets: {},
  runLogLineCounts: {},
  runTimelineIndexes: {},
  lastRunsSignature: "",
  lastProfilesSignature: "",
  lastProfileSelectSignature: "",
  lastPackDetailSignature: "",
  totalRunCount: 0,
  hasActiveRun: false,
  lastRuntimeSignature: "",
  lastReadinessSignature: "",
  lastRunReadinessSignature: "",
  lastMessageSignatures: {},
};

const MAX_LOG_CHARS = 120000;
const MAX_LOG_LINES = 1500;
const MAX_VISIBLE_ARTIFACTS = 60;
const MAX_VISIBLE_TIMELINE_EVENTS = 200;
const MAX_VISIBLE_RUNS = 100;
const PREVIEW_REFRESH_INTERVAL_MS = 15000;
const ACTIVE_POLL_INTERVAL_MS = 1500;
const IDLE_POLL_INTERVAL_MS = 6000;
const IDLE_READINESS_EVERY_POLLS = 2;
const RUNTIME_REFRESH_EVERY_POLLS = 5;

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

async function fetchLogTail(runId, offset) {
  const response = await fetch(
    `/api/runs/${encodeURIComponent(runId)}/log-tail?offset=${offset}`,
  );
  const text = await response.text();
  if (!response.ok) {
    let message = text || `Request failed: ${response.status}`;
    try {
      const payload = text ? JSON.parse(text) : {};
      message = payload.error || message;
    } catch (_error) {
      // Keep plain-text error fallback.
    }
    throw new Error(message);
  }
  return {
    text,
    offset: Number(response.headers.get("X-Log-Offset") || "0"),
    next_offset: Number(response.headers.get("X-Log-Next-Offset") || "0"),
    reset: response.headers.get("X-Log-Reset") === "1",
  };
}

async function validateSelectedProfile() {
  if (!state.selectedProfileId) return null;
  return api(`/api/profiles/${encodeURIComponent(state.selectedProfileId)}/validate`, {
    method: "POST",
  });
}

async function selectProfile(profileId, { autoDryRun = false, skipInitialReadiness = false } = {}) {
  state.selectedProfileId = profileId;
  state.lastPreviewRefreshAt = 0;
  renderProfiles();
  renderProfileSelect();
  renderProfilePackDetail();
  if (!skipInitialReadiness) {
    await refreshReadiness({ includePreview: true, forcePreview: true });
  }
  if (!autoDryRun) return;
  if (state.autoDryRunStartedByProfileId[profileId]) return;
  state.autoDryRunStartedByProfileId[profileId] = true;
  try {
    const validatedProfile = await validateSelectedProfile();
    if (validatedProfile) {
      upsertProfileEntry(validatedProfile);
      renderProfiles();
      renderProfileSelect();
      renderProfilePackDetail();
    }
    const selectedProfile = state.profiles.find((profile) => profile.id === profileId);
    if (!selectedProfile || !selectedProfile.valid) {
      return;
    }
    await startRun("dry-run", null, { skipValidation: true });
  } catch (error) {
    console.error(error);
  }
}

async function refreshProfiles({ refreshReadinessAfter = true } = {}) {
  await refreshRuntimeStatus();
  const payload = await api("/api/profiles");
  state.profiles = payload.profiles || [];
  if (!state.selectedProfileId && state.profiles.length) {
    state.selectedProfileId = state.profiles[0].id;
  }
  renderProfiles();
  renderProfileSelect();
  renderProfilePackDetail();
  if (refreshReadinessAfter) {
    await refreshReadiness({ includePreview: true, forcePreview: true });
  }
}

async function refreshRuntimeStatus() {
  const runtime = await api("/api/runtime");
  const signature = JSON.stringify(runtime || {});
  if (signature === state.lastRuntimeSignature) {
    return;
  }
  state.lastRuntimeSignature = signature;
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
  const signature = JSON.stringify({
    selectedProfileId: state.selectedProfileId,
    profiles: state.profiles.map((profile) => ({
      id: profile.id,
      name: profile.name,
      path: profile.path,
      valid: profile.valid,
    })),
  });
  if (signature === state.lastProfilesSignature) {
    return;
  }
  state.lastProfilesSignature = signature;
  $("profiles").innerHTML = "";
  for (const profile of state.profiles) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.profileId = profile.id;
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
    $("profiles").appendChild(button);
  }
}

function renderProfileSelect() {
  const select = $("profile-select");
  const signature = JSON.stringify({
    selectedProfileId: state.selectedProfileId,
    profiles: state.profiles.map((profile) => ({
      id: profile.id,
      name: profile.name,
    })),
  });
  if (signature === state.lastProfileSelectSignature) {
    return;
  }
  state.lastProfileSelectSignature = signature;
  select.innerHTML = "";
  for (const profile of state.profiles) {
    const option = document.createElement("option");
    option.value = profile.id;
    option.textContent = profile.name;
    option.selected = profile.id === state.selectedProfileId;
    select.appendChild(option);
  }
}

function upsertProfileEntry(profileEntry) {
  const index = state.profiles.findIndex((profile) => profile.id === profileEntry.id);
  if (index >= 0) {
    state.profiles[index] = profileEntry;
    return;
  }
  state.profiles.push(profileEntry);
}

async function refreshReadiness({ includePreview = false, forcePreview = false } = {}) {
  if (!state.selectedProfileId) return;
  const report = await api(`/api/profiles/${encodeURIComponent(state.selectedProfileId)}/readiness`);
  const signature = JSON.stringify(report || {});
  if (signature !== state.lastReadinessSignature) {
    state.lastReadinessSignature = signature;
    $("readiness-badge").textContent = report.live_available ? "Live Ready" : "Blocked";
    $("readiness-badge").className = `badge ${report.live_available ? "good" : "bad"}`;
    $("target-status").textContent = report.target_status;
    $("resolution-status").textContent = report.resolution_status;
    $("compatibility-status").textContent = report.compatibility_status;
    renderMessages("blockers", report.blockers);
    renderMessages("warnings", report.warnings);
  }
  if (includePreview) {
    await refreshTargetPreview({ force: forcePreview });
  }
}

async function refreshTargetPreview({ force = false } = {}) {
  const image = $("target-preview-image");
  const empty = $("target-preview-empty");
  const meta = $("target-preview-meta");
  const frame = $("target-preview-frame");
  if (!state.selectedProfileId) {
    image.hidden = true;
    empty.hidden = false;
    meta.textContent = "No profile selected";
    frame.style.removeProperty("--target-preview-ratio");
    return;
  }
  const now = Date.now();
  if (!force && now - state.lastPreviewRefreshAt < PREVIEW_REFRESH_INTERVAL_MS) {
    return;
  }
  try {
    const preview = await api(`/api/profiles/${encodeURIComponent(state.selectedProfileId)}/target-preview`);
    const previewRatio = preview.height > 0 ? preview.width / preview.height : 16 / 9;
    frame.style.setProperty("--target-preview-ratio", String(Math.max(previewRatio, 16 / 9)));
    image.src = preview.data_url;
    image.hidden = false;
    empty.hidden = true;
    meta.textContent = `${preview.title} · ${preview.process_name || "unknown process"} · client ${preview.width}x${preview.height}`;
    state.lastPreviewRefreshAt = now;
  } catch (error) {
    image.hidden = true;
    image.removeAttribute("src");
    empty.hidden = false;
    empty.textContent = "Target preview unavailable";
    meta.textContent = error.message;
    frame.style.removeProperty("--target-preview-ratio");
  }
}

function renderProfilePackDetail() {
  const target = $("profile-pack-detail");
  const profile = state.profiles.find((item) => item.id === state.selectedProfileId);
  const signature = JSON.stringify({
    selectedProfileId: state.selectedProfileId,
    packStatus: profile?.pack_status || null,
    profilePack: profile?.profile_pack || null,
    notes: profile?.notes || null,
  });
  if (signature === state.lastPackDetailSignature) {
    return;
  }
  state.lastPackDetailSignature = signature;
  
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
  const normalizedMessages = messages || [];
  const signature = JSON.stringify(normalizedMessages);
  if (state.lastMessageSignatures[id] === signature) {
    return;
  }
  state.lastMessageSignatures[id] = signature;
  list.innerHTML = "";
  for (const message of normalizedMessages) {
    const item = document.createElement("li");
    item.textContent = message;
    list.appendChild(item);
  }
  if (normalizedMessages.length === 0) {
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
    const validatedProfile = await validateSelectedProfile();
    if (validatedProfile) {
      upsertProfileEntry(validatedProfile);
      renderProfiles();
      renderProfileSelect();
      renderProfilePackDetail();
    }
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
  upsertRunEntry(payload);
  renderRunCount();
  renderRunsList();
  updateStopButton();
  await refreshSelectedRunData({ force: true });
}

async function stopSelectedRun() {
  const run = getActiveStoppableRun();
  if (!run) return;
  state.selectedRunId = run.id;
  const payload = await api(`/api/runs/${encodeURIComponent(run.id)}/stop`, {
    method: "POST",
  });
  upsertRunEntry(payload);
  renderRunCount();
  renderRunsList();
  updateStopButton();
  syncSelectedRunListState();
}

async function relaunchDashboardAsAdmin() {
  const payload = await api("/api/runtime/relaunch-admin", { method: "POST" });
  $("runtime-status-title").textContent = "Administrator relaunch started";
  $("runtime-status-message").textContent = payload.message || "Approve the Windows prompt, then refresh this page.";
  $("runtime-admin-button").hidden = true;
  window.setTimeout(() => window.location.reload(), 2500);
}

async function refreshRuns() {
  const payload = await api(`/api/runs?limit=${MAX_VISIBLE_RUNS}`);
  const runs = payload.runs || [];
  const totalCount = Number(payload.total_count || runs.length);
  const previousSelectedRunId = state.selectedRunId;
  const previousHasActiveRun = state.hasActiveRun;
  state.runs = runs;
  state.totalRunCount = totalCount;
  state.hasActiveRun = runs.some((run) => isRunActive(run));
  state.selectedRunId = runs.length ? runs[0].id : null;
  renderRunCount();
  const nextSignature = runsSignature(runs);
  const listChanged = nextSignature !== state.lastRunsSignature;
  state.lastRunsSignature = nextSignature;

  if (listChanged || previousSelectedRunId !== state.selectedRunId) {
    renderRunsList();
  }
  updateStopButton();
  
  const shouldRefreshSelectedRunDetail = (
    state.selectedRunId
    && (
      listChanged
      || previousSelectedRunId !== state.selectedRunId
      || state.hasActiveRun
      || previousHasActiveRun !== state.hasActiveRun
    )
  );

  if (shouldRefreshSelectedRunDetail) {
    await refreshSelectedRunData();
  } else if (!state.selectedRunId) {
    resetSelectedRunDetail();
  } else {
    syncSelectedRunListState();
  }
}

function renderRunsList() {
  const container = $("runs");
  const scrollTop = container.scrollTop;

  container.innerHTML = "";
  for (const run of state.runs) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.runId = run.id;
    button.className = run.id === state.selectedRunId ? "run active" : "run";
    button.innerHTML = `
      <span>
        <strong>${escapeHtml(run.profile_id)} ${escapeHtml(run.mode)}</strong>
        <small>${escapeHtml(run.started_at)} · ${escapeHtml(run.status)}</small>
      </span>
      <span class="badge ${run.status === "completed" ? "good" : run.status === "failed" ? "bad" : ""}">
        ${escapeHtml(displayResultLabel(run.final_result || run.status))}
      </span>
    `;
    container.appendChild(button);
  }

  container.scrollTop = scrollTop;
}

function renderRunCount() {
  const visibleCount = state.runs.length;
  const totalCount = Number(state.totalRunCount || visibleCount);
  $("run-count").textContent = totalCount > visibleCount
    ? `Showing latest ${visibleCount} of ${totalCount} runs`
    : `${visibleCount} runs`;
}

function upsertRunEntry(runEntry) {
  const normalized = normalizeRunListEntry(runEntry);
  const index = state.runs.findIndex((run) => run.id === normalized.id);
  if (index >= 0) {
    state.runs[index] = normalized;
  } else {
    state.runs.unshift(normalized);
    state.totalRunCount += 1;
  }
  if (state.runs.length > MAX_VISIBLE_RUNS) {
    state.runs = state.runs.slice(0, MAX_VISIBLE_RUNS);
  }
  state.hasActiveRun = state.runs.some((run) => isRunActive(run));
  state.lastRunsSignature = runsSignature(state.runs);
}

function normalizeRunListEntry(runEntry) {
  return {
    id: runEntry.id,
    profile_id: runEntry.profile_id,
    mode: runEntry.mode,
    status: runEntry.status,
    current_state: runEntry.current_state || null,
    final_result: runEntry.final_result || null,
    failure_reason: runEntry.failure_reason || null,
    started_at: runEntry.started_at,
    finished_at: runEntry.finished_at || null,
    stop_requested: Boolean(runEntry.stop_requested),
  };
}

async function refreshRunDetail() {
  await refreshSelectedRunData({ force: true });
}

async function refreshSelectedRunData({ force = false } = {}) {
  if (!state.selectedRunId) {
    resetSelectedRunDetail();
    return;
  }
  const summary = await api(`/api/runs/${encodeURIComponent(state.selectedRunId)}/summary`);
  const previous = state.selectedRunSummary;
  const runChanged = !previous || previous.id !== summary.id;
  state.selectedRunSummary = summary;

  $("selected-run").textContent = summary.id;
  $("current-state").textContent = summary.current_state || "idle";
  $("final-result").textContent = displayResultLabel(summary.final_result || summary.status);

  if (runChanged) {
    state.runLogOffsets[summary.id] = 0;
    state.runLogLineCounts[summary.id] = 0;
    state.runTimelineIndexes[summary.id] = 0;
    $("log-output").textContent = "";
    renderArtifacts(summary.id, [], 0);
    renderRunReview([], { append: false });
  }

  if (
    force
    || runChanged
    || !previous
    || previous.log_size !== summary.log_size
  ) {
    await refreshRunLog(summary, { reset: runChanged || force });
  }
  if (
    force
    || runChanged
    || !previous
    || previous.artifact_stamp !== summary.artifact_stamp
  ) {
    await refreshRunArtifacts(summary.id);
  }
  if (
    force
    || runChanged
    || !previous
    || previous.timeline_count !== summary.timeline_count
  ) {
    await refreshRunReviewDelta(summary, { reset: runChanged || force });
  }
  if (
    force
    || runChanged
    || !previous
    || previous.status !== summary.status
    || previous.current_state !== summary.current_state
  ) {
    await refreshRunReadinessForRun(summary.id);
  }
}

async function refreshRunLog(summary, { reset = false } = {}) {
  const currentOffset = reset ? 0 : (state.runLogOffsets[summary.id] || 0);
  const payload = await fetchLogTail(summary.id, currentOffset);
  const target = $("log-output");
  if (reset || payload.reset || currentOffset === 0) {
    target.textContent = payload.text || "";
    state.runLogLineCounts[summary.id] = countLines(target.textContent);
  } else if (payload.text) {
    target.textContent += payload.text;
    state.runLogLineCounts[summary.id] = (
      state.runLogLineCounts[summary.id] || 0
    ) + countLines(payload.text);
  }
  state.runLogOffsets[summary.id] = payload.next_offset || 0;
  trimLogOutput(target, summary.id);
  scrollLogToLatest(target);
}

async function refreshRunArtifacts(runId) {
  const payload = await api(`/api/runs/${encodeURIComponent(runId)}/artifacts?limit=${MAX_VISIBLE_ARTIFACTS}`);
  renderArtifacts(runId, payload.artifacts || [], payload.total_count || 0);
}

function renderArtifacts(runId, artifacts, totalCount = artifacts.length) {
  const target = $("artifacts");
  const primary = $("primary-artifact");
  target.innerHTML = "";
  primary.innerHTML = "";
  const latestArtifact = artifacts[0] || null;
  if (latestArtifact) {
    const link = document.createElement("a");
    link.id = "latest-screenshot-link";
    link.href = `/api/runs/${encodeURIComponent(runId)}/artifacts/${latestArtifact.relative_path}`;
    link.textContent = `Latest artifact: ${latestArtifact.name}`;
    link.target = "_blank";
    primary.appendChild(link);
  } else {
    const empty = document.createElement("span");
    empty.id = "latest-screenshot-link";
    empty.className = "muted";
    empty.textContent = "Latest artifact: none";
    primary.appendChild(empty);
  }
  for (const artifact of artifacts) {
    const link = document.createElement("a");
    link.href = `/api/runs/${encodeURIComponent(runId)}/artifacts/${artifact.relative_path}`;
    link.textContent = `${artifact.name} (${artifact.size} bytes)`;
    link.target = "_blank";
    target.appendChild(link);
  }
  if (totalCount > artifacts.length) {
    const summary = document.createElement("span");
    summary.className = "muted";
    summary.textContent = `Showing latest ${artifacts.length} of ${totalCount} artifacts`;
    target.appendChild(summary);
  }
  if (artifacts.length === 0) {
    const empty = document.createElement("span");
    empty.className = "muted";
    empty.textContent = "No artifacts";
    target.appendChild(empty);
  }
}

async function refreshRunReadinessForRun(runId) {
  const readiness = await api(`/api/runs/${encodeURIComponent(runId)}/readiness`);
  renderRunReadiness(readiness);
}

function renderRunReadiness(report) {
  const signature = JSON.stringify(report || {});
  if (signature === state.lastRunReadinessSignature) {
    return;
  }
  state.lastRunReadinessSignature = signature;
  $("run-readiness-badge").textContent = report.live_available ? "Live Ready" : "Blocked";
  $("run-readiness-badge").className = `badge ${report.live_available ? "good" : "bad"}`;
  renderMessages("run-readiness-blockers", report.blockers);
}

async function refreshRunReviewDelta(summary, { reset = false } = {}) {
  const totalCount = Number(summary.timeline_count || 0);
  const after = reset
    ? Math.max(0, totalCount - MAX_VISIBLE_TIMELINE_EVENTS)
    : Math.min(state.runTimelineIndexes[summary.id] || 0, totalCount);
  const review = await api(
    `/api/runs/${encodeURIComponent(summary.id)}/review?after=${after}&limit=${MAX_VISIBLE_TIMELINE_EVENTS}&include_artifacts=0`,
  );
  renderRunReview(review.timeline || [], { append: !reset && after > 0 });
  state.runTimelineIndexes[summary.id] = review.next_index || totalCount;
  trimTimeline();
}

function renderRunReview(timeline, { append = false } = {}) {
  const target = $("run-review-timeline");
  if (!append) {
    target.innerHTML = "";
  } else {
    const placeholder = target.querySelector(".muted");
    if (placeholder) {
      placeholder.remove();
    }
  }
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
  if (!target.children.length) {
    const empty = document.createElement("li");
    empty.className = "muted";
    empty.textContent = "No review events";
    target.appendChild(empty);
  }
}

function displayResultLabel(result) {
  if (result === "operator_stopped") {
    return "interrupt";
  }
  return result;
}

function getActiveStoppableRun() {
  const selectedRun = state.runs.find((run) => run.id === state.selectedRunId);
  if (isRunActive(selectedRun)) {
    return selectedRun;
  }

  const selectedProfileRun = state.runs.find((run) => (
    run.profile_id === state.selectedProfileId && isRunActive(run)
  ));
  if (selectedProfileRun) {
    return selectedProfileRun;
  }

  return state.runs.find((run) => isRunActive(run)) || null;
}

function isRunActive(run) {
  return Boolean(run) && (run.status === "queued" || run.status === "running");
}

function updateStopButton() {
  const button = $("stop-run-button");
  const run = getActiveStoppableRun();
  button.disabled = !run;
  button.textContent = run ? `Stop ${run.mode}` : "Stop";
}

function trimLogOutput(target, runId) {
  const currentLineCount = state.runLogLineCounts[runId] || 0;
  if (target.textContent.length <= MAX_LOG_CHARS && currentLineCount <= MAX_LOG_LINES) {
    return;
  }

  let text = target.textContent.slice(-MAX_LOG_CHARS);
  const firstNewline = text.indexOf("\n");
  if (firstNewline >= 0) {
    text = text.slice(firstNewline + 1);
  }
  const lines = text.split("\n");
  if (lines.length > MAX_LOG_LINES) {
    text = lines.slice(lines.length - MAX_LOG_LINES).join("\n");
  }
  target.textContent = text;
  state.runLogLineCounts[runId] = countLines(text);
}

function scrollLogToLatest(target) {
  target.scrollTop = target.scrollHeight;
}

function trimTimeline() {
  const target = $("run-review-timeline");
  while (target.children.length > MAX_VISIBLE_TIMELINE_EVENTS) {
    target.removeChild(target.firstChild);
  }
}

function resetSelectedRunDetail() {
  state.selectedRunSummary = null;
  $("selected-run").textContent = "No run selected";
  $("current-state").textContent = "idle";
  $("final-result").textContent = "none";
  $("log-output").textContent = "";
  state.runLogLineCounts = {};
  renderArtifacts("", [], 0);
  renderRunReview([], { append: false });
}

function syncSelectedRunListState() {
  const selectedRun = state.runs.find((run) => run.id === state.selectedRunId);
  if (!selectedRun) {
    resetSelectedRunDetail();
    return;
  }
  $("selected-run").textContent = selectedRun.id;
  $("current-state").textContent = selectedRun.current_state || "idle";
  $("final-result").textContent = displayResultLabel(selectedRun.final_result || selectedRun.status);
}

function runsSignature(runs) {
  return runs.map((run) => (
    `${run.id}:${run.status}:${run.current_state || ""}:${run.final_result || ""}:${run.stop_requested ? "1" : "0"}`
  )).join("|");
}

function scheduleNextPoll() {
  if (state.pollTimer !== null) {
    window.clearTimeout(state.pollTimer);
  }
  const interval = state.hasActiveRun ? ACTIVE_POLL_INTERVAL_MS : IDLE_POLL_INTERVAL_MS;
  state.pollTimer = window.setTimeout(async () => {
    state.pollCount += 1;
    try {
      await refreshRuns();
      if (state.hasActiveRun || state.pollCount % IDLE_READINESS_EVERY_POLLS === 0) {
        await refreshReadiness();
      }
      if (state.pollCount % RUNTIME_REFRESH_EVERY_POLLS === 0) {
        await refreshRuntimeStatus();
      }
    } catch (_error) {
      // Ignore transient poll failures and retry on the next scheduled cycle.
    } finally {
      scheduleNextPoll();
    }
  }, interval);
}

function countLines(text) {
  if (!text) {
    return 0;
  }
  return String(text).split("\n").length;
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
$("profiles").addEventListener("click", async (event) => {
  if (!(event.target instanceof Element)) {
    return;
  }
  const button = event.target.closest("button[data-profile-id]");
  if (!button) {
    return;
  }
  await selectProfile(button.dataset.profileId, { autoDryRun: true });
});
$("runs").addEventListener("click", async (event) => {
  if (!(event.target instanceof Element)) {
    return;
  }
  const button = event.target.closest("button[data-run-id]");
  if (!button) {
    return;
  }
  state.selectedRunId = button.dataset.runId;
  renderRunsList();
  await refreshRunDetail();
});
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
    await selectProfile(state.selectedProfileId, {
      autoDryRun: true,
      skipInitialReadiness: true,
    });
  }
});
scheduleNextPoll();

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
