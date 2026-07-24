const state = {
  profiles: [],
  runs: [],
  selectedProfileId: null,
  selectedRunId: null,
  selectedRunSummary: null,
  selectedReadiness: null,
  targetPreview: null,
  activeRun: null,
  activeWorkspace: "run",
  activeSelectionView: "profiles",
  activeDetailView: "readiness",
  builderDocument: null,
  builderSource: null,
  builderDraft: null,
  builderProfileId: null,
  selectedBuilderState: null,
  selectedBuilderActionIndex: null,
  actionSchema: null,
  builderAutosaveTimer: null,
  builderAutosavePromise: null,
  builderAutosavePending: false,
  builderInspectorTimer: null,
  builderInspectorPending: null,
  structuredMutationPending: false,
  createProfileIdTouched: false,
  createProfileNameTouched: false,
  pollTimer: null,
  pollCount: 0,
  runtime: null,
  lastPreviewRefreshAt: 0,
  previewStreamProfileId: null,
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
const PREVIEW_REFRESH_INTERVAL_MS = 1000;
const PREVIEW_META_REFRESH_INTERVAL_MS = 5000;
const PREVIEW_STREAM_FPS = 6;
const PREVIEW_STREAM_MAX_WIDTH = 960;
const ACTIVE_POLL_INTERVAL_MS = 1000;
const IDLE_POLL_INTERVAL_MS = 1000;
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
    const error = new Error(payload.error || `Request failed: ${response.status}`);
    error.status = response.status;
    error.payload = payload;
    throw error;
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

async function selectProfile(profileId, { skipInitialReadiness = false } = {}) {
  await flushBuilderAutosave();
  state.selectedProfileId = profileId;
  state.lastPreviewRefreshAt = 0;
  renderProfiles();
  renderProfileSelect();
  renderProfilePackDetail();
  renderBuilderProfileSummary();
  await refreshBuilderProfile();
  if (!skipInitialReadiness) {
    await refreshReadiness({ includePreview: true, forcePreview: true });
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
  renderBuilderProfileSummary();
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
  $("settings-workspace").textContent = runtime.workspace || "Unavailable";
  $("settings-logs").textContent = runtime.logs || "Unavailable";
  $("settings-server").textContent = `${runtime.host || "127.0.0.1"}:${runtime.port ?? "—"}`;
  $("settings-runtime-badge").textContent = runtime.is_admin ? "Administrator" : "Standard user";
  $("settings-runtime-badge").className = `badge ${runtime.is_admin ? "good" : "warn"}`;
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
  state.selectedReadiness = report;
  const signature = JSON.stringify(report || {});
  if (signature !== state.lastReadinessSignature) {
    state.lastReadinessSignature = signature;
    $("readiness-badge").textContent = report.live_available ? "Live Ready" : "Blocked";
    $("readiness-badge").className = `badge ${report.live_available ? "good" : "bad"}`;
    $("target-status").textContent = report.target_status;
    $("resolution-status").textContent = report.resolution_status;
    $("compatibility-status").textContent = report.compatibility_status;
    $("background-capture-status").textContent = displayBackgroundCaptureStatus(report.background_capture_status);
    renderMessages("blockers", report.blockers);
    renderMessages("warnings", report.warnings);
  }
  updateRunCommandState();
  updateOverviewAlert();
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
    stopTargetPreviewStream();
    image.hidden = true;
    image.removeAttribute("src");
    empty.hidden = false;
    empty.textContent = "No target preview";
    meta.textContent = "No profile selected";
    frame.style.removeProperty("--target-preview-ratio");
    return;
  }
  startTargetPreviewStream();
  const now = Date.now();
  if (!force && now - state.lastPreviewRefreshAt < PREVIEW_META_REFRESH_INTERVAL_MS) {
    return;
  }
  try {
    const preview = await api(`/api/profiles/${encodeURIComponent(state.selectedProfileId)}/target-preview-meta`);
    state.targetPreview = preview;
    const previewRatio = preview.height > 0 ? preview.width / preview.height : 16 / 9;
    frame.style.setProperty("--target-preview-ratio", String(Math.max(previewRatio, 16 / 9)));
    image.hidden = false;
    empty.hidden = true;
    meta.textContent = `${preview.title} · ${preview.process_name || "unknown process"} · client ${preview.width}x${preview.height}`;
    state.lastPreviewRefreshAt = now;
  } catch (error) {
    state.targetPreview = null;
    image.hidden = true;
    image.removeAttribute("src");
    empty.hidden = false;
    empty.textContent = "Target preview unavailable";
    meta.textContent = error.message;
    frame.style.removeProperty("--target-preview-ratio");
  }
}

function startTargetPreviewStream() {
  const image = $("target-preview-image");
  const empty = $("target-preview-empty");
  if (!state.selectedProfileId) {
    return;
  }
  if (state.previewStreamProfileId === state.selectedProfileId && image.getAttribute("src")) {
    return;
  }
  const streamUrl = `/api/profiles/${encodeURIComponent(state.selectedProfileId)}/target-preview-stream?fps=${PREVIEW_STREAM_FPS}&max_width=${PREVIEW_STREAM_MAX_WIDTH}`;
  state.previewStreamProfileId = state.selectedProfileId;
  image.src = streamUrl;
  image.hidden = false;
  empty.hidden = false;
  empty.textContent = "Connecting to live preview...";
}

function stopTargetPreviewStream() {
  const image = $("target-preview-image");
  state.previewStreamProfileId = null;
  image.removeAttribute("src");
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
  if (state.activeRun && isRunActive(state.activeRun)) {
    throw activeRunConflictError(state.activeRun);
  }
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
  state.activeRun = normalizeRunListEntry(payload);
  state.hasActiveRun = true;
  upsertRunEntry(payload);
  renderRunCount();
  renderRunsList();
  updateStopButton();
  updateRunCommandState();
  updateGlobalRunStatus();
  await refreshSelectedRunData({ force: true });
  activateSelectionView("runs");
  activateDetailTab("timeline");
  showNotice(`${mode === "live" ? "Live" : "Dry"} Run started.`, "good");
}

async function stopSelectedRun() {
  const run = getActiveStoppableRun();
  if (!run) return;
  state.selectedRunId = run.id;
  const payload = await api(`/api/runs/${encodeURIComponent(run.id)}/stop`, {
    method: "POST",
  });
  upsertRunEntry(payload);
  state.activeRun = isRunActive(payload) ? normalizeRunListEntry(payload) : null;
  state.hasActiveRun = Boolean(state.activeRun);
  renderRunCount();
  renderRunsList();
  updateStopButton();
  updateRunCommandState();
  updateGlobalRunStatus();
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
  state.activeRun = payload.active_run
    ? normalizeRunListEntry(payload.active_run)
    : (runs.find((run) => isRunActive(run)) || null);
  state.hasActiveRun = Boolean(state.activeRun);
  if (!state.selectedRunId || !runs.some((run) => run.id === state.selectedRunId)) {
    state.selectedRunId = runs.length ? runs[0].id : null;
  }
  renderRunCount();
  const nextSignature = runsSignature(runs);
  const listChanged = nextSignature !== state.lastRunsSignature;
  state.lastRunsSignature = nextSignature;

  if (listChanged || previousSelectedRunId !== state.selectedRunId) {
    renderRunsList();
  }
  updateStopButton();
  updateRunCommandState();
  updateGlobalRunStatus();
  
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
  updateOverviewAlert();

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

function displayBackgroundCaptureStatus(status) {
  if (status === "verified_for_occlusion") return "Verified for occlusion";
  if (status === "probe_failed") return "Probe failed";
  if (status === "visible_required") return "Visible target required";
  return status || "not_checked";
}

function getActiveStoppableRun() {
  if (isRunActive(state.activeRun)) {
    return state.activeRun;
  }
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
  button.setAttribute(
    "aria-label",
    run ? `Stop active ${run.mode} for ${run.profile_id}` : "No active Run to stop",
  );
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
  $("run-readiness-badge").textContent = "Unknown";
  $("run-readiness-badge").className = "badge";
  renderMessages("run-readiness-blockers", []);
  updateOverviewAlert();
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
      await refreshReadiness({ includePreview: true });
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

function showNotice(message, tone = "") {
  const notice = $("app-notice");
  $("app-notice-message").textContent = message;
  notice.className = `app-notice ${tone}`.trim();
  notice.setAttribute("role", tone === "error" ? "alert" : "status");
  notice.hidden = false;
}

function hideNotice() {
  $("app-notice").hidden = true;
}

function activeRunConflictError(run) {
  const error = new Error("another Run is already active");
  error.status = 409;
  error.payload = { active_run: run };
  return error;
}

function describeError(error) {
  const activeRun = error?.payload?.active_run;
  if (activeRun) {
    return `A ${activeRun.mode} Run for ${activeRun.profile_id} is already ${activeRun.status}. View or stop it before starting another Run.`;
  }
  return error?.message || "The operation could not be completed.";
}

async function runCommand(command) {
  try {
    return await command();
  } catch (error) {
    const activeRun = error?.payload?.active_run;
    if (activeRun) {
      state.activeRun = normalizeRunListEntry(activeRun);
      state.hasActiveRun = true;
      upsertRunEntry(activeRun);
      renderRunsList();
      updateStopButton();
      updateRunCommandState();
      updateGlobalRunStatus();
    }
    showNotice(describeError(error), "error");
    return null;
  }
}

function updateRunCommandState() {
  const profile = state.profiles.find((item) => item.id === state.selectedProfileId);
  const activeRun = isRunActive(state.activeRun) ? state.activeRun : null;
  $("dry-run-button").disabled = Boolean(activeRun) || !profile;
  $("live-run-button").disabled = (
    Boolean(activeRun)
    || !profile
    || !state.selectedReadiness?.live_available
  );

  let status = "Select a Profile to inspect readiness.";
  if (activeRun) {
    status = `${activeRun.profile_id} has an active ${activeRun.mode} Run. View or stop it before starting another.`;
  } else if (profile && state.selectedReadiness?.live_available) {
    status = `${profile.name} is Live Ready. Profile selection never starts a Run.`;
  } else if (profile) {
    const blockerCount = state.selectedReadiness?.blockers?.length || 0;
    status = blockerCount
      ? `${profile.name} has ${blockerCount} Live blocker${blockerCount === 1 ? "" : "s"}. Dry Run remains explicit.`
      : `${profile.name} selected. Dry Run remains explicit.`;
  }
  $("command-status").textContent = status;
}

function updateGlobalRunStatus() {
  const run = isRunActive(state.activeRun) ? state.activeRun : null;
  $("global-run-label").textContent = run ? "Active Run" : "No active run";
  $("global-run-summary").textContent = run
    ? `${run.profile_id} · ${run.mode} · ${run.status}`
    : "Ready";
}

function updateOverviewAlert() {
  const target = $("overview-alert");
  const summary = state.selectedRunSummary;
  if (summary) {
    if (summary.failure_reason) {
      target.textContent = summary.failure_reason;
      return;
    }
    if (isRunActive(summary)) {
      target.textContent = `Run is ${summary.status}${summary.current_state ? ` in ${summary.current_state}` : ""}.`;
      return;
    }
    target.textContent = `Run finished with ${displayResultLabel(summary.final_result || summary.status)}.`;
    return;
  }
  const blockers = state.selectedReadiness?.blockers || [];
  if (blockers.length) {
    target.textContent = blockers[0];
  } else if (state.selectedReadiness?.live_available) {
    target.textContent = "Live Readiness passed. Confirm the matched target before starting Live.";
  } else if (state.selectedProfileId) {
    target.textContent = "Refresh readiness or begin an explicit Dry Run.";
  } else {
    target.textContent = "Select a Profile to review readiness before starting a Run.";
  }
}

async function openLiveConfirmation() {
  if (!state.selectedProfileId) return;
  if (isRunActive(state.activeRun)) {
    throw activeRunConflictError(state.activeRun);
  }
  await refreshReadiness({ includePreview: true, forcePreview: true });
  if (!state.selectedReadiness?.live_available) {
    activateWorkspace("run");
    activateDetailTab("readiness");
    showNotice("Live Run is blocked. Review and resolve the Readiness details first.", "error");
    $("detail-readiness-tab").focus();
    return;
  }

  const profile = state.profiles.find((item) => item.id === state.selectedProfileId);
  $("live-confirm-profile").textContent = profile
    ? `${profile.name} (${profile.id})`
    : state.selectedProfileId;
  $("live-confirm-target").textContent = state.targetPreview
    ? `${state.targetPreview.title} · ${state.targetPreview.process_name || "unknown process"} · ${state.targetPreview.width}×${state.targetPreview.height}`
    : $("target-preview-meta").textContent;
  $("live-confirm-readiness").textContent = `${displayBackgroundCaptureStatus(state.selectedReadiness.background_capture_status)} · readiness passed`;
  $("live-confirm-runtime").textContent = state.runtime?.is_admin
    ? "Current runtime is elevated"
    : "Current runtime uses standard user privilege";
  const dialog = $("live-dialog");
  dialog.returnValue = "";
  dialog.showModal();
  window.requestAnimationFrame(() => $("cancel-live-button").focus());
}

function activateWorkspace(workspace, { focus = false } = {}) {
  const allowed = new Set(["run", "build", "settings"]);
  const nextWorkspace = allowed.has(workspace) ? workspace : "run";
  state.activeWorkspace = nextWorkspace;
  document.body.dataset.workspace = nextWorkspace;
  for (const button of document.querySelectorAll("[data-workspace-target]")) {
    const selected = button.dataset.workspaceTarget === nextWorkspace;
    button.classList.toggle("active", selected);
    button.setAttribute("aria-selected", String(selected));
    button.tabIndex = selected ? 0 : -1;
  }
  for (const panel of document.querySelectorAll(".workspace-view")) {
    const selected = panel.id === `workspace-${nextWorkspace}`;
    panel.hidden = !selected;
    panel.classList.toggle("active", selected);
  }
  localStorage.setItem("operator-workspace", nextWorkspace);
  if (nextWorkspace === "build") {
    void runCommand(async () => {
      await flushBuilderAutosave();
      await refreshBuilderProfile();
    });
  }
  if (focus) {
    $(`workspace-${nextWorkspace}`).focus();
  }
}

function activateSelectionView(view, { focus = false } = {}) {
  const nextView = view === "runs" ? "runs" : "profiles";
  state.activeSelectionView = nextView;
  for (const button of document.querySelectorAll("[data-selection-target]")) {
    const selected = button.dataset.selectionTarget === nextView;
    button.classList.toggle("active", selected);
    button.setAttribute("aria-selected", String(selected));
    button.tabIndex = selected ? 0 : -1;
  }
  $("profiles-list-panel").hidden = nextView !== "profiles";
  $("runs-list-panel").hidden = nextView !== "runs";
  if (focus) $(`${nextView}-list-tab`).focus();
}

function activateDetailTab(view, { focus = false } = {}) {
  const allowed = new Set(["readiness", "timeline", "logs", "artifacts", "pack"]);
  const nextView = allowed.has(view) ? view : "readiness";
  state.activeDetailView = nextView;
  for (const button of document.querySelectorAll("[data-detail-target]")) {
    const selected = button.dataset.detailTarget === nextView;
    button.classList.toggle("active", selected);
    button.setAttribute("aria-selected", String(selected));
    button.tabIndex = selected ? 0 : -1;
  }
  for (const pane of document.querySelectorAll(".detail-pane")) {
    const selected = pane.id === `detail-${nextView}`;
    pane.hidden = !selected;
    pane.classList.toggle("active", selected);
  }
  if (focus) $(`detail-${nextView}-tab`).focus();
}

function addArrowKeyNavigation(container, buttonSelector, activate) {
  container.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    const buttons = [...container.querySelectorAll(buttonSelector)];
    const currentIndex = buttons.indexOf(document.activeElement);
    if (currentIndex < 0) return;
    event.preventDefault();
    let nextIndex = currentIndex;
    if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % buttons.length;
    if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + buttons.length) % buttons.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = buttons.length - 1;
    const button = buttons[nextIndex];
    activate(button);
    button.focus();
  });
}

function renderBuilderProfileSummary() {
  const profile = state.profiles.find((item) => item.id === state.selectedProfileId);
  $("builder-profile-name").textContent = profile?.name || "No Profile selected";
  $("builder-profile-id").textContent = profile?.id || "—";
  $("builder-pack-status").textContent = profile?.pack_status || "—";
  $("builder-profile-path").textContent = profile?.path || "—";
  $("builder-profile-notes").textContent = profile?.notes || "No notes available.";
  $("builder-validity").textContent = profile ? (profile.valid ? "Valid" : "Invalid") : "Unknown";
  $("builder-validity").className = `badge ${profile ? (profile.valid ? "good" : "bad") : ""}`.trim();
}

async function refreshBuilderProfile() {
  if (!state.selectedProfileId) {
    state.builderDocument = null;
    state.builderSource = null;
    state.builderDraft = null;
    state.builderProfileId = null;
    state.selectedBuilderActionIndex = null;
    renderBuilderDocument();
    renderBuilderDraft();
    return;
  }
  const profileId = state.selectedProfileId;
  try {
    const [source, draft, actionSchema] = await Promise.all([
      api(`/api/profiles/${encodeURIComponent(profileId)}/source`),
      api(`/api/profiles/${encodeURIComponent(profileId)}/draft`),
      state.actionSchema ? Promise.resolve(state.actionSchema) : api("/api/profile-schema"),
    ]);
    if (profileId !== state.selectedProfileId) return;
    state.builderSource = source;
    state.builderDraft = draft;
    state.actionSchema = actionSchema;
    state.builderDocument = draft.document || null;
    if (!state.builderDocument) {
      try {
        const structured = await api(`/api/profiles/${encodeURIComponent(profileId)}/structured`);
        if (profileId !== state.selectedProfileId) return;
        state.builderDocument = structured.document || null;
      } catch (_error) {
        state.builderDocument = null;
      }
    }
    state.builderProfileId = profileId;
    const states = Object.keys(state.builderDocument?.states || {});
    const initialState = state.builderDocument?.initial_state;
    state.selectedBuilderState = states.includes(state.selectedBuilderState)
      ? state.selectedBuilderState
      : (states.includes(initialState) ? initialState : (states[0] || null));
    const actions = state.builderDocument?.states?.[state.selectedBuilderState]?.actions || [];
    state.selectedBuilderActionIndex = Number.isInteger(state.selectedBuilderActionIndex)
      && state.selectedBuilderActionIndex < actions.length
      ? state.selectedBuilderActionIndex
      : (actions.length ? 0 : null);
  } catch (error) {
    if (profileId !== state.selectedProfileId) return;
    state.builderSource = null;
    state.builderDraft = null;
    state.builderDocument = null;
    state.builderProfileId = profileId;
    state.selectedBuilderState = null;
    state.selectedBuilderActionIndex = null;
    $("builder-empty").querySelector("h2").textContent = "Saved source could not be displayed";
    $("builder-empty").querySelector("p").textContent = error.message;
  }
  renderBuilderDocument();
  renderBuilderDraft();
}

function renderBuilderDraft() {
  const editor = $("builder-yaml-editor");
  const draft = state.builderDraft;
  const hasProfile = Boolean(state.builderProfileId && state.builderSource);
  editor.disabled = !hasProfile;
  if (hasProfile && editor.value !== draft?.source) {
    editor.value = draft?.source || state.builderSource?.source || "";
  }
  if (!hasProfile) editor.value = "";

  const badge = $("builder-draft-status");
  if (!hasProfile) {
    badge.textContent = "No Profile";
    badge.className = "badge";
  } else if (draft?.conflict) {
    badge.textContent = "Save Conflict";
    badge.className = "badge bad";
  } else if (state.builderAutosavePending) {
    badge.textContent = "Autosaving";
    badge.className = "badge warn";
  } else if (!draft?.dirty) {
    badge.textContent = "Saved Version";
    badge.className = "badge good";
  } else if (draft?.valid) {
    badge.textContent = "Valid Draft";
    badge.className = "badge good";
  } else {
    badge.textContent = "Invalid Draft";
    badge.className = "badge bad";
  }

  const messages = $("builder-draft-messages");
  messages.innerHTML = "";
  const errors = draft?.errors || [];
  for (const error of errors) {
    const item = document.createElement("li");
    item.textContent = error;
    messages.appendChild(item);
  }
  if (draft?.conflict) {
    const item = document.createElement("li");
    item.textContent = "profile.yaml changed outside the application. Your draft is preserved; discard it to reload the saved file.";
    messages.appendChild(item);
  }

  const meta = $("builder-editor-help");
  if (!hasProfile) {
    meta.textContent = "Select a Profile to begin editing.";
  } else if (draft?.conflict) {
    meta.textContent = "External changes detected. Save is blocked to prevent an overwrite.";
  } else if (state.builderAutosavePending) {
    meta.textContent = "Autosaving the recoverable draft…";
  } else if (draft?.exists && draft?.dirty) {
    meta.textContent = "Draft autosaved. The runnable saved version has not changed.";
  } else {
    meta.textContent = `Saved source: sha256 ${String(state.builderSource.fingerprint).slice(0, 12)}…`;
  }

  $("validate-builder-draft").disabled = !hasProfile || state.builderAutosavePending;
  $("save-builder-profile").disabled = !hasProfile
    || state.builderAutosavePending
    || !draft?.exists
    || !draft?.dirty
    || !draft?.valid
    || draft?.conflict;
  $("reload-builder-source").disabled = !hasProfile
    || state.builderAutosavePending
    || (!draft?.exists && !draft?.dirty && !draft?.conflict);
  $("undo-builder-action").disabled = !hasProfile
    || state.builderAutosavePending
    || state.structuredMutationPending
    || !draft?.history?.can_undo;
  $("redo-builder-action").disabled = !hasProfile
    || state.builderAutosavePending
    || state.structuredMutationPending
    || !draft?.history?.can_redo;
  renderBuilderProblems();
}

function queueBuilderDraftAutosave() {
  if (!state.builderProfileId || !state.builderSource) return;
  window.clearTimeout(state.builderAutosaveTimer);
  const source = $("builder-yaml-editor").value;
  state.builderDraft = {
    ...(state.builderDraft || {}),
    source,
    exists: true,
    dirty: source !== state.builderSource.source,
    valid: false,
    errors: [],
  };
  state.builderAutosavePending = true;
  renderBuilderDraft();
  state.builderAutosaveTimer = window.setTimeout(() => {
    state.builderAutosaveTimer = null;
    const promise = persistBuilderDraft({ showResult: false });
    state.builderAutosavePromise = promise;
    void promise.finally(() => {
      if (state.builderAutosavePromise === promise) state.builderAutosavePromise = null;
    });
  }, 600);
}

async function persistBuilderDraft({ showResult = false } = {}) {
  const profileId = state.builderProfileId;
  if (!profileId || !state.builderSource) return null;
  const source = $("builder-yaml-editor").value;
  const baseFingerprint = state.builderDraft?.base_fingerprint || state.builderSource.fingerprint;
  const expectedVersion = state.builderDraft?.version;
  const expectedFingerprint = state.builderDraft?.draft_fingerprint;
  state.builderAutosavePending = true;
  renderBuilderDraft();
  try {
    const draft = await api(`/api/profiles/${encodeURIComponent(profileId)}/draft`, {
      method: "POST",
      body: JSON.stringify({
        source,
        base_fingerprint: baseFingerprint,
        expected_version: expectedVersion,
        expected_fingerprint: expectedFingerprint,
      }),
    });
    if (profileId !== state.builderProfileId) return draft;
    state.builderDraft = draft;
    if (draft.document) {
      state.builderDocument = draft.document;
      const stateNames = Object.keys(draft.document.states || {});
      if (!stateNames.includes(state.selectedBuilderState)) {
        state.selectedBuilderState = stateNames.includes(draft.document.initial_state)
          ? draft.document.initial_state
          : (stateNames[0] || null);
      }
      renderBuilderDocument();
    }
    if (showResult) {
      showNotice(
        draft.valid ? "Draft is valid and ready to save." : "Draft was preserved, but validation found problems.",
        draft.valid ? "good" : "error",
      );
    }
    return draft;
  } catch (error) {
    if (profileId === state.builderProfileId) {
      state.builderDraft = {
        ...(state.builderDraft || {}),
        valid: false,
        errors: [describeError(error)],
      };
    }
    if (showResult) throw error;
    return null;
  } finally {
    if (profileId === state.builderProfileId) {
      state.builderAutosavePending = false;
      renderBuilderDraft();
    }
  }
}

async function flushBuilderAutosave({ includeInspector = true } = {}) {
  if (includeInspector) await flushBuilderInspectorEdit();
  if (state.builderAutosaveTimer) {
    window.clearTimeout(state.builderAutosaveTimer);
    state.builderAutosaveTimer = null;
    const draft = await persistBuilderDraft({ showResult: false });
    if (!draft) {
      throw new Error("The draft could not be autosaved, so the Profile selection was not changed.");
    }
  }
  if (state.builderAutosavePromise) {
    const draft = await state.builderAutosavePromise;
    if (!draft) {
      throw new Error("The draft could not be autosaved, so structured editing was cancelled.");
    }
  }
}

async function validateBuilderDraft() {
  await flushBuilderAutosave();
  if (!state.builderAutosavePending) {
    await persistBuilderDraft({ showResult: true });
  }
}

async function saveBuilderProfile() {
  const profileId = state.builderProfileId;
  if (!profileId) return;
  await flushBuilderAutosave();
  const draft = await persistBuilderDraft({ showResult: false });
  if (!draft?.valid) {
    showNotice("Fix the Draft Validation problems before saving the Profile.", "error");
    renderBuilderDraft();
    return;
  }
  let saved;
  try {
    saved = await api(`/api/profiles/${encodeURIComponent(profileId)}/save`, {
      method: "POST",
      body: "{}",
    });
  } catch (error) {
    if (error.status === 409) {
      state.builderDraft = {
        ...(state.builderDraft || {}),
        conflict: true,
        errors: [describeError(error)],
      };
      renderBuilderDraft();
    }
    throw error;
  }
  upsertProfileEntry(saved.profile);
  state.builderSource = saved.source;
  state.builderDraft = saved.draft;
  state.builderDocument = saved.draft.document || null;
  renderProfiles();
  renderProfileSelect();
  renderProfilePackDetail();
  renderBuilderProfileSummary();
  renderBuilderDocument();
  renderBuilderDraft();
  await refreshReadiness({ includePreview: false });
  showNotice("Profile saved. A revision backup was retained.", "good");
}

async function discardBuilderDraft() {
  const profileId = state.builderProfileId;
  if (!profileId) return;
  if (!window.confirm("Discard the recoverable draft and reload the saved profile.yaml?")) return;
  window.clearTimeout(state.builderAutosaveTimer);
  window.clearTimeout(state.builderInspectorTimer);
  state.builderAutosaveTimer = null;
  state.builderInspectorTimer = null;
  state.builderInspectorPending = null;
  const draft = await api(`/api/profiles/${encodeURIComponent(profileId)}/discard-draft`, {
    method: "POST",
    body: "{}",
  });
  state.builderDraft = draft;
  state.builderDocument = draft.document || null;
  renderBuilderDocument();
  renderBuilderDraft();
  showNotice("Draft discarded. Reloaded the saved Profile.", "good");
}

function renderBuilderDocument() {
  const documentValue = state.builderDocument;
  const states = documentValue?.states || {};
  const stateNames = Object.keys(states);
  $("builder-fingerprint").textContent = state.builderSource?.fingerprint
    ? `sha256 ${state.builderSource.fingerprint.slice(0, 12)}…`
    : "No source loaded";
  $("builder-empty").hidden = stateNames.length > 0;
  $("builder-flow").hidden = stateNames.length === 0;
  if (!stateNames.length) return;

  const target = $("builder-state-list");
  target.innerHTML = "";
  for (const stateName of stateNames) {
    const stateValue = states[stateName] || {};
    const button = document.createElement("button");
    button.type = "button";
    button.className = `builder-state-node${stateName === state.selectedBuilderState ? " active" : ""}`;
    button.dataset.builderState = stateName;
    button.setAttribute("role", "listitem");
    const transitionParts = [stateValue.on_success, stateValue.on_failure].filter(Boolean);
    button.innerHTML = `<strong>${escapeHtml(stateName)}</strong><span>${stateValue.terminal ? "terminal" : transitionParts.length ? `to ${transitionParts.map(escapeHtml).join(" / ")}` : "no transition"}</span>`;
    target.appendChild(button);
  }
  renderBuilderState();
}

function renderBuilderState() {
  const documentValue = state.builderDocument;
  const stateName = state.selectedBuilderState;
  const stateValue = documentValue?.states?.[stateName] || {};
  $("builder-state-name").textContent = stateName || "No State selected";
  const kind = stateValue.terminal
    ? "Terminal"
    : (stateName === documentValue?.initial_state ? "Initial" : "State");
  $("builder-state-kind").textContent = kind;
  $("builder-state-kind").className = `badge ${stateValue.terminal ? "good" : ""}`.trim();

  const transitions = $("builder-state-transitions");
  transitions.innerHTML = `
    <div><dt>On success</dt><dd>${escapeHtml(stateValue.on_success || "—")}</dd></div>
    <div><dt>On failure</dt><dd>${escapeHtml(stateValue.on_failure || "—")}</dd></div>
  `;

  const anchors = $("builder-anchor-list");
  const requiredAnchors = stateValue.required_anchors || [];
  anchors.innerHTML = requiredAnchors.length
    ? requiredAnchors.map((anchor) => `<li><strong>${escapeHtml(anchor.name || anchor.type || "anchor")}</strong><span class="muted">${escapeHtml(anchor.type || "unknown")}</span></li>`).join("")
    : '<li class="muted">No required anchors</li>';

  const actions = $("builder-action-list");
  const actionValues = stateValue.actions || [];
  if (
    !Number.isInteger(state.selectedBuilderActionIndex)
    || state.selectedBuilderActionIndex >= actionValues.length
  ) {
    state.selectedBuilderActionIndex = actionValues.length ? 0 : null;
  }
  actions.innerHTML = actionValues.length
    ? actionValues.map((action, index) => {
      const definition = actionDefinition(action.type);
      const problems = actionProblems(stateName, index);
      const selected = index === state.selectedBuilderActionIndex;
      const status = problems.length
        ? `<span class="builder-action-status">${problems.length} error${problems.length === 1 ? "" : "s"}</span>`
        : "";
      return `<li><button type="button" class="builder-action-block${action.disabled ? " disabled" : ""}" data-builder-action-index="${index}" aria-current="${selected ? "true" : "false"}"><span class="builder-drag-handle" aria-hidden="true"><svg viewBox="0 0 12 18" width="12" height="18" fill="currentColor"><circle cx="3" cy="3" r="1.25"/><circle cx="9" cy="3" r="1.25"/><circle cx="3" cy="9" r="1.25"/><circle cx="9" cy="9" r="1.25"/><circle cx="3" cy="15" r="1.25"/><circle cx="9" cy="15" r="1.25"/></svg></span><span class="builder-action-copy"><strong>${index + 1}. ${escapeHtml(definition?.label || action.type || "Action")}</strong><span>${escapeHtml(action.type || "unknown")}</span><span>${escapeHtml(formatActionSummary(action, definition))}</span>${status}</span></button></li>`;
    }).join("")
    : '<li class="muted">No Actions. Add Wait from the Tool Palette.</li>';
  renderBuilderActionPalette();
  renderBuilderActionInspector();
}

function actionDefinition(actionType) {
  return state.actionSchema?.actions?.find((definition) => definition.type === actionType) || null;
}

function formatActionSummary(action, definition = null) {
  const summaryFields = definition?.summary_fields || [];
  const entries = summaryFields.length
    ? summaryFields.filter((key) => Object.hasOwn(action || {}, key)).map((key) => [key, action[key]])
    : Object.entries(action || {}).filter(([key]) => !["type", "disabled"].includes(key)).slice(0, 4);
  const fields = entries
    .map(([key, value]) => {
      const rendered = typeof value === "object" ? JSON.stringify(value) : String(value);
      return `${key}=${rendered}`;
    });
  if (action?.disabled) fields.unshift("Disabled");
  return fields.join(" · ") || "No additional settings";
}

function renderBuilderActionPalette() {
  const target = $("builder-action-palette");
  const query = $("builder-action-search").value.trim().toLowerCase();
  const definitions = (state.actionSchema?.actions || [])
    .filter((definition) => definition.structured)
    .filter((definition) => {
      const searchable = [
        definition.label,
        definition.type,
        ...(definition.keywords || []),
      ].join(" ").toLowerCase();
      return !query || searchable.includes(query);
    });
  target.innerHTML = definitions.length
    ? definitions.map((definition) => `<button type="button" data-add-builder-action="${escapeHtml(definition.type)}" role="listitem" ${state.structuredMutationPending ? "disabled" : ""}><strong>${escapeHtml(definition.label)}</strong><span>${escapeHtml(definition.type)}</span></button>`).join("")
    : '<span class="muted">No matching structured Actions.</span>';
}

function actionProblems(stateName, actionIndex) {
  const prefix = `states.${stateName}.actions[${actionIndex}]`;
  return (state.builderDraft?.problems || []).filter((problem) => problem.location?.startsWith(prefix));
}

function renderBuilderActionInspector() {
  const stateValue = state.builderDocument?.states?.[state.selectedBuilderState] || {};
  const actions = stateValue.actions || [];
  const index = state.selectedBuilderActionIndex;
  const action = Number.isInteger(index) ? actions[index] : null;
  $("builder-action-inspector-empty").hidden = Boolean(action);
  const form = $("builder-action-inspector-form");
  form.hidden = !action;
  if (!action) return;

  const definition = actionDefinition(action.type);
  $("builder-inspector-label").textContent = definition?.label || action.type || "Action";
  $("builder-inspector-type").textContent = action.type || "unknown";
  const fields = $("builder-inspector-fields");
  if (definition?.structured && action.type === "wait") {
    const fieldProblems = actionProblems(state.selectedBuilderState, index)
      .filter((problem) => problem.location?.endsWith(".seconds"));
    fields.innerHTML = `
      <label for="builder-action-seconds">Seconds</label>
      <input id="builder-action-seconds" name="seconds" type="number" min="0" step="any" value="${escapeHtml(action.seconds ?? "")}" aria-invalid="${fieldProblems.length ? "true" : "false"}" aria-describedby="builder-inspector-errors">
      <span class="muted">${escapeHtml(definition.fields[0]?.hint || "")}</span>
    `;
  } else {
    fields.innerHTML = '<p class="muted">This Action uses the raw YAML editor for its fields. Ordering and lifecycle commands remain available here.</p>';
  }

  const problems = actionProblems(state.selectedBuilderState, index);
  $("builder-inspector-errors").innerHTML = problems
    .map((problem) => `<div>${escapeHtml(problem.message)}</div>`)
    .join("");
  const pending = state.structuredMutationPending || state.builderAutosavePending;
  $("move-builder-action-up").disabled = pending || index <= 0;
  $("move-builder-action-down").disabled = pending || index >= actions.length - 1;
  $("duplicate-builder-action").disabled = pending;
  $("toggle-builder-action").disabled = pending;
  $("toggle-builder-action").textContent = action.disabled ? "Enable" : "Disable";
  $("delete-builder-action").disabled = pending;
  const moveStateSelect = $("move-builder-action-state");
  const otherStates = Object.keys(state.builderDocument?.states || {})
    .filter((candidate) => candidate !== state.selectedBuilderState);
  const previousTarget = moveStateSelect.value;
  moveStateSelect.innerHTML = otherStates.length
    ? otherStates.map((candidate) => `<option value="${escapeHtml(candidate)}">${escapeHtml(candidate)}</option>`).join("")
    : '<option value="">No other State</option>';
  if (otherStates.includes(previousTarget)) moveStateSelect.value = previousTarget;
  moveStateSelect.disabled = pending || !otherStates.length;
  $("move-builder-action-state-button").disabled = pending || !otherStates.length;
}

function renderBuilderProblems() {
  const problems = state.builderDraft?.problems || [];
  $("builder-problem-count").textContent = String(problems.length);
  $("builder-problem-count").className = `badge ${problems.length ? "bad" : "good"}`;
  $("builder-problem-list").innerHTML = problems.length
    ? problems.map((problem, index) => `<li><button type="button" data-builder-problem-index="${index}">${escapeHtml(problem.location ? `${problem.location}: ${problem.message}` : problem.message)}</button></li>`).join("")
    : '<li class="muted">No Draft Validation problems.</li>';
}

function applyStructuredDraft(draft) {
  state.builderDraft = draft;
  if (draft.document) state.builderDocument = draft.document;
  renderBuilderDocument();
  renderBuilderDraft();
}

async function mutateBuilderAction(
  mutation,
  { focusIndex = null, focusField = false, focusState = null } = {},
) {
  const profileId = state.builderProfileId;
  if (!profileId || state.structuredMutationPending) return;
  await flushBuilderInspectorEdit();
  await flushBuilderAutosave({ includeInspector: false });
  state.structuredMutationPending = true;
  renderBuilderDraft();
  renderBuilderActionPalette();
  renderBuilderActionInspector();
  try {
    const draft = await api(`/api/profiles/${encodeURIComponent(profileId)}/actions`, {
      method: "POST",
      body: JSON.stringify({
        expected_version: state.builderDraft?.version,
        expected_fingerprint: state.builderDraft?.draft_fingerprint,
        mutation,
      }),
    });
    if (profileId !== state.builderProfileId) return;
    if (focusState) state.selectedBuilderState = focusState;
    state.selectedBuilderActionIndex = focusIndex;
    applyStructuredDraft(draft);
    showNotice(`${mutation.operation[0].toUpperCase()}${mutation.operation.slice(1)} Action completed.`, draft.valid ? "good" : "error");
    window.requestAnimationFrame(() => {
      const selector = focusField
        ? "#builder-action-seconds"
        : `[data-builder-action-index="${state.selectedBuilderActionIndex}"]`;
      document.querySelector(selector)?.focus();
    });
  } catch (error) {
    if (error.status === 409) await refreshBuilderProfile();
    throw error;
  } finally {
    if (profileId === state.builderProfileId) {
      state.structuredMutationPending = false;
      renderBuilderDraft();
      renderBuilderActionPalette();
      renderBuilderActionInspector();
    }
  }
}

async function restoreBuilderActionHistory(direction) {
  const profileId = state.builderProfileId;
  if (!profileId || state.structuredMutationPending) return;
  await flushBuilderAutosave();
  state.structuredMutationPending = true;
  renderBuilderDraft();
  try {
    const draft = await api(`/api/profiles/${encodeURIComponent(profileId)}/${direction}`, {
      method: "POST",
      body: JSON.stringify({
        expected_version: state.builderDraft?.version,
        expected_fingerprint: state.builderDraft?.draft_fingerprint,
      }),
    });
    if (profileId !== state.builderProfileId) return;
    applyStructuredDraft(draft);
    showNotice(`${direction === "undo" ? "Undo" : "Redo"} completed.`, "good");
  } finally {
    if (profileId === state.builderProfileId) {
      state.structuredMutationPending = false;
      renderBuilderDraft();
      renderBuilderActionPalette();
      renderBuilderActionInspector();
    }
  }
}

function selectedBuilderAction() {
  const actions = state.builderDocument?.states?.[state.selectedBuilderState]?.actions || [];
  return Number.isInteger(state.selectedBuilderActionIndex)
    ? actions[state.selectedBuilderActionIndex]
    : null;
}

async function flushBuilderInspectorEdit() {
  if (!state.builderInspectorPending) return;
  window.clearTimeout(state.builderInspectorTimer);
  state.builderInspectorTimer = null;
  const pending = state.builderInspectorPending;
  state.builderInspectorPending = null;
  await mutateBuilderAction(pending.mutation, pending.options);
}

function profileIdFromText(value) {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 64);
}

function updateCreateProfileSuggestions() {
  const game = $("create-profile-game").value.trim();
  const mode = $("create-profile-mode").value.trim();
  const nameInput = $("create-profile-name");
  if (!state.createProfileNameTouched) {
    nameInput.value = [game, mode].filter(Boolean).join(" ");
  }
  if (!state.createProfileIdTouched) {
    $("create-profile-id").value = profileIdFromText(
      nameInput.value.trim() || [game, mode].filter(Boolean).join(" "),
    );
  }
  const identifier = $("create-profile-id").value.trim() || "<identifier>";
  $("create-profile-destination").textContent = `Destination: profiles/${identifier}/`;
}

function openCreateProfileDialog() {
  const form = $("create-profile-form");
  form.reset();
  state.createProfileIdTouched = false;
  state.createProfileNameTouched = false;
  $("create-profile-initial-state").value = "start";
  $("create-profile-error").hidden = true;
  $("confirm-create-profile").disabled = false;
  updateCreateProfileSuggestions();
  $("create-profile-dialog").showModal();
  window.requestAnimationFrame(() => $("create-profile-game").focus());
}

async function createProfile(event) {
  event.preventDefault();
  const form = $("create-profile-form");
  if (!form.reportValidity()) return;
  const errorTarget = $("create-profile-error");
  const submitButton = $("confirm-create-profile");
  errorTarget.hidden = true;
  submitButton.disabled = true;
  try {
    const created = await api("/api/profiles", {
      method: "POST",
      body: JSON.stringify({
        game: $("create-profile-game").value.trim(),
        mode: $("create-profile-mode").value.trim(),
        name: $("create-profile-name").value.trim(),
        profile_id: $("create-profile-id").value.trim(),
        initial_state: $("create-profile-initial-state").value.trim(),
      }),
    });
    $("create-profile-dialog").close();
    await refreshProfiles({ refreshReadinessAfter: false });
    await selectProfile(created.profile.id, { skipInitialReadiness: true });
    activateWorkspace("build");
    showNotice(`Created ${created.profile.name}. Complete the YAML Draft, then validate and save.`, "good");
    window.requestAnimationFrame(() => $("builder-yaml-editor").focus());
  } catch (error) {
    errorTarget.textContent = describeError(error);
    errorTarget.hidden = false;
  } finally {
    submitButton.disabled = false;
  }
}

async function refreshStartupChecks() {
  const payload = await api("/api/startup-checks");
  $("startup-checks-badge").textContent = payload.ok ? "Passed" : "Needs attention";
  $("startup-checks-badge").className = `badge ${payload.ok ? "good" : "bad"}`;
  const list = $("startup-checks-list");
  list.innerHTML = "";
  for (const [name, value] of Object.entries(payload.checks || {})) {
    const item = document.createElement("li");
    item.textContent = `${name.replaceAll("_", " ")}: ${String(value)}`;
    list.appendChild(item);
  }
  for (const message of payload.messages || []) {
    const item = document.createElement("li");
    item.textContent = message;
    list.appendChild(item);
  }
  if (!list.children.length) {
    const item = document.createElement("li");
    item.className = "muted";
    item.textContent = "No diagnostics were returned.";
    list.appendChild(item);
  }
}

$("refresh-button").addEventListener("click", () => runCommand(() => refreshProfiles()));
$("readiness-refresh-button").addEventListener("click", () => runCommand(() => refreshReadiness({ includePreview: true, forcePreview: true })));
$("dry-run-button").addEventListener("click", () => runCommand(() => startRun("dry-run")));
$("live-run-button").addEventListener("click", () => runCommand(() => openLiveConfirmation()));
$("stop-run-button").addEventListener("click", () => runCommand(() => stopSelectedRun()));
$("app-notice-dismiss").addEventListener("click", hideNotice);
$("build-view-in-run").addEventListener("click", () => activateWorkspace("run", { focus: true }));
$("create-profile-button").addEventListener("click", openCreateProfileDialog);
$("cancel-create-profile").addEventListener("click", () => $("create-profile-dialog").close());
$("create-profile-form").addEventListener("submit", (event) => void createProfile(event));
$("create-profile-game").addEventListener("input", updateCreateProfileSuggestions);
$("create-profile-mode").addEventListener("input", updateCreateProfileSuggestions);
$("create-profile-name").addEventListener("input", () => {
  state.createProfileNameTouched = true;
  updateCreateProfileSuggestions();
});
$("create-profile-id").addEventListener("input", () => {
  state.createProfileIdTouched = true;
  updateCreateProfileSuggestions();
});
$("builder-yaml-editor").addEventListener("input", queueBuilderDraftAutosave);
$("validate-builder-draft").addEventListener("click", () => runCommand(() => validateBuilderDraft()));
$("save-builder-profile").addEventListener("click", () => runCommand(() => saveBuilderProfile()));
$("reload-builder-source").addEventListener("click", () => runCommand(() => discardBuilderDraft()));
$("undo-builder-action").addEventListener("click", () => runCommand(() => restoreBuilderActionHistory("undo")));
$("redo-builder-action").addEventListener("click", () => runCommand(() => restoreBuilderActionHistory("redo")));
$("builder-action-search").addEventListener("input", renderBuilderActionPalette);
$("settings-refresh-button").addEventListener("click", () => runCommand(async () => {
  await Promise.all([refreshRuntimeStatus(), refreshStartupChecks()]);
  showNotice("Diagnostics refreshed.", "good");
}));

$("workspace-navigation").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-workspace-target]");
  if (button) activateWorkspace(button.dataset.workspaceTarget, { focus: true });
});
$("profiles-list-tab").addEventListener("click", () => activateSelectionView("profiles"));
$("runs-list-tab").addEventListener("click", () => activateSelectionView("runs"));
$("detail-tabs").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-detail-target]");
  if (button) activateDetailTab(button.dataset.detailTarget);
});

addArrowKeyNavigation($("workspace-navigation"), "button[data-workspace-target]", (button) => activateWorkspace(button.dataset.workspaceTarget));
addArrowKeyNavigation(document.querySelector(".segmented-control"), "button[data-selection-target]", (button) => activateSelectionView(button.dataset.selectionTarget));
addArrowKeyNavigation($("detail-tabs"), "button[data-detail-target]", (button) => activateDetailTab(button.dataset.detailTarget));

$("profiles").addEventListener("click", (event) => runCommand(async () => {
  if (!(event.target instanceof Element)) return;
  const button = event.target.closest("button[data-profile-id]");
  if (!button) return;
  await selectProfile(button.dataset.profileId);
}));

$("runs").addEventListener("click", (event) => runCommand(async () => {
  if (!(event.target instanceof Element)) return;
  const button = event.target.closest("button[data-run-id]");
  if (!button) return;
  state.selectedRunId = button.dataset.runId;
  renderRunsList();
  await refreshRunDetail();
}));

$("builder-state-list").addEventListener("click", (event) => {
  if (!(event.target instanceof Element)) return;
  const button = event.target.closest("button[data-builder-state]");
  if (!button) return;
  state.selectedBuilderState = button.dataset.builderState;
  const actions = state.builderDocument?.states?.[state.selectedBuilderState]?.actions || [];
  state.selectedBuilderActionIndex = actions.length ? 0 : null;
  renderBuilderDocument();
});

$("builder-action-list").addEventListener("click", (event) => {
  if (!(event.target instanceof Element)) return;
  const button = event.target.closest("button[data-builder-action-index]");
  if (!button) return;
  state.selectedBuilderActionIndex = Number(button.dataset.builderActionIndex);
  renderBuilderState();
});

$("builder-action-palette").addEventListener("click", (event) => runCommand(async () => {
  if (!(event.target instanceof Element)) return;
  const button = event.target.closest("button[data-add-builder-action]");
  if (!button || !state.selectedBuilderState) return;
  const actions = state.builderDocument?.states?.[state.selectedBuilderState]?.actions || [];
  const definition = actionDefinition(button.dataset.addBuilderAction);
  const fields = Object.fromEntries(
    (definition?.fields || [])
      .filter((field) => field.default !== undefined)
      .map((field) => [field.name, field.default]),
  );
  await mutateBuilderAction(
    {
      operation: "insert",
      state: state.selectedBuilderState,
      index: actions.length,
      action_type: button.dataset.addBuilderAction,
      fields,
    },
    { focusIndex: actions.length, focusField: true },
  );
}));

$("builder-action-inspector-form").addEventListener("input", (event) => {
  if (!(event.target instanceof HTMLInputElement) || event.target.name !== "seconds") return;
  const index = state.selectedBuilderActionIndex;
  if (!Number.isInteger(index)) return;
  const value = event.target.value === "" ? "" : Number(event.target.value);
  window.clearTimeout(state.builderInspectorTimer);
  state.builderInspectorPending = {
    mutation: {
      operation: "update",
      state: state.selectedBuilderState,
      index,
      fields: { seconds: value },
    },
    options: { focusIndex: index, focusField: true },
  };
  state.builderInspectorTimer = window.setTimeout(() => {
    state.builderInspectorTimer = null;
    void runCommand(() => flushBuilderInspectorEdit());
  }, 400);
});

$("move-builder-action-up").addEventListener("click", () => runCommand(() => {
  const index = state.selectedBuilderActionIndex;
  return mutateBuilderAction(
    {
      operation: "move",
      state: state.selectedBuilderState,
      index,
      target_index: index - 1,
    },
    { focusIndex: index - 1 },
  );
}));

$("move-builder-action-down").addEventListener("click", () => runCommand(() => {
  const index = state.selectedBuilderActionIndex;
  return mutateBuilderAction(
    {
      operation: "move",
      state: state.selectedBuilderState,
      index,
      target_index: index + 1,
    },
    { focusIndex: index + 1 },
  );
}));

$("duplicate-builder-action").addEventListener("click", () => runCommand(() => {
  const index = state.selectedBuilderActionIndex;
  return mutateBuilderAction(
    {
      operation: "duplicate",
      state: state.selectedBuilderState,
      index,
    },
    { focusIndex: index + 1 },
  );
}));

$("toggle-builder-action").addEventListener("click", () => runCommand(() => {
  const action = selectedBuilderAction();
  const index = state.selectedBuilderActionIndex;
  return mutateBuilderAction(
    {
      operation: action?.disabled ? "enable" : "disable",
      state: state.selectedBuilderState,
      index,
    },
    { focusIndex: index },
  );
}));

$("move-builder-action-state-button").addEventListener("click", () => runCommand(() => {
  const index = state.selectedBuilderActionIndex;
  const targetState = $("move-builder-action-state").value;
  if (!Number.isInteger(index) || !targetState) return null;
  const targetActions = state.builderDocument?.states?.[targetState]?.actions || [];
  return mutateBuilderAction(
    {
      operation: "move_to_state",
      state: state.selectedBuilderState,
      index,
      target_state: targetState,
      target_index: targetActions.length,
    },
    {
      focusState: targetState,
      focusIndex: targetActions.length,
    },
  );
}));

$("delete-builder-action").addEventListener("click", () => runCommand(() => {
  const action = selectedBuilderAction();
  const index = state.selectedBuilderActionIndex;
  const hasNestedSettings = Object.values(action || {}).some((value) => value && typeof value === "object");
  if (hasNestedSettings && !window.confirm("Delete this Action and its nested settings?")) return null;
  const actions = state.builderDocument?.states?.[state.selectedBuilderState]?.actions || [];
  return mutateBuilderAction(
    {
      operation: "delete",
      state: state.selectedBuilderState,
      index,
    },
    { focusIndex: actions.length > 1 ? Math.min(index, actions.length - 2) : null },
  );
}));

$("builder-problem-list").addEventListener("click", (event) => {
  if (!(event.target instanceof Element)) return;
  const button = event.target.closest("button[data-builder-problem-index]");
  if (!button) return;
  const problem = state.builderDraft?.problems?.[Number(button.dataset.builderProblemIndex)];
  const match = problem?.location?.match(/^states\.([^.]+)\.actions\[(\d+)\](?:\.(.+))?$/);
  if (!match) return;
  state.selectedBuilderState = match[1];
  state.selectedBuilderActionIndex = Number(match[2]);
  renderBuilderDocument();
  window.requestAnimationFrame(() => {
    const target = match[3] === "seconds"
      ? $("builder-action-seconds")
      : document.querySelector(`[data-builder-action-index="${match[2]}"]`);
    target?.focus();
  });
});

$("runtime-admin-button").addEventListener("click", () => runCommand(async () => {
  try {
    await relaunchDashboardAsAdmin();
  } catch (error) {
    $("runtime-status-title").textContent = "Administrator relaunch failed";
    $("runtime-status-message").textContent = error.message;
    throw error;
  }
}));

$("profile-select").addEventListener("change", (event) => runCommand(() => selectProfile(event.target.value)));

$("live-dialog").addEventListener("close", () => {
  if ($("live-dialog").returnValue === "confirm") {
    void runCommand(() => startRun("live", "start-live-run"));
  }
});

$("target-preview-image").addEventListener("load", () => {
  const image = $("target-preview-image");
  const empty = $("target-preview-empty");
  image.hidden = false;
  empty.hidden = true;
});

$("target-preview-image").addEventListener("error", () => {
  const image = $("target-preview-image");
  const empty = $("target-preview-empty");
  empty.hidden = false;
  empty.textContent = "Target preview unavailable";
  image.hidden = true;
});

async function initialize() {
  const savedWorkspace = localStorage.getItem("operator-workspace") || "run";
  activateWorkspace(savedWorkspace);
  activateSelectionView("profiles");
  activateDetailTab("readiness");
  updateStopButton();
  updateRunCommandState();
  updateGlobalRunStatus();
  try {
    await refreshProfiles();
    await refreshBuilderProfile();
    await refreshRuns();
  } catch (error) {
    showNotice(`Dashboard initialization failed: ${describeError(error)}`, "error");
  } finally {
    scheduleNextPoll();
  }
}

void initialize();
