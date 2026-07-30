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
  builderDrag: null,
  builderDropSlot: null,
  builderDropState: null,
  builderPointerDrag: null,
  builderActionAutoPan: null,
  builderSuppressActionClick: false,
  builderActionLibraryCollapsed: false,
  builderActionLibraryHidden: false,
  builderActionLibraryDrag: null,
  builderActionInspectorCollapsed: true,
  builderActionViewport: {
    profileId: null,
    x: 0,
    y: 0,
    zoom: 1,
    initialized: false,
  },
  // This arrangement deliberately lives only for the current browser session.
  // State/action changes remain Draft mutations; moving a roof never writes YAML.
  builderActionLayout: { profileId: null, positions: {} },
  builderActionInitialLayoutProfileId: null,
  builderActionInitialLayoutActivation: 0,
  builderActionInitialLayoutCompletedActivation: null,
  builderActionColumnLayoutMobile: null,
  builderActionSectionDrag: null,
  builderActionNavigationCollapsed: true,
  builderActionOverviewOpen: false,
  builderStateMinimapSignature: "",
  builderCanvasPan: null,
  builderView: "state",
  builderFlowLayout: null,
  builderFlowNodeDrag: null,
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
const BUILDER_ACTION_MIN_ZOOM = 0.45;
const BUILDER_ACTION_MAX_ZOOM = 1.8;
const BUILDER_ACTION_AUTO_PAN_SPEED = 1080;
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
  if (state.selectedProfileId !== profileId) {
    state.builderActionInitialLayoutActivation += 1;
  }
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

async function refreshBuilderTargetPreview() {
  const image = $("builder-target-preview-image");
  const empty = $("builder-target-preview-empty");
  const meta = $("builder-target-preview-meta");
  const frame = $("builder-target-preview-frame");
  const button = $("refresh-builder-target-preview");
  if (!state.selectedProfileId) {
    image.hidden = true;
    image.removeAttribute("src");
    empty.hidden = false;
    empty.textContent = "Select a Profile to inspect its target.";
    meta.textContent = "The preview always uses the Saved Profile Version.";
    frame.style.removeProperty("--builder-target-preview-ratio");
    button.disabled = true;
    return;
  }
  button.disabled = true;
  empty.hidden = false;
  empty.textContent = "Capturing Saved Profile target…";
  try {
    const preview = await api(
      `/api/profiles/${encodeURIComponent(state.selectedProfileId)}/target-preview`,
    );
    const previewRatio = preview.height > 0 ? preview.width / preview.height : 16 / 9;
    frame.style.setProperty(
      "--builder-target-preview-ratio",
      String(Math.max(previewRatio, 16 / 9)),
    );
    image.src = preview.data_url;
    image.hidden = false;
    empty.hidden = true;
    meta.textContent = `${preview.title} · ${preview.process_name || "unknown process"} · client ${preview.width}×${preview.height} · Saved Profile`;
  } catch (error) {
    image.hidden = true;
    image.removeAttribute("src");
    empty.hidden = false;
    empty.textContent = "Target preview unavailable";
    meta.textContent = `${describeError(error)} · Saved Profile`;
    frame.style.removeProperty("--builder-target-preview-ratio");
  } finally {
    button.disabled = false;
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
      if (state.activeWorkspace === "build") {
        await refreshBuilderTargetPreview();
      }
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
    state.builderFlowLayout = null;
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
    try {
      state.builderFlowLayout = await api(
        `/api/profiles/${encodeURIComponent(profileId)}/flow-layout`,
      );
    } catch (_error) {
      state.builderFlowLayout = null;
    }
    if (profileId !== state.selectedProfileId) return;
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
    state.builderFlowLayout = null;
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
  renderBuilderView();
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
    const problemSummary = builderProblemSummary(stateProblems(stateName));
    const problemBadge = problemSummary.count
      ? `<span class="builder-state-problems ${problemSummary.className}">${escapeHtml(problemSummary.label)}</span>`
      : "";
    button.innerHTML = `<strong>${escapeHtml(stateName)}</strong><span>${stateValue.terminal ? "terminal" : transitionParts.length ? `to ${transitionParts.map(escapeHtml).join(" / ")}` : "no transition"}</span>${problemBadge}`;
    target.appendChild(button);
  }
  renderBuilderState();
  renderBuilderFlowGraph();
}

function renderBuilderView() {
  const flowActive = state.builderView === "flow";
  const stateActionsMode = !flowActive && !$("builder-flow").hidden;
  $("builder-state-view").hidden = flowActive;
  $("builder-graph-view").hidden = !flowActive;
  $("builder-state-view-tab").setAttribute("aria-selected", String(!flowActive));
  $("builder-graph-view-tab").setAttribute("aria-selected", String(flowActive));
  $("builder-canvas-title").textContent = flowActive ? "Flow" : "State Actions";
  $("workspace-build").classList.toggle("state-actions-mode", stateActionsMode);
  if (flowActive) closeBuilderDrawers();
  if (stateActionsMode) {
    window.requestAnimationFrame(() => renderBuilderActionViewport());
  }
}

function builderFlowPositions() {
  return state.builderFlowLayout?.positions || {};
}

function renderBuilderFlowEdges() {
  const svg = $("builder-flow-edges");
  const documentValue = state.builderDocument;
  const states = documentValue?.states || {};
  const positions = builderFlowPositions();
  const nodeWidth = 184;
  const nodeHeight = 82;
  const edges = [];
  for (const [sourceName, stateValue] of Object.entries(states)) {
    const source = positions[sourceName];
    if (!source) continue;
    for (const [field, kind] of [["on_success", "success"], ["on_failure", "failure"]]) {
      const targetName = stateValue?.[field];
      const target = positions[targetName];
      if (!target) continue;
      const x1 = source.x + nodeWidth;
      const y1 = source.y + nodeHeight / 2;
      const x2 = target.x;
      const y2 = target.y + nodeHeight / 2;
      const middle = Math.round((x1 + x2) / 2);
      edges.push(
        `<path class="builder-flow-edge ${kind}" d="M ${x1} ${y1} C ${middle} ${y1}, ${middle} ${y2}, ${x2} ${y2}"><title>${escapeHtml(`${sourceName} ${field.replace("_", " ")} ${targetName}`)}</title></path>`,
      );
    }
  }
  svg.innerHTML = edges.join("");
}

function renderBuilderFlowInspector() {
  const stateName = state.selectedBuilderState;
  const stateValue = state.builderDocument?.states?.[stateName] || {};
  const stateNames = Object.keys(state.builderDocument?.states || {});
  const terminal = Boolean(stateValue.terminal);
  $("builder-flow-state-name").textContent = stateName || "No State selected";
  $("builder-flow-initial").checked = stateName === state.builderDocument?.initial_state;
  $("builder-flow-terminal").checked = terminal;
  $("builder-flow-result").value = stateValue.result || "";
  const transitionOptions = ({ failure = false } = {}) => [
    '<option value="">No transition</option>',
    ...(failure ? ['<option value="graceful_termination">Graceful termination</option>'] : []),
    ...stateNames.map((candidate) => `<option value="${escapeHtml(candidate)}">${escapeHtml(candidate)}</option>`),
  ].join("");
  $("builder-flow-success").innerHTML = transitionOptions();
  $("builder-flow-failure").innerHTML = transitionOptions({ failure: true });
  $("builder-flow-success").value = stateValue.on_success || "";
  $("builder-flow-failure").value = stateValue.on_failure || "";
  $("builder-flow-result").disabled = !terminal;
  $("builder-flow-success").disabled = terminal;
  $("builder-flow-failure").disabled = terminal;
  $("builder-flow-initial").disabled = !stateName || state.structuredMutationPending;
  $("builder-flow-terminal").disabled = !stateName || state.structuredMutationPending;
  $("save-builder-flow-state").disabled = !stateName || state.structuredMutationPending;
  for (const buttonId of [
    "move-builder-node-up",
    "move-builder-node-left",
    "move-builder-node-down",
    "move-builder-node-right",
  ]) {
    $(buttonId).disabled = !stateName || !state.builderFlowLayout;
  }
}

function renderBuilderFlowGraph() {
  const target = $("builder-flow-nodes");
  const states = state.builderDocument?.states || {};
  const positions = builderFlowPositions();
  const stateNames = Object.keys(states);
  const maximumX = Math.max(720, ...stateNames.map((name) => (positions[name]?.x || 0) + 232));
  const maximumY = Math.max(420, ...stateNames.map((name) => (positions[name]?.y || 0) + 130));
  target.style.width = `${maximumX}px`;
  target.style.height = `${maximumY}px`;
  $("builder-flow-edges").setAttribute("width", String(maximumX));
  $("builder-flow-edges").setAttribute("height", String(maximumY));
  $("builder-flow-edges").setAttribute("viewBox", `0 0 ${maximumX} ${maximumY}`);
  target.innerHTML = stateNames.map((stateName) => {
    const stateValue = states[stateName] || {};
    const position = positions[stateName] || { x: 48, y: 48 };
    const initial = stateName === state.builderDocument?.initial_state;
    const problemSummary = builderProblemSummary(stateProblems(stateName));
    const kind = stateValue.terminal ? "Terminal" : (initial ? "Initial" : "State");
    const transition = stateValue.terminal
      ? `result ${stateValue.result || "missing"}`
      : `success ${stateValue.on_success || "missing"} · failure ${stateValue.on_failure || "graceful"}`;
    return `<button type="button" class="builder-flow-node${stateName === state.selectedBuilderState ? " active" : ""}${stateValue.terminal ? " terminal" : ""}" data-builder-flow-state="${escapeHtml(stateName)}" style="left:${position.x}px;top:${position.y}px" aria-pressed="${stateName === state.selectedBuilderState ? "true" : "false"}"><strong>${escapeHtml(stateName)}</strong><span class="builder-flow-node-kind">${kind}</span><span class="builder-flow-node-transition">${escapeHtml(transition)}</span>${problemSummary.count ? `<span class="builder-flow-node-problem ${problemSummary.className}">${escapeHtml(problemSummary.label)}</span>` : ""}</button>`;
  }).join("");
  renderBuilderFlowEdges();
  renderBuilderFlowInspector();
  $("undo-builder-layout").disabled = !state.builderFlowLayout?.history?.can_undo;
  $("redo-builder-layout").disabled = !state.builderFlowLayout?.history?.can_redo;
  $("tidy-builder-flow").disabled = !stateNames.length;
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
  const selectedActions = stateValue.actions || [];
  if (!Number.isInteger(state.selectedBuilderActionIndex)
    || state.selectedBuilderActionIndex >= selectedActions.length) {
    state.selectedBuilderActionIndex = selectedActions.length ? 0 : null;
  }
  renderBuilderStateSections();
  renderBuilderActionCanvasControls();
  window.requestAnimationFrame(() => renderBuilderActionViewport());
  renderBuilderActionPalette();
  renderBuilderActionInspector();
}

const BUILDER_ACTIONS_PER_DESKTOP_COLUMN = 5;
const BUILDER_ACTION_LAYOUT_MAX_GROUPS = 3;
const BUILDER_ACTION_LAYOUT_MOBILE_MAX_GROUPS = 1;
const BUILDER_ACTION_SECTION_GUTTER_X = 64;
const BUILDER_ACTION_SECTION_GUTTER_Y = 72;
const BUILDER_ACTION_SECTION_ORIGIN_X = 72;
const BUILDER_ACTION_RESERVED_TOP = 128;
const BUILDER_ACTION_SECTION_ORIGIN_Y = BUILDER_ACTION_RESERVED_TOP + 24;
const BUILDER_ACTION_VIEWPORT_PADDING_X = 72;
const BUILDER_ACTION_VIEWPORT_PADDING_Y = 88;
const BUILDER_ACTION_FIT_MIN_ZOOM = 0.25;

function builderActionStateNames() {
  return Object.keys(state.builderDocument?.states || {});
}

function builderActionUsesSingleColumn() {
  return window.matchMedia("(max-width: 720px)").matches;
}

function builderActionColumnStarts(actionCount) {
  const count = Math.max(0, actionCount);
  const actionsPerColumn = builderActionUsesSingleColumn()
    ? Math.max(1, count)
    : BUILDER_ACTIONS_PER_DESKTOP_COLUMN;
  const columnCount = Math.max(1, Math.ceil(count / actionsPerColumn));
  return Array.from({ length: columnCount }, (_unused, columnIndex) => (
    columnIndex * actionsPerColumn
  ));
}

function builderActionSectionPosition(stateName, index) {
  const layout = state.builderActionLayout;
  if (layout.profileId !== state.builderProfileId) {
    layout.profileId = state.builderProfileId;
    layout.positions = {};
  }
  if (!layout.positions[stateName]) {
    const groupsPerRow = window.matchMedia("(max-width: 720px)").matches
      ? BUILDER_ACTION_LAYOUT_MOBILE_MAX_GROUPS
      : BUILDER_ACTION_LAYOUT_MAX_GROUPS;
    layout.positions[stateName] = {
      x: BUILDER_ACTION_SECTION_ORIGIN_X
        + (index % groupsPerRow) * (326 + BUILDER_ACTION_SECTION_GUTTER_X),
      y: BUILDER_ACTION_SECTION_ORIGIN_Y
        + Math.floor(index / groupsPerRow) * (560 + BUILDER_ACTION_SECTION_GUTTER_Y),
    };
  }
  return layout.positions[stateName];
}

function renderBuilderActionBlock(stateName, action, index) {
  const definition = actionDefinition(action.type);
  const problemSummary = builderProblemSummary(actionProblems(stateName, index));
  const selected = stateName === state.selectedBuilderState
    && index === state.selectedBuilderActionIndex;
  const status = problemSummary.count
    ? `<span class="builder-action-status ${problemSummary.className}">${escapeHtml(problemSummary.label)}</span>`
    : "";
  return `<li><button type="button" draggable="false" class="builder-action-block${action.disabled ? " disabled" : ""}" data-builder-action-state="${escapeHtml(stateName)}" data-builder-action-index="${index}" aria-current="${selected ? "true" : "false"}" aria-grabbed="false"><span class="builder-drag-handle" aria-hidden="true"><svg viewBox="0 0 12 18" width="12" height="18" fill="currentColor"><circle cx="3" cy="3" r="1.25"/><circle cx="9" cy="3" r="1.25"/><circle cx="3" cy="9" r="1.25"/><circle cx="9" cy="9" r="1.25"/><circle cx="3" cy="15" r="1.25"/><circle cx="9" cy="15" r="1.25"/></svg></span><span class="builder-action-copy"><strong>${index + 1}. ${escapeHtml(definition?.label || action.type || "Action")}</strong><span>${escapeHtml(action.type || "unknown")}</span><span>${escapeHtml(formatActionSummary(action, definition))}</span>${status}</span></button></li>`;
}

function renderBuilderStateSections() {
  const target = $("builder-state-sections");
  const states = state.builderDocument?.states || {};
  const stateNames = Object.keys(states);
  const needsInitialLayout = Boolean(state.builderProfileId)
    && (state.builderActionInitialLayoutProfileId !== state.builderProfileId
      || state.builderActionInitialLayoutCompletedActivation
        !== state.builderActionInitialLayoutActivation);
  state.builderActionColumnLayoutMobile = builderActionUsesSingleColumn();
  target.classList.toggle("initial-layout-pending", needsInitialLayout);
  target.setAttribute("aria-busy", String(needsInitialLayout));
  target.innerHTML = stateNames.map((stateName, stateIndex) => {
    const stateValue = states[stateName] || {};
    const position = builderActionSectionPosition(stateName, stateIndex);
    const actionValues = stateValue.actions || [];
    const columns = [];
    for (const start of builderActionColumnStarts(actionValues.length)) {
      const actionsPerColumn = builderActionUsesSingleColumn()
        ? Math.max(1, actionValues.length)
        : BUILDER_ACTIONS_PER_DESKTOP_COLUMN;
      const chunk = actionValues.slice(start, start + actionsPerColumn);
      const actionItems = chunk.length
        ? chunk.map((action, offset) => renderBuilderActionBlock(stateName, action, start + offset)).join("")
        : '<li class="builder-state-section-empty muted">No Actions. Drop an Action here.</li>';
      columns.push(`<div class="builder-action-column"><ol class="builder-action-list" data-builder-action-state="${escapeHtml(stateName)}" data-builder-action-column="${columns.length}" start="${start + 1}">${actionItems}</ol></div>`);
    }
    const kind = stateValue.terminal
      ? "Terminal"
      : (stateName === state.builderDocument?.initial_state ? "Initial" : "State");
    const active = stateName === state.selectedBuilderState;
    return `<section class="builder-state-section${active ? " active" : ""}" data-builder-state-section="${escapeHtml(stateName)}" role="listitem" aria-current="${active ? "true" : "false"}" style="left:${position.x}px;top:${position.y}px"><button type="button" class="builder-state-roof" data-builder-state-section-handle="${escapeHtml(stateName)}" aria-grabbed="false" aria-label="${escapeHtml(`Move ${stateName} layout only`)}"><strong class="builder-state-name">${escapeHtml(stateName)}</strong><span class="builder-state-kind">${kind}</span></button><div class="builder-action-start" data-builder-action-start>Start</div><svg class="builder-state-action-connectors" data-builder-state-connectors="${escapeHtml(stateName)}" aria-hidden="true"></svg><div class="builder-state-action-columns">${columns.join("")}</div></section>`;
  }).join("");
  window.requestAnimationFrame(() => {
    if (ensureInitialBuilderActionLayout()) return;
    renderBuilderActionConnectors();
    renderBuilderStateMinimap();
    renderBuilderActionViewport();
  });
}

function builderOffsetWithin(element, ancestor) {
  let x = 0;
  let y = 0;
  for (let node = element; node && node !== ancestor; node = node.offsetParent) {
    x += node.offsetLeft;
    y += node.offsetTop;
  }
  return { x, y };
}

function builderActionManhattanPath(points) {
  return points.map(([x, y], index) => `${index ? "L" : "M"} ${x} ${y}`).join(" ");
}

function renderBuilderActionConnectors() {
  const sections = [...document.querySelectorAll("[data-builder-state-section]")];
  for (const [sectionIndex, section] of sections.entries()) {
    const svg = section.querySelector("[data-builder-state-connectors]");
    const start = section.querySelector("[data-builder-action-start]");
    const blocks = [...section.querySelectorAll("[data-builder-action-index]")]
      .sort((left, right) => (
        Number(left.dataset.builderActionIndex) - Number(right.dataset.builderActionIndex)
      ));
    if (!svg) continue;
    Object.assign(svg.style, {
      position: "absolute",
      inset: "0",
      zIndex: "0",
      overflow: "visible",
      pointerEvents: "none",
    });
    svg.setAttribute("width", String(section.offsetWidth));
    svg.setAttribute("height", String(section.offsetHeight));
    svg.setAttribute("viewBox", `0 0 ${section.offsetWidth} ${section.offsetHeight}`);
    const markerId = `builder-action-arrow-${sectionIndex}`;
    const paths = [`<defs><marker id="${markerId}" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 8 4 L 0 8 z" fill="var(--state-accent)"></path></marker></defs>`];
    if (start && blocks.length) {
      const first = blocks[0];
      const startPosition = builderOffsetWithin(start, section);
      const firstPosition = builderOffsetWithin(first, section);
      const x1 = startPosition.x + start.offsetWidth / 2;
      const y1 = startPosition.y + start.offsetHeight;
      const x2 = firstPosition.x + first.offsetWidth / 2;
      const y2 = firstPosition.y;
      const routeY = y1 + Math.max(8, (y2 - y1) / 2);
      const path = builderActionManhattanPath([
        [x1, y1], [x1, routeY], [x2, routeY], [x2, y2],
      ]);
      paths.push(`<g class="builder-action-connector start" data-builder-action-connector-start><path d="${path}" fill="none" stroke="var(--state-accent)" stroke-width="2" vector-effect="non-scaling-stroke" marker-end="url(#${markerId})"></path></g>`);
    }
    for (let index = 0; index < blocks.length - 1; index += 1) {
      const current = blocks[index];
      const next = blocks[index + 1];
      const currentPosition = builderOffsetWithin(current, section);
      const nextPosition = builderOffsetWithin(next, section);
      const x1 = currentPosition.x + current.offsetWidth / 2;
      const y1 = currentPosition.y + current.offsetHeight;
      const x2 = nextPosition.x + next.offsetWidth / 2;
      const y2 = nextPosition.y;
      const sameColumn = window.matchMedia("(max-width: 720px)").matches
        || current.closest(".builder-action-column") === next.closest(".builder-action-column");
      let path;
      let label = "";
      if (sameColumn) {
        const routeY = y1 + Math.max(8, (y2 - y1) / 2);
        path = builderActionManhattanPath([
          [x1, y1], [x1, routeY], [x2, routeY], [x2, y2],
        ]);
      } else {
        const currentColumn = current.closest(".builder-action-column");
        const nextColumn = next.closest(".builder-action-column");
        const currentColumnPosition = builderOffsetWithin(currentColumn, section);
        const nextColumnPosition = builderOffsetWithin(nextColumn, section);
        const leftColumn = currentColumnPosition.x <= nextColumnPosition.x
          ? { element: currentColumn, position: currentColumnPosition }
          : { element: nextColumn, position: nextColumnPosition };
        const rightColumn = leftColumn.element === currentColumn
          ? { element: nextColumn, position: nextColumnPosition }
          : { element: currentColumn, position: currentColumnPosition };
        const gutterX = (leftColumn.position.x + leftColumn.element.offsetWidth
          + rightColumn.position.x) / 2;
        const routeY = Math.max(18, y2 - 18);
        path = builderActionManhattanPath([
          [x1, y1], [gutterX, y1], [gutterX, routeY], [x2, routeY], [x2, y2],
        ]);
        label = `<text class="builder-action-connector-label" data-builder-action-connector-label x="${gutterX}" y="${Math.max(12, routeY - 7)}" fill="var(--state-accent)" font-size="10" text-anchor="middle">Next</text>`;
      }
      paths.push(
        `<g class="builder-action-connector${sameColumn ? " same-column" : " cross-column"}" data-builder-action-connector-from="${current.dataset.builderActionIndex}" data-builder-action-connector-to="${next.dataset.builderActionIndex}"><path d="${path}" fill="none" stroke="var(--state-accent)" stroke-width="2" vector-effect="non-scaling-stroke" marker-end="url(#${markerId})"></path>${label}</g>`,
      );
    }
    svg.innerHTML = paths.join("");
  }
}

function renderBuilderStateOverview() {
  const overview = $("builder-state-overview");
  const toggle = $("builder-all-states-button");
  if (!overview || !toggle) return;
  overview.hidden = !state.builderActionOverviewOpen;
  toggle.setAttribute("aria-expanded", String(state.builderActionOverviewOpen));
}

function renderBuilderStateMinimap() {
  const minimap = $("builder-state-minimap");
  const canvas = $("builder-state-detail");
  const container = $("builder-state-sections");
  if (!minimap || !canvas || !container) return;
  const world = builderActionWorldBounds();
  const viewport = state.builderActionViewport;
  const scaleX = 100 / world.width;
  const scaleY = 100 / world.height;
  const sections = [...document.querySelectorAll("[data-builder-state-section]")];
  const signature = JSON.stringify(sections.map((section) => [
    section.dataset.builderStateSection,
    section.offsetLeft,
    section.offsetTop,
    section.offsetWidth,
    section.offsetHeight,
    section.dataset.builderStateSection === state.selectedBuilderState,
  ]));
  if (!state.builderActionSectionDrag
    && signature !== state.builderStateMinimapSignature) {
    const footprints = sections.map((section) => {
      const stateName = section.dataset.builderStateSection;
      const left = (container.offsetLeft + section.offsetLeft) * scaleX;
      const top = (container.offsetTop + section.offsetTop) * scaleY;
      const width = Math.max(1.5, section.offsetWidth * scaleX);
      const height = Math.max(2, section.offsetHeight * scaleY);
      const active = stateName === state.selectedBuilderState ? " active" : "";
      return `<button type="button" class="builder-state-minimap-section${active}" data-builder-minimap-state="${escapeHtml(stateName)}" title="${escapeHtml(stateName)}" aria-label="${escapeHtml(`Center ${stateName}`)}" style="left:${left}%;top:${top}%;width:${width}%;height:${height}%"></button>`;
    });
    footprints.push(
      '<span class="builder-state-minimap-viewport" aria-hidden="true"></span>',
    );
    minimap.innerHTML = footprints.join("");
    state.builderStateMinimapSignature = signature;
  }
  const visibleLeft = Math.max(0, -viewport.x / viewport.zoom);
  const visibleTop = Math.max(0, -viewport.y / viewport.zoom);
  const visibleWidth = Math.min(world.width, canvas.clientWidth / viewport.zoom);
  const visibleHeight = Math.min(world.height, canvas.clientHeight / viewport.zoom);
  const viewportNode = minimap.querySelector(".builder-state-minimap-viewport");
  if (viewportNode) {
    viewportNode.style.left = `${visibleLeft * scaleX}%`;
    viewportNode.style.top = `${visibleTop * scaleY}%`;
    viewportNode.style.width = `${visibleWidth * scaleX}%`;
    viewportNode.style.height = `${visibleHeight * scaleY}%`;
  }
}

function autoOrganizeBuilderActionLayout({ announce = true } = {}) {
  const sections = [...document.querySelectorAll("[data-builder-state-section]")];
  if (!sections.length) return;
  const canvas = $("builder-state-detail");
  const groupsPerRow = window.matchMedia("(max-width: 720px)").matches
    ? BUILDER_ACTION_LAYOUT_MOBILE_MAX_GROUPS
    : BUILDER_ACTION_LAYOUT_MAX_GROUPS;
  const maximumRowRight = Math.max(
    BUILDER_ACTION_SECTION_ORIGIN_X + 1,
    (canvas?.clientWidth || 0) - BUILDER_ACTION_SECTION_ORIGIN_X,
  );
  let x = BUILDER_ACTION_SECTION_ORIGIN_X;
  let y = BUILDER_ACTION_SECTION_ORIGIN_Y;
  let rowHeight = 0;
  let groupsInRow = 0;
  const positions = {};
  for (const section of sections) {
    const width = section.offsetWidth;
    const height = section.offsetHeight;
    if (groupsInRow > 0 && (
      groupsInRow === groupsPerRow || x + width > maximumRowRight
    )) {
      x = BUILDER_ACTION_SECTION_ORIGIN_X;
      y += rowHeight + BUILDER_ACTION_SECTION_GUTTER_Y;
      rowHeight = 0;
      groupsInRow = 0;
    }
    positions[section.dataset.builderStateSection] = { x, y };
    x += width + BUILDER_ACTION_SECTION_GUTTER_X;
    rowHeight = Math.max(rowHeight, height);
    groupsInRow += 1;
  }
  state.builderActionLayout = {
    profileId: state.builderProfileId,
    positions,
  };
  state.builderActionInitialLayoutProfileId = state.builderProfileId;
  state.builderActionInitialLayoutCompletedActivation
    = state.builderActionInitialLayoutActivation;
  renderBuilderStateSections();
  window.requestAnimationFrame(() => renderBuilderActionViewport({ reset: true }));
  if (announce) showNotice("State sections auto-organized for this browser session.", "good");
}

function ensureInitialBuilderActionLayout() {
  if (!state.builderProfileId
    || state.builderActionInitialLayoutProfileId === state.builderProfileId
    || !document.querySelector("[data-builder-state-section]")) return false;
  autoOrganizeBuilderActionLayout({ announce: false });
  return true;
}

function bestBuilderStateMatch(query) {
  const stateNames = builderActionStateNames();
  const needle = query.trim().toLocaleLowerCase();
  if (!needle) return state.selectedBuilderState || stateNames[0] || null;
  return stateNames.find((name) => name.toLocaleLowerCase() === needle)
    || stateNames.find((name) => name.toLocaleLowerCase().startsWith(needle))
    || stateNames.find((name) => name.toLocaleLowerCase().includes(needle))
    || null;
}

function selectAndCenterBuilderState(stateName, { smooth = true } = {}) {
  if (!stateName || !state.builderDocument?.states?.[stateName]) return;
  state.selectedBuilderState = stateName;
  const actions = state.builderDocument.states[stateName]?.actions || [];
  if (!Number.isInteger(state.selectedBuilderActionIndex)
    || state.selectedBuilderActionIndex >= actions.length) {
    state.selectedBuilderActionIndex = actions.length ? 0 : null;
  }
  state.builderActionOverviewOpen = false;
  renderBuilderDocument();
  renderBuilderStateOverview();
  window.requestAnimationFrame(() => centerBuilderActionState(stateName, { smooth }));
}

function renderBuilderActionCanvasControls() {
  const library = $("builder-action-library");
  library.classList.toggle("collapsed", state.builderActionLibraryCollapsed);
  library.classList.toggle("canvas-hidden", state.builderActionLibraryHidden);
  $("builder-action-library-body").hidden = state.builderActionLibraryCollapsed;
  $("collapse-builder-action-library").textContent = state.builderActionLibraryCollapsed ? "+" : "−";
  $("collapse-builder-action-library").setAttribute(
    "aria-label",
    state.builderActionLibraryCollapsed ? "Expand Action Library" : "Collapse Action Library",
  );
  $("collapse-builder-action-library").setAttribute(
    "aria-expanded",
    String(!state.builderActionLibraryCollapsed),
  );
  $("toggle-builder-action-library").textContent = state.builderActionLibraryHidden
    ? "Show Library"
    : "Hide Library";
  $("toggle-builder-action-library").setAttribute(
    "aria-expanded",
    String(!state.builderActionLibraryHidden),
  );
  $("builder-action-inspector").classList.toggle(
    "collapsed",
    state.builderActionInspectorCollapsed,
  );
  $("toggle-builder-action-inspector").textContent = state.builderActionInspectorCollapsed
    ? "Show Inspector"
    : "Hide Inspector";
  $("toggle-builder-action-inspector").setAttribute(
    "aria-expanded",
    String(!state.builderActionInspectorCollapsed),
  );
  const navigationExpanded = !state.builderActionNavigationCollapsed;
  $("builder-state-navigation-content").hidden = !navigationExpanded;
  $("toggle-builder-state-navigation").textContent = navigationExpanded
    ? "Hide State navigation"
    : "Show State navigation";
  $("toggle-builder-state-navigation").setAttribute("aria-expanded", String(navigationExpanded));
  $("builder-selected-state-summary").textContent = state.selectedBuilderState || "No State selected";
  renderBuilderStateOverview();
}

function builderActionWorldBounds() {
  const container = $("builder-state-sections");
  const sections = [...document.querySelectorAll("[data-builder-state-section]")];
  if (!container || !sections.length) return { width: 960, height: 760 };
  let width = 1;
  let height = 1;
  for (const section of sections) {
    width = Math.max(
      width,
      container.offsetLeft + section.offsetLeft + section.offsetWidth,
    );
    height = Math.max(
      height,
      container.offsetTop + section.offsetTop + section.offsetHeight,
    );
  }
  return { width, height };
}

function builderActionContentBounds() {
  const container = $("builder-state-sections");
  const sections = [...document.querySelectorAll("[data-builder-state-section]")];
  if (!container || !sections.length) {
    return { left: 0, top: 0, right: 960, bottom: 760, width: 960, height: 760 };
  }
  const left = Math.min(...sections.map((section) => container.offsetLeft + section.offsetLeft));
  const top = Math.min(...sections.map((section) => container.offsetTop + section.offsetTop));
  const right = Math.max(...sections.map(
    (section) => container.offsetLeft + section.offsetLeft + section.offsetWidth,
  ));
  const bottom = Math.max(...sections.map(
    (section) => container.offsetTop + section.offsetTop + section.offsetHeight,
  ));
  return {
    left,
    top,
    right,
    bottom,
    width: right - left,
    height: bottom - top,
  };
}

function normalizeBuilderActionViewport() {
  const viewport = state.builderActionViewport;
  if (!Number.isFinite(viewport.x)) viewport.x = 0;
  if (!Number.isFinite(viewport.y)) viewport.y = 0;
  if (!Number.isFinite(viewport.zoom) || viewport.zoom <= 0) viewport.zoom = 1;
}

function renderBuilderActionViewport({ reset = false } = {}) {
  const canvas = $("builder-state-detail");
  const world = $("builder-action-world");
  const viewport = state.builderActionViewport;
  if (!canvas || !world || canvas.clientWidth === 0 || canvas.clientHeight === 0) return;
  if (viewport.profileId !== state.builderProfileId) {
    viewport.profileId = state.builderProfileId;
    viewport.initialized = false;
  }
  if (reset || !viewport.initialized) {
    const content = builderActionContentBounds();
    const availableWidth = Math.max(
      240,
      canvas.clientWidth - BUILDER_ACTION_VIEWPORT_PADDING_X * 2,
    );
    const availableHeight = Math.max(
      180,
      canvas.clientHeight - BUILDER_ACTION_VIEWPORT_PADDING_Y * 2,
    );
    viewport.zoom = Math.min(
      1,
      BUILDER_ACTION_MAX_ZOOM,
      Math.max(
        BUILDER_ACTION_FIT_MIN_ZOOM,
        Math.min(availableWidth / content.width, availableHeight / content.height),
      ),
    );
    viewport.x = canvas.clientWidth / 2
      - (content.left + content.width / 2) * viewport.zoom;
    viewport.y = (canvas.clientHeight + 120) / 2
      - (content.top + content.height / 2) * viewport.zoom;
    viewport.initialized = true;
  }
  // State Actions is a virtual canvas, not a native scroll container. Focus and
  // pointer automation can otherwise retain a hidden scroll offset that is not
  // represented by viewport.x/y and makes rendered content appear displaced.
  canvas.scrollLeft = 0;
  canvas.scrollTop = 0;
  const worldBounds = builderActionWorldBounds();
  world.style.width = `${worldBounds.width}px`;
  world.style.height = `${worldBounds.height}px`;
  // World dimensions support section layout and the minimap only. The canvas
  // deliberately does not clamp x/y to them, so panning remains unbounded.
  normalizeBuilderActionViewport();
  const deviceScale = window.devicePixelRatio || 1;
  const renderedX = Math.round(viewport.x * deviceScale) / deviceScale;
  const renderedY = Math.round(viewport.y * deviceScale) / deviceScale;
  // CSS zoom lays out and paints DOM text at the requested scale. Keeping scale
  // out of transform avoids repeatedly raster-scaling the whole Action stack.
  world.style.zoom = String(viewport.zoom);
  world.style.transform = `translate(${renderedX / viewport.zoom}px, ${renderedY / viewport.zoom}px)`;
  canvas.style.backgroundPosition = `${renderedX}px ${renderedY}px`;
  canvas.style.backgroundSize = `${24 * viewport.zoom}px ${24 * viewport.zoom}px`;
  $("builder-canvas-zoom-value").textContent = `${Math.round(viewport.zoom * 100)}%`;
  renderBuilderStateMinimap();
}

let builderActionViewportFrame = null;

function scheduleBuilderActionViewportRender() {
  if (builderActionViewportFrame !== null) return;
  builderActionViewportFrame = window.requestAnimationFrame(() => {
    builderActionViewportFrame = null;
    renderBuilderActionViewport();
  });
}

function zoomBuilderActionCanvas(nextZoom, clientX = null, clientY = null) {
  cancelBuilderActionCentering();
  const canvas = $("builder-state-detail");
  const bounds = canvas.getBoundingClientRect();
  const viewport = state.builderActionViewport;
  const zoom = Math.min(
    BUILDER_ACTION_MAX_ZOOM,
    Math.max(BUILDER_ACTION_MIN_ZOOM, nextZoom),
  );
  if (Math.abs(zoom - viewport.zoom) < 0.001) return;
  const localX = clientX === null ? canvas.clientWidth / 2 : clientX - bounds.left;
  const localY = clientY === null ? canvas.clientHeight / 2 : clientY - bounds.top;
  const worldX = (localX - viewport.x) / viewport.zoom;
  const worldY = (localY - viewport.y) / viewport.zoom;
  viewport.x = localX - worldX * zoom;
  viewport.y = localY - worldY * zoom;
  viewport.zoom = zoom;
  viewport.initialized = true;
  renderBuilderActionViewport();
}

let builderActionCenterFrame = null;

function cancelBuilderActionCentering() {
  if (builderActionCenterFrame === null) return;
  window.cancelAnimationFrame(builderActionCenterFrame);
  builderActionCenterFrame = null;
}

function centerBuilderActionState(stateName, { smooth = true } = {}) {
  const canvas = $("builder-state-detail");
  const container = $("builder-state-sections");
  const section = document.querySelector(`[data-builder-state-section="${CSS.escape(stateName)}"]`);
  if (!canvas || !section) return;
  const viewport = state.builderActionViewport;
  const canvasBounds = canvas.getBoundingClientRect();
  const selectorBounds = $("builder-state-list").getBoundingClientRect();
  const headingBounds = document.querySelector(".builder-workspace-toolbar")
    ?.getBoundingClientRect();
  const focusTop = Math.max(
    16,
    selectorBounds.bottom - canvasBounds.top + 12,
    (headingBounds?.bottom || canvasBounds.top) - canvasBounds.top + 12,
  );
  const focusBottom = canvas.clientHeight - 16;
  const renderedSectionHeight = section.offsetHeight * viewport.zoom;
  const focusHeight = Math.max(0, focusBottom - focusTop);
  const sectionTop = renderedSectionHeight >= focusHeight
    ? focusTop
    : focusTop + (focusHeight - renderedSectionHeight) / 2;
  const targetX = canvas.clientWidth / 2
    - (container.offsetLeft + section.offsetLeft + section.offsetWidth / 2) * viewport.zoom;
  const targetY = sectionTop
    - (container.offsetTop + section.offsetTop) * viewport.zoom;
  cancelBuilderActionCentering();
  if (!smooth || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    viewport.x = targetX;
    viewport.y = targetY;
    renderBuilderActionViewport();
    return;
  }
  const originX = viewport.x;
  const originY = viewport.y;
  const startedAt = performance.now();
  const tick = (now) => {
    const progress = Math.min(1, (now - startedAt) / 260);
    const eased = 1 - (1 - progress) ** 3;
    viewport.x = originX + (targetX - originX) * eased;
    viewport.y = originY + (targetY - originY) * eased;
    renderBuilderActionViewport();
    if (progress < 1) builderActionCenterFrame = window.requestAnimationFrame(tick);
    else builderActionCenterFrame = null;
  };
  builderActionCenterFrame = window.requestAnimationFrame(tick);
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
    ? definitions.map((definition) => `<button type="button" draggable="true" data-add-builder-action="${escapeHtml(definition.type)}" role="listitem" aria-grabbed="false" ${state.structuredMutationPending ? "disabled" : ""}><strong>${escapeHtml(definition.label)}</strong><span>${escapeHtml(definition.type)}</span></button>`).join("")
    : '<span class="muted">No matching structured Actions.</span>';
}

function actionProblems(stateName, actionIndex) {
  const prefix = `states.${stateName}.actions[${actionIndex}]`;
  return (state.builderDraft?.problems || []).filter((problem) => problem.location?.startsWith(prefix));
}

function builderProblemSummary(problems) {
  const warningCount = problems.filter((problem) => problem.severity === "warning").length;
  const errorCount = problems.length - warningCount;
  const parts = [];
  if (errorCount) parts.push(`${errorCount} error${errorCount === 1 ? "" : "s"}`);
  if (warningCount) parts.push(`${warningCount} warning${warningCount === 1 ? "" : "s"}`);
  return {
    count: problems.length,
    label: parts.join(", "),
    className: errorCount ? "bad" : "warn",
  };
}

function stateProblems(stateName) {
  const prefix = `states.${stateName}`;
  return (state.builderDraft?.problems || [])
    .filter((problem) => problem.location === prefix || problem.location?.startsWith(`${prefix}.`));
}

function builderFieldLabel(fieldName) {
  return fieldName
    .split("_")
    .map((part) => `${part.slice(0, 1).toUpperCase()}${part.slice(1)}`)
    .join(" ");
}

function builderFieldOptions(field) {
  if (field.choices?.length) return field.choices;
  if (field.kind === "state") return Object.keys(state.builderDocument?.states || {});
  if (field.kind === "region") return Object.keys(state.builderDocument?.regions || {});
  return null;
}

function renderBuilderInspectorField(field, action, stateName, actionIndex) {
  const fieldId = `builder-action-field-${field.name.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
  const hintId = `${fieldId}-hint`;
  const value = action[field.name] ?? "";
  const fieldProblems = actionProblems(stateName, actionIndex)
    .filter((problem) => problem.location?.endsWith(`.${field.name}`));
  const describedBy = `${hintId} builder-inspector-errors`;
  const common = `id="${fieldId}" name="${escapeHtml(field.name)}" data-builder-action-field="${escapeHtml(field.name)}" data-builder-field-kind="${escapeHtml(field.kind)}" data-builder-field-required="${field.required ? "true" : "false"}" aria-invalid="${fieldProblems.length ? "true" : "false"}" aria-describedby="${describedBy}" ${field.required ? "required" : ""}`;
  const options = builderFieldOptions(field);
  let control;
  if (options) {
    const optionValues = [
      `<option value="">${field.required ? "Select…" : "Use default"}</option>`,
      ...options.map((option) => `<option value="${escapeHtml(option)}" ${String(value) === String(option) ? "selected" : ""}>${escapeHtml(option)}</option>`),
    ];
    control = `<select ${common}>${optionValues.join("")}</select>`;
  } else if (["duration", "positive_duration", "number", "positive_integer"].includes(field.kind)) {
    const minimum = field.kind === "positive_duration" || field.kind === "positive_integer"
      ? ' min="0.000001"'
      : (field.kind === "duration" ? ' min="0"' : "");
    const step = field.kind === "positive_integer" ? ' step="1"' : ' step="any"';
    control = `<input ${common} type="number" inputmode="decimal"${minimum}${step} value="${escapeHtml(value)}">`;
  } else {
    const spellcheck = field.kind === "key" ? ' spellcheck="false" autocomplete="off"' : "";
    control = `<input ${common} type="text"${spellcheck} value="${escapeHtml(value)}">`;
  }
  return `
    <div class="builder-inspector-field">
      <label for="${fieldId}">${escapeHtml(builderFieldLabel(field.name))}${field.required ? " *" : ""}</label>
      ${control}
      <span id="${hintId}" class="muted">${escapeHtml(field.hint || (field.required ? "Required." : "Optional."))}</span>
    </div>
  `;
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
  if (definition?.structured) {
    fields.innerHTML = definition.fields?.length
      ? definition.fields
        .map((field) => renderBuilderInspectorField(
          field,
          action,
          state.selectedBuilderState,
          index,
        ))
        .join("")
      : '<p class="muted">This Action has no additional settings.</p>';
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
  const summary = builderProblemSummary(problems);
  $("builder-problem-count").textContent = String(problems.length);
  $("builder-problem-count").className = `badge ${problems.length ? summary.className : "good"}`;
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

function confirmBuilderDiff(preview) {
  const dialog = $("builder-diff-dialog");
  $("builder-diff-preview").textContent = preview.diff || "No textual change.";
  $("builder-diff-comment-warning").hidden = !preview.comment_changes;
  dialog.returnValue = "cancel";
  dialog.showModal();
  return new Promise((resolve) => {
    dialog.addEventListener(
      "close",
      () => resolve(dialog.returnValue === "confirm"),
      { once: true },
    );
  });
}

async function mutateBuilderAction(
  mutation,
  { focusIndex = null, focusField = null, focusState = null } = {},
) {
  const profileId = state.builderProfileId;
  if (!profileId || state.structuredMutationPending) return;
  await flushBuilderInspectorEdit();
  await flushBuilderAutosave({ includeInspector: false });
  let confirmedPreviewFingerprint = null;
  if (["move", "move_to_state", "duplicate", "delete"].includes(mutation.operation)) {
    const preview = await api(
      `/api/profiles/${encodeURIComponent(profileId)}/actions/preview`,
      {
        method: "POST",
        body: JSON.stringify({
          expected_version: state.builderDraft?.version,
          expected_fingerprint: state.builderDraft?.draft_fingerprint,
          mutation,
        }),
      },
    );
    if (preview.requires_confirmation) {
      const confirmed = await confirmBuilderDiff(preview);
      if (!confirmed) {
        showNotice("Structured Draft change cancelled.", "good");
        return;
      }
      confirmedPreviewFingerprint = preview.updated_fingerprint;
    }
  }
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
        confirmed_preview_fingerprint: confirmedPreviewFingerprint,
        mutation,
      }),
    });
    if (profileId !== state.builderProfileId) return;
    if (focusState) state.selectedBuilderState = focusState;
    state.selectedBuilderActionIndex = focusIndex;
    applyStructuredDraft(draft);
    if (["insert", "move", "duplicate"].includes(mutation.operation)) {
      settleBuilderAction(focusIndex);
    }
    showNotice(`${mutation.operation[0].toUpperCase()}${mutation.operation.slice(1)} Action completed.`, draft.valid ? "good" : "error");
    window.requestAnimationFrame(() => {
      const selector = focusField
        ? `[data-builder-action-field="${focusField}"]`
        : `[data-builder-action-state="${CSS.escape(state.selectedBuilderState)}"][data-builder-action-index="${state.selectedBuilderActionIndex}"]`;
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

async function mutateBuilderFlow(mutation) {
  const profileId = state.builderProfileId;
  if (!profileId || state.structuredMutationPending) return;
  await flushBuilderAutosave();
  let confirmedPreviewFingerprint = null;
  const preview = await api(
    `/api/profiles/${encodeURIComponent(profileId)}/flow/preview`,
    {
      method: "POST",
      body: JSON.stringify({
        expected_version: state.builderDraft?.version,
        expected_fingerprint: state.builderDraft?.draft_fingerprint,
        mutation,
      }),
    },
  );
  if (preview.requires_confirmation) {
    const confirmed = await confirmBuilderDiff(preview);
    if (!confirmed) {
      renderBuilderFlowInspector();
      showNotice("Flow change cancelled.", "good");
      return;
    }
    confirmedPreviewFingerprint = preview.updated_fingerprint;
  }
  state.structuredMutationPending = true;
  renderBuilderDraft();
  renderBuilderFlowInspector();
  try {
    const draft = await api(`/api/profiles/${encodeURIComponent(profileId)}/flow`, {
      method: "POST",
      body: JSON.stringify({
        expected_version: state.builderDraft?.version,
        expected_fingerprint: state.builderDraft?.draft_fingerprint,
        confirmed_preview_fingerprint: confirmedPreviewFingerprint,
        mutation,
      }),
    });
    if (profileId !== state.builderProfileId) return;
    applyStructuredDraft(draft);
    showNotice("State settings updated in the recoverable Draft.", draft.valid ? "good" : "error");
    window.requestAnimationFrame(() => {
      document.querySelector(`[data-builder-flow-state="${state.selectedBuilderState}"]`)?.focus();
    });
  } catch (error) {
    if (error.status === 409) await refreshBuilderProfile();
    throw error;
  } finally {
    if (profileId === state.builderProfileId) {
      state.structuredMutationPending = false;
      renderBuilderDraft();
      renderBuilderFlowInspector();
    }
  }
}

async function saveBuilderFlowLayout(positions) {
  const profileId = state.builderProfileId;
  if (!profileId || !state.builderFlowLayout) return;
  try {
    state.builderFlowLayout = await api(
      `/api/profiles/${encodeURIComponent(profileId)}/flow-layout`,
      {
        method: "POST",
        body: JSON.stringify({
          expected_version: state.builderFlowLayout.version,
          positions,
        }),
      },
    );
    renderBuilderFlowGraph();
  } catch (error) {
    try {
      state.builderFlowLayout = await api(
        `/api/profiles/${encodeURIComponent(profileId)}/flow-layout`,
      );
      renderBuilderFlowGraph();
    } catch (_refreshError) {
      // Keep the original save error as the actionable failure.
    }
    throw error;
  }
}

async function tidyBuilderFlowLayout() {
  const profileId = state.builderProfileId;
  if (!profileId || !state.builderFlowLayout) return;
  state.builderFlowLayout = await api(
    `/api/profiles/${encodeURIComponent(profileId)}/flow-layout/tidy`,
    {
      method: "POST",
      body: JSON.stringify({
        expected_version: state.builderFlowLayout.version,
      }),
    },
  );
  renderBuilderFlowGraph();
  showNotice("Flow layout tidied. Profile YAML was not changed.", "good");
}

async function restoreBuilderFlowLayout(direction) {
  const profileId = state.builderProfileId;
  if (!profileId || !state.builderFlowLayout) return;
  state.builderFlowLayout = await api(
    `/api/profiles/${encodeURIComponent(profileId)}/flow-layout/${direction}`,
    {
      method: "POST",
      body: JSON.stringify({
        expected_version: state.builderFlowLayout.version,
      }),
    },
  );
  renderBuilderFlowGraph();
  showNotice(`${direction === "undo" ? "Undo" : "Redo"} layout completed.`, "good");
}

async function nudgeBuilderFlowNode(deltaX, deltaY) {
  const stateName = state.selectedBuilderState;
  const current = builderFlowPositions()[stateName];
  if (!stateName || !current) return;
  const positions = structuredClone(builderFlowPositions());
  positions[stateName] = {
    x: Math.max(0, current.x + deltaX),
    y: Math.max(0, current.y + deltaY),
  };
  await saveBuilderFlowLayout(positions);
  window.requestAnimationFrame(() => {
    document.querySelector(`[data-builder-flow-state="${stateName}"]`)?.focus();
  });
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

function defaultBuilderActionFields(actionType) {
  const definition = actionDefinition(actionType);
  return Object.fromEntries(
    (definition?.fields || [])
      .filter((field) => field.default !== undefined)
      .map((field) => [field.name, field.default]),
  );
}

function insertBuilderAction(actionType, index, stateName = state.selectedBuilderState) {
  const definition = actionDefinition(actionType);
  state.selectedBuilderState = stateName;
  state.selectedBuilderActionIndex = index;
  return mutateBuilderAction(
    {
      operation: "insert",
      state: stateName,
      index,
      action_type: actionType,
      fields: defaultBuilderActionFields(actionType),
    },
    {
      focusIndex: index,
      focusField: definition?.fields?.[0]?.name || null,
    },
  );
}

function clearBuilderDrag({ restoreFocus = false } = {}) {
  const drag = state.builderDrag;
  stopBuilderActionAutoPan();
  document.querySelector("#builder-drop-indicator")?.remove();
  document.querySelectorAll(".builder-state-node.drag-target")
    .forEach((node) => node.classList.remove("drag-target"));
  document.querySelectorAll('[aria-grabbed="true"]')
    .forEach((node) => node.setAttribute("aria-grabbed", "false"));
  state.builderDrag = null;
  state.builderDropSlot = null;
  state.builderDropState = null;
  setBuilderActionDragStatus("");
  if (restoreFocus && drag) {
    window.requestAnimationFrame(() => {
      const selector = drag.kind === "palette"
        ? `[data-add-builder-action="${drag.actionType}"]`
        : `[data-builder-action-state="${CSS.escape(drag.state)}"][data-builder-action-index="${drag.index}"]`;
      document.querySelector(selector)?.focus();
    });
  }
}

function setBuilderActionDragStatus(message) {
  const status = $("builder-action-drag-status");
  if (status.textContent !== message) status.textContent = message;
}

function showBuilderDropIndicator(list, slot) {
  const existing = document.querySelector("#builder-drop-indicator");
  if (
    existing
    && existing.parentElement === list
    && state.builderDropSlot === slot
  ) return;
  existing?.remove();
  const indicator = document.createElement("li");
  indicator.id = "builder-drop-indicator";
  indicator.className = "builder-drop-indicator";
  indicator.setAttribute("aria-hidden", "true");
  const actionItems = [...list.children]
    .filter((item) => item.id !== "builder-drop-indicator");
  let previous = null;
  for (const item of actionItems) {
    const block = item.querySelector("[data-builder-action-index]");
    if (block && Number(block.dataset.builderActionIndex) < slot) previous = item;
  }
  const next = actionItems.find((item) => {
    const block = item.querySelector("[data-builder-action-index]");
    return block && Number(block.dataset.builderActionIndex) >= slot;
  }) || null;
  const grooveCenter = previous && next
    ? (previous.offsetTop + previous.offsetHeight + next.offsetTop) / 2
    : previous
      ? previous.offsetTop + previous.offsetHeight + 12
      : next
        ? Math.max(11, next.offsetTop - 12)
        : 18;
  indicator.style.top = `${Math.max(0, grooveCenter - 11)}px`;
  list.appendChild(indicator);
  state.builderDropSlot = slot;
  setBuilderActionDragStatus(
    `Valid insertion groove ${slot + 1} of ${actionItems.length + 1}.`,
  );
}

function builderDropSlot(list, clientY) {
  const blocks = [...list.querySelectorAll(
    "[data-builder-action-index]",
  )];
  for (const block of blocks) {
    const bounds = block.getBoundingClientRect();
    if (clientY < bounds.top + bounds.height / 2) {
      return Number(block.dataset.builderActionIndex);
    }
  }
  return blocks.length
    ? Number(blocks[blocks.length - 1].dataset.builderActionIndex) + 1
    : 0;
}

function autoScrollBuilderActionList(clientY) {
  const canvas = $("builder-state-detail");
  const bounds = canvas.getBoundingClientRect();
  const edge = 48;
  const direction = clientY < bounds.top + edge
    ? 1
    : clientY > bounds.bottom - edge
      ? -1
      : 0;
  if (!direction) {
    stopBuilderActionAutoPan();
    return;
  }
  if (state.builderActionAutoPan) {
    state.builderActionAutoPan.direction = direction;
    return;
  }
  state.builderActionAutoPan = {
    direction,
    frameId: null,
    lastTimestamp: null,
  };
  const step = (timestamp) => {
    const autoPan = state.builderActionAutoPan;
    if (!autoPan) return;
    const elapsed = autoPan.lastTimestamp === null
      ? 1000 / 60
      : Math.min(50, timestamp - autoPan.lastTimestamp);
    autoPan.lastTimestamp = timestamp;
    state.builderActionViewport.y += (
      autoPan.direction * BUILDER_ACTION_AUTO_PAN_SPEED * elapsed / 1000
    );
    renderBuilderActionViewport();
    autoPan.frameId = window.requestAnimationFrame(step);
  };
  state.builderActionAutoPan.frameId = window.requestAnimationFrame(step);
}

function stopBuilderActionAutoPan() {
  const autoPan = state.builderActionAutoPan;
  if (!autoPan) return;
  if (autoPan.frameId !== null) window.cancelAnimationFrame(autoPan.frameId);
  state.builderActionAutoPan = null;
}

function dropBuilderActionAtSlot(drag, slot, targetState) {
  if (drag.kind === "palette") {
    void runCommand(() => insertBuilderAction(drag.actionType, slot, targetState));
    return;
  }
  if (drag.state !== targetState) return;
  const targetIndex = drag.index < slot ? slot - 1 : slot;
  if (targetIndex === drag.index) {
    window.requestAnimationFrame(() => {
      document.querySelector(`[data-builder-action-state="${CSS.escape(drag.state)}"][data-builder-action-index="${drag.index}"]`)?.focus();
    });
    return;
  }
  void runCommand(() => mutateBuilderAction(
    {
      operation: "move",
      state: drag.state,
      index: drag.index,
      target_index: targetIndex,
    },
    { focusIndex: targetIndex },
  ));
}

function settleBuilderAction(index) {
  if (!Number.isInteger(index)) return;
  window.requestAnimationFrame(() => {
    const block = document.querySelector(
      `[data-builder-action-state="${CSS.escape(state.selectedBuilderState)}"][data-builder-action-index="${index}"]`,
    );
    if (!block) return;
    block.classList.add("builder-action-settling");
    block.addEventListener(
      "animationend",
      () => block.classList.remove("builder-action-settling"),
      { once: true },
    );
  });
}

function moveBuilderActionLibrary(left, top) {
  const library = $("builder-action-library");
  const canvas = $("builder-state-detail");
  const maximumLeft = Math.max(8, canvas.clientWidth - library.offsetWidth - 8);
  const maximumTop = Math.max(70, canvas.clientHeight - library.offsetHeight - 8);
  library.style.left = `${Math.min(Math.max(8, left), maximumLeft)}px`;
  library.style.top = `${Math.min(Math.max(70, top), maximumTop)}px`;
  library.style.right = "auto";
}

const BUILDER_DRAWERS = [
  ["builder-notes-drawer", "toggle-builder-notes-drawer"],
  ["builder-yaml-drawer", "toggle-builder-yaml-drawer"],
  ["builder-problems-drawer", "toggle-builder-problems-drawer"],
];

function syncBuilderDrawerControls() {
  for (const [drawerId, controlId] of BUILDER_DRAWERS) {
    $(controlId).setAttribute("aria-expanded", String($(drawerId).open));
  }
}

function closeBuilderDrawers(exceptId = null) {
  for (const [drawerId] of BUILDER_DRAWERS) {
    if (drawerId !== exceptId) $(drawerId).open = false;
  }
  syncBuilderDrawerControls();
}

function toggleBuilderDrawer(drawerId) {
  const drawer = $(drawerId);
  const shouldOpen = !drawer.open;
  closeBuilderDrawers(shouldOpen ? drawerId : null);
  drawer.open = shouldOpen;
  syncBuilderDrawerControls();
  if (shouldOpen) {
    window.requestAnimationFrame(() => drawer.querySelector("summary")?.focus());
  }
}

function dropBuilderActionOnState(drag, targetState) {
  if (drag.kind !== "action" || targetState === drag.state) return;
  const targetActions = state.builderDocument?.states?.[targetState]?.actions || [];
  void runCommand(() => mutateBuilderAction(
    {
      operation: "move_to_state",
      state: drag.state,
      index: drag.index,
      target_state: targetState,
      target_index: targetActions.length,
    },
    {
      focusState: targetState,
      focusIndex: targetActions.length,
    },
  ));
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
$("refresh-builder-target-preview").addEventListener("click", () => runCommand(
  refreshBuilderTargetPreview,
));
$("undo-builder-action").addEventListener("click", () => runCommand(() => restoreBuilderActionHistory("undo")));
$("redo-builder-action").addEventListener("click", () => runCommand(() => restoreBuilderActionHistory("redo")));
$("builder-action-search").addEventListener("input", renderBuilderActionPalette);
$("builder-state-view-tab").addEventListener("click", () => {
  state.builderView = "state";
  renderBuilderView();
  window.requestAnimationFrame(() => $("builder-state-view").querySelector("button")?.focus());
});
$("builder-graph-view-tab").addEventListener("click", () => {
  state.builderView = "flow";
  renderBuilderView();
  renderBuilderFlowGraph();
  window.requestAnimationFrame(() => {
    document.querySelector(`[data-builder-flow-state="${state.selectedBuilderState}"]`)?.focus();
  });
});
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
  selectAndCenterBuilderState(button.dataset.builderState);
});

$("builder-flow-nodes").addEventListener("click", (event) => {
  if (!(event.target instanceof Element)) return;
  const button = event.target.closest("[data-builder-flow-state]");
  if (!button) return;
  state.selectedBuilderState = button.dataset.builderFlowState;
  const actions = state.builderDocument?.states?.[state.selectedBuilderState]?.actions || [];
  state.selectedBuilderActionIndex = actions.length ? 0 : null;
  renderBuilderDocument();
  window.requestAnimationFrame(() => {
    document.querySelector(`[data-builder-flow-state="${state.selectedBuilderState}"]`)?.focus();
  });
});

$("builder-flow-nodes").addEventListener("pointerdown", (event) => {
  if (!(event.target instanceof Element) || !state.builderFlowLayout) return;
  const button = event.target.closest("[data-builder-flow-state]");
  if (!button || event.button !== 0) return;
  const stateName = button.dataset.builderFlowState;
  const position = builderFlowPositions()[stateName];
  if (!position) return;
  state.selectedBuilderState = stateName;
  state.builderFlowNodeDrag = {
    pointerId: event.pointerId,
    stateName,
    startX: event.clientX,
    startY: event.clientY,
    origin: { ...position },
    originalPositions: structuredClone(builderFlowPositions()),
  };
  button.setPointerCapture(event.pointerId);
  event.preventDefault();
});

$("builder-flow-nodes").addEventListener("pointermove", (event) => {
  const drag = state.builderFlowNodeDrag;
  if (!drag || drag.pointerId !== event.pointerId) return;
  const position = builderFlowPositions()[drag.stateName];
  position.x = Math.max(0, Math.round(drag.origin.x + event.clientX - drag.startX));
  position.y = Math.max(0, Math.round(drag.origin.y + event.clientY - drag.startY));
  const button = document.querySelector(`[data-builder-flow-state="${drag.stateName}"]`);
  if (button) {
    button.style.left = `${position.x}px`;
    button.style.top = `${position.y}px`;
  }
  renderBuilderFlowEdges();
});

$("builder-flow-nodes").addEventListener("pointerup", (event) => {
  const drag = state.builderFlowNodeDrag;
  if (!drag || drag.pointerId !== event.pointerId) return;
  state.builderFlowNodeDrag = null;
  void runCommand(() => saveBuilderFlowLayout(structuredClone(builderFlowPositions())));
});

$("builder-flow-inspector-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const selectedState = state.selectedBuilderState;
  if (!selectedState) return;
  const terminal = $("builder-flow-terminal").checked;
  void runCommand(() => mutateBuilderFlow({
    operation: "update_state",
    state: selectedState,
    make_initial: $("builder-flow-initial").checked,
    terminal,
    result: terminal ? $("builder-flow-result").value.trim() : null,
    on_success: terminal ? null : ($("builder-flow-success").value || null),
    on_failure: terminal ? null : ($("builder-flow-failure").value || null),
  }));
});

$("builder-flow-terminal").addEventListener("change", () => {
  const terminal = $("builder-flow-terminal").checked;
  $("builder-flow-result").disabled = !terminal;
  $("builder-flow-success").disabled = terminal;
  $("builder-flow-failure").disabled = terminal;
});
$("tidy-builder-flow").addEventListener("click", () => runCommand(tidyBuilderFlowLayout));
$("undo-builder-layout").addEventListener("click", () => runCommand(
  () => restoreBuilderFlowLayout("undo"),
));
$("redo-builder-layout").addEventListener("click", () => runCommand(
  () => restoreBuilderFlowLayout("redo"),
));
$("move-builder-node-up").addEventListener("click", () => runCommand(
  () => nudgeBuilderFlowNode(0, -24),
));
$("move-builder-node-left").addEventListener("click", () => runCommand(
  () => nudgeBuilderFlowNode(-24, 0),
));
$("move-builder-node-down").addEventListener("click", () => runCommand(
  () => nudgeBuilderFlowNode(0, 24),
));
$("move-builder-node-right").addEventListener("click", () => runCommand(
  () => nudgeBuilderFlowNode(24, 0),
));

$("builder-state-sections").addEventListener("click", (event) => {
  if (state.builderSuppressActionClick) {
    state.builderSuppressActionClick = false;
    event.preventDefault();
    return;
  }
  if (!(event.target instanceof Element)) return;
  const button = event.target.closest("button[data-builder-action-index]");
  if (!button) return;
  state.selectedBuilderState = button.dataset.builderActionState;
  state.selectedBuilderActionIndex = Number(button.dataset.builderActionIndex);
  state.builderActionInspectorCollapsed = false;
  renderBuilderState();
});

$("toggle-builder-action-library").addEventListener("click", () => {
  state.builderActionLibraryHidden = !state.builderActionLibraryHidden;
  renderBuilderActionCanvasControls();
});

$("toggle-builder-state-navigation").addEventListener("click", () => {
  state.builderActionNavigationCollapsed = !state.builderActionNavigationCollapsed;
  renderBuilderActionCanvasControls();
});

$("collapse-builder-action-library").addEventListener("click", () => {
  state.builderActionLibraryCollapsed = !state.builderActionLibraryCollapsed;
  renderBuilderActionCanvasControls();
});

$("toggle-builder-action-inspector").addEventListener("click", () => {
  state.builderActionInspectorCollapsed = !state.builderActionInspectorCollapsed;
  renderBuilderActionCanvasControls();
});

$("collapse-builder-action-inspector").addEventListener("click", () => {
  state.builderActionInspectorCollapsed = true;
  renderBuilderActionCanvasControls();
  $("toggle-builder-action-inspector").focus();
});

$("builder-canvas-zoom-out").addEventListener("click", () => {
  zoomBuilderActionCanvas(state.builderActionViewport.zoom / 1.15);
});

$("builder-canvas-zoom-reset").addEventListener("click", () => {
  renderBuilderActionViewport({ reset: true });
});

$("builder-canvas-zoom-in").addEventListener("click", () => {
  zoomBuilderActionCanvas(state.builderActionViewport.zoom * 1.15);
});

$("builder-all-states-button")?.addEventListener("click", () => {
  state.builderActionOverviewOpen = !state.builderActionOverviewOpen;
  renderBuilderStateOverview();
  if (state.builderActionOverviewOpen) {
    window.requestAnimationFrame(() => $("builder-state-search")?.focus());
  }
});

function findAndCenterBuilderState() {
  const query = $("builder-state-search")?.value || "";
  const match = bestBuilderStateMatch(query);
  if (!match) {
    showNotice(`No State matches “${query.trim()}”.`, "error");
    return;
  }
  selectAndCenterBuilderState(match);
}

$("builder-find-state")?.addEventListener("click", findAndCenterBuilderState);
$("builder-state-search")?.addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  findAndCenterBuilderState();
});
$("builder-canvas-reset-view")?.addEventListener("click", () => {
  cancelBuilderActionCentering();
  renderBuilderActionViewport({ reset: true });
});
$("builder-auto-organize")?.addEventListener("click", autoOrganizeBuilderActionLayout);

$("builder-state-minimap")?.addEventListener("click", (event) => {
  if (!(event.target instanceof Element)) return;
  const stateButton = event.target.closest("[data-builder-minimap-state]");
  if (stateButton) {
    selectAndCenterBuilderState(stateButton.dataset.builderMinimapState);
    return;
  }
  const minimap = $("builder-state-minimap");
  const canvas = $("builder-state-detail");
  const bounds = minimap.getBoundingClientRect();
  if (!bounds.width || !bounds.height) return;
  const world = builderActionWorldBounds();
  const worldX = (event.clientX - bounds.left) / bounds.width * world.width;
  const worldY = (event.clientY - bounds.top) / bounds.height * world.height;
  state.builderActionViewport.x = canvas.clientWidth / 2
    - worldX * state.builderActionViewport.zoom;
  state.builderActionViewport.y = canvas.clientHeight / 2
    - worldY * state.builderActionViewport.zoom;
  state.builderActionViewport.initialized = true;
  renderBuilderActionViewport();
});

for (const [drawerId, controlId] of BUILDER_DRAWERS) {
  $(controlId).addEventListener("click", () => toggleBuilderDrawer(drawerId));
  $(drawerId).addEventListener("toggle", () => {
    if ($(drawerId).open && $("workspace-build").classList.contains("state-actions-mode")) {
      closeBuilderDrawers(drawerId);
    }
    syncBuilderDrawerControls();
  });
}

$("builder-state-detail").addEventListener("wheel", (event) => {
  if (event.target instanceof Element && event.target.closest(
    ".builder-tool-palette, .builder-state-context",
  )) return;
  event.preventDefault();
  const factor = Math.exp(-event.deltaY * 0.0015);
  zoomBuilderActionCanvas(
    state.builderActionViewport.zoom * factor,
    event.clientX,
    event.clientY,
  );
}, { passive: false });

$("builder-state-detail").addEventListener("pointerdown", (event) => {
  if (!(event.target instanceof Element) || event.button !== 0) return;
  if (event.target.closest(
    "button, input, select, textarea, summary, a, [data-builder-state-section], .builder-tool-palette, .builder-state-context",
  )) return;
  event.preventDefault();
  cancelBuilderActionCentering();
  const canvas = $("builder-state-detail");
  state.builderCanvasPan = {
    pointerId: event.pointerId,
    startX: event.clientX,
    startY: event.clientY,
    originX: state.builderActionViewport.x,
    originY: state.builderActionViewport.y,
  };
  canvas.classList.add("canvas-panning");
  canvas.setPointerCapture?.(event.pointerId);
});

$("builder-state-detail").addEventListener("pointermove", (event) => {
  const pan = state.builderCanvasPan;
  if (!pan || pan.pointerId !== event.pointerId) return;
  event.preventDefault();
  state.builderActionViewport.x = pan.originX + event.clientX - pan.startX;
  state.builderActionViewport.y = pan.originY + event.clientY - pan.startY;
  state.builderActionViewport.initialized = true;
  scheduleBuilderActionViewportRender();
});

$("builder-state-detail").addEventListener("scroll", () => {
  if (!$("workspace-build").classList.contains("state-actions-mode")) return;
  const canvas = $("builder-state-detail");
  if (canvas.scrollLeft) canvas.scrollLeft = 0;
  if (canvas.scrollTop) canvas.scrollTop = 0;
});

function finishBuilderCanvasPan(event) {
  if (state.builderCanvasPan?.pointerId !== event.pointerId) return;
  state.builderCanvasPan = null;
  $("builder-state-detail").classList.remove("canvas-panning");
}

$("builder-state-detail").addEventListener("pointerup", finishBuilderCanvasPan);
$("builder-state-detail").addEventListener("pointercancel", finishBuilderCanvasPan);

$("move-builder-action-library").addEventListener("pointerdown", (event) => {
  if (event.button !== 0) return;
  const library = $("builder-action-library");
  const canvas = $("builder-state-detail");
  const libraryBounds = library.getBoundingClientRect();
  const canvasBounds = canvas.getBoundingClientRect();
  event.preventDefault();
  state.builderActionLibraryDrag = {
    pointerId: event.pointerId,
    offsetX: event.clientX - libraryBounds.left,
    offsetY: event.clientY - libraryBounds.top,
    canvasLeft: canvasBounds.left,
    canvasTop: canvasBounds.top,
  };
  event.currentTarget.setPointerCapture?.(event.pointerId);
});

$("move-builder-action-library").addEventListener("keydown", (event) => {
  const deltas = {
    ArrowUp: [0, -16],
    ArrowRight: [16, 0],
    ArrowDown: [0, 16],
    ArrowLeft: [-16, 0],
  };
  const delta = deltas[event.key];
  if (!delta) return;
  event.preventDefault();
  const library = $("builder-action-library");
  moveBuilderActionLibrary(
    Number.parseFloat(library.style.left || "16") + delta[0],
    Number.parseFloat(library.style.top || "94") + delta[1],
  );
});

$("builder-action-palette").addEventListener("dragstart", (event) => {
  if (!(event.target instanceof Element)) return;
  const button = event.target.closest("button[data-add-builder-action]");
  if (!button || button.disabled) {
    event.preventDefault();
    return;
  }
  state.builderDrag = {
    kind: "palette",
    actionType: button.dataset.addBuilderAction,
  };
  button.setAttribute("aria-grabbed", "true");
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = "copy";
    event.dataTransfer.setData("text/plain", button.dataset.addBuilderAction);
  }
});

$("builder-state-sections").addEventListener("dragover", (event) => {
  if (!state.builderDrag || state.structuredMutationPending) return;
  if (!(event.target instanceof Element)) return;
  const list = event.target.closest("ol[data-builder-action-state]");
  if (!list) return;
  event.preventDefault();
  const slot = builderDropSlot(list, event.clientY);
  state.builderDropState = list.dataset.builderActionState;
  showBuilderDropIndicator(list, slot);
  autoScrollBuilderActionList(event.clientY);
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = state.builderDrag.kind === "palette" ? "copy" : "move";
  }
});

document.addEventListener("dragover", (event) => {
  if (
    state.builderDrag?.kind === "palette"
    && !(event.target instanceof Element && event.target.closest("ol[data-builder-action-state]"))
  ) {
    stopBuilderActionAutoPan();
  }
});

$("builder-state-sections").addEventListener("drop", (event) => {
  const drag = state.builderDrag;
  if (!drag || state.structuredMutationPending) return;
  if (!(event.target instanceof Element)) return;
  const list = event.target.closest("ol[data-builder-action-state]");
  if (!list) return;
  event.preventDefault();
  const targetState = list.dataset.builderActionState;
  const slot = state.builderDropSlot ?? builderDropSlot(list, event.clientY);
  clearBuilderDrag();
  dropBuilderActionAtSlot(drag, slot, targetState);
});

$("builder-state-sections").addEventListener("dragend", () => clearBuilderDrag());
$("builder-action-palette").addEventListener("dragend", () => clearBuilderDrag());

$("builder-state-sections").addEventListener("pointerdown", (event) => {
  if (!(event.target instanceof Element) || event.button !== 0) return;
  const button = event.target.closest("button[data-builder-action-index]");
  if (!button || state.structuredMutationPending) return;
  const interactiveTarget = event.target.closest(
    "button, input, select, textarea, a, summary, [contenteditable]",
  );
  if (interactiveTarget && interactiveTarget !== button) return;
  state.builderDrag = {
    kind: "action",
    state: button.dataset.builderActionState,
    index: Number(button.dataset.builderActionIndex),
  };
  state.builderPointerDrag = {
    pointerId: event.pointerId,
    startX: event.clientX,
    startY: event.clientY,
    active: false,
  };
  button.setAttribute("aria-grabbed", "true");
  button.setPointerCapture?.(event.pointerId);
});

$("builder-state-sections").addEventListener("pointerdown", (event) => {
  if (!(event.target instanceof Element) || event.button !== 0) return;
  const roof = event.target.closest("[data-builder-state-section-handle]");
  const section = event.target.closest("[data-builder-state-section]");
  if (!section) return;
  if (!roof && event.target.closest(
    "button, input, select, textarea, a, summary, ol[data-builder-action-state]",
  )) return;
  const stateName = roof?.dataset.builderStateSectionHandle
    || section.dataset.builderStateSection;
  const position = state.builderActionLayout.positions[stateName];
  if (!position) return;
  event.preventDefault();
  cancelBuilderActionCentering();
  state.builderActionSectionDrag = {
    pointerId: event.pointerId,
    stateName,
    handle: roof || section,
    startX: event.clientX,
    startY: event.clientY,
    origin: { ...position },
    moved: false,
  };
  if (roof) roof.setAttribute("aria-grabbed", "true");
  section.classList.add("dragging");
  (roof || section).setPointerCapture?.(event.pointerId);
});

document.addEventListener("pointermove", (event) => {
  const libraryDrag = state.builderActionLibraryDrag;
  if (libraryDrag?.pointerId === event.pointerId) {
    event.preventDefault();
    moveBuilderActionLibrary(
      event.clientX - libraryDrag.canvasLeft - libraryDrag.offsetX,
      event.clientY - libraryDrag.canvasTop - libraryDrag.offsetY,
    );
    return;
  }
  const sectionDrag = state.builderActionSectionDrag;
  if (sectionDrag?.pointerId === event.pointerId) {
    event.preventDefault();
    const zoom = state.builderActionViewport.zoom || 1;
    const position = state.builderActionLayout.positions[sectionDrag.stateName];
    position.x = Math.max(0, Math.round(sectionDrag.origin.x + (event.clientX - sectionDrag.startX) / zoom));
    position.y = Math.max(
      BUILDER_ACTION_RESERVED_TOP,
      Math.round(sectionDrag.origin.y + (event.clientY - sectionDrag.startY) / zoom),
    );
    sectionDrag.moved = sectionDrag.moved
      || Math.hypot(event.clientX - sectionDrag.startX, event.clientY - sectionDrag.startY) >= 4;
    const section = document.querySelector(
      `[data-builder-state-section="${CSS.escape(sectionDrag.stateName)}"]`,
    );
    if (section) {
      section.style.left = `${position.x}px`;
      section.style.top = `${position.y}px`;
    }
    scheduleBuilderActionViewportRender();
    return;
  }
  const pointer = state.builderPointerDrag;
  if (!pointer || pointer.pointerId !== event.pointerId || !state.builderDrag) return;
  const distance = Math.hypot(
    event.clientX - pointer.startX,
    event.clientY - pointer.startY,
  );
  if (!pointer.active && distance < 5) return;
  pointer.active = true;
  event.preventDefault();
  const target = document.elementFromPoint(event.clientX, event.clientY);
  const list = target?.closest?.("ol[data-builder-action-state]");
  if (list && list.dataset.builderActionState === state.builderDrag.state) {
    state.builderDropState = list.dataset.builderActionState;
    showBuilderDropIndicator(list, builderDropSlot(list, event.clientY));
    autoScrollBuilderActionList(event.clientY);
    return;
  }
  document.querySelector("#builder-drop-indicator")?.remove();
  state.builderDropSlot = null;
  state.builderDropState = null;
  stopBuilderActionAutoPan();
  setBuilderActionDragStatus(
    "Actions can only be reordered inside their owning State. Releasing here will not change the Draft.",
  );
});

document.addEventListener("pointerup", (event) => {
  if (state.builderActionLibraryDrag?.pointerId === event.pointerId) {
    state.builderActionLibraryDrag = null;
    return;
  }
  const sectionDrag = state.builderActionSectionDrag;
  if (sectionDrag?.pointerId === event.pointerId) {
    state.builderActionSectionDrag = null;
    sectionDrag.handle.setAttribute?.("aria-grabbed", "false");
    sectionDrag.handle.closest("[data-builder-state-section]")?.classList.remove("dragging");
    state.selectedBuilderState = sectionDrag.stateName;
    const actions = state.builderDocument?.states?.[sectionDrag.stateName]?.actions || [];
    state.selectedBuilderActionIndex = actions.length ? 0 : null;
    renderBuilderDocument();
    return;
  }
  const pointer = state.builderPointerDrag;
  if (!pointer || pointer.pointerId !== event.pointerId) return;
  const drag = state.builderDrag;
  const slot = state.builderDropSlot;
  const targetState = state.builderDropState;
  const active = pointer.active;
  state.builderPointerDrag = null;
  clearBuilderDrag();
  if (!active || !drag) return;
  state.builderSuppressActionClick = true;
  window.setTimeout(() => {
    state.builderSuppressActionClick = false;
  }, 0);
  if (slot !== null && targetState) {
    dropBuilderActionAtSlot(drag, slot, targetState);
  }
});

document.addEventListener("pointercancel", (event) => {
  if (state.builderActionLibraryDrag?.pointerId === event.pointerId) {
    state.builderActionLibraryDrag = null;
  }
  const sectionDrag = state.builderActionSectionDrag;
  if (sectionDrag?.pointerId === event.pointerId) {
    state.builderActionLayout.positions[sectionDrag.stateName] = sectionDrag.origin;
    state.builderActionSectionDrag = null;
    sectionDrag.handle.setAttribute?.("aria-grabbed", "false");
    renderBuilderStateSections();
    return;
  }
  if (state.builderPointerDrag?.pointerId !== event.pointerId) return;
  state.builderPointerDrag = null;
  clearBuilderDrag({ restoreFocus: true });
});

$("builder-action-palette").addEventListener("click", (event) => runCommand(async () => {
  if (!(event.target instanceof Element)) return;
  const button = event.target.closest("button[data-add-builder-action]");
  if (!button || !state.selectedBuilderState) return;
  const actions = state.builderDocument?.states?.[state.selectedBuilderState]?.actions || [];
  await insertBuilderAction(button.dataset.addBuilderAction, actions.length);
}));

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  if (state.builderActionSectionDrag) {
    event.preventDefault();
    const drag = state.builderActionSectionDrag;
    state.builderActionLayout.positions[drag.stateName] = drag.origin;
    state.builderActionSectionDrag = null;
    drag.handle.setAttribute?.("aria-grabbed", "false");
    renderBuilderStateSections();
    return;
  }
  if (state.builderCanvasPan) {
    event.preventDefault();
    state.builderCanvasPan = null;
    $("builder-state-detail").classList.remove("canvas-panning");
    return;
  }
  if (state.builderActionLibraryDrag) {
    event.preventDefault();
    state.builderActionLibraryDrag = null;
    $("move-builder-action-library").focus();
    return;
  }
  if (state.builderFlowNodeDrag) {
    event.preventDefault();
    state.builderFlowLayout.positions = state.builderFlowNodeDrag.originalPositions;
    state.builderFlowNodeDrag = null;
    renderBuilderFlowGraph();
    showNotice("State move cancelled.", "good");
    return;
  }
  if (!state.builderDrag) return;
  event.preventDefault();
  state.builderPointerDrag = null;
  clearBuilderDrag({ restoreFocus: true });
  showNotice("Action drag cancelled.", "good");
});

$("builder-action-inspector-form").addEventListener("input", (event) => {
  if (
    !(event.target instanceof HTMLInputElement)
    && !(event.target instanceof HTMLSelectElement)
  ) return;
  const fieldName = event.target.dataset.builderActionField;
  if (!fieldName) return;
  const index = state.selectedBuilderActionIndex;
  if (!Number.isInteger(index)) return;
  const definition = actionDefinition(selectedBuilderAction()?.type);
  const field = definition?.fields?.find((candidate) => candidate.name === fieldName);
  if (!field) return;
  const rawValue = event.target.value;
  const numeric = ["duration", "positive_duration", "number", "positive_integer"].includes(field.kind);
  const value = rawValue === "" ? "" : (numeric ? Number(rawValue) : rawValue);
  const mutation = {
    operation: "update",
    state: state.selectedBuilderState,
    index,
  };
  if (rawValue === "" && !field.required) {
    mutation.unset_fields = [fieldName];
  } else {
    mutation.fields = { [fieldName]: value };
  }
  window.clearTimeout(state.builderInspectorTimer);
  state.builderInspectorPending = {
    mutation,
    options: { focusIndex: index, focusField: fieldName },
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
  const stateMatch = problem?.location?.match(/^states\.([^.]+)(?:\.(.+))?$/);
  if (!match && !stateMatch) return;
  state.selectedBuilderState = match?.[1] || stateMatch[1];
  state.selectedBuilderActionIndex = match ? Number(match[2]) : null;
  if (!match) state.builderView = "flow";
  renderBuilderDocument();
  window.requestAnimationFrame(() => {
    const stateFieldTargets = {
      on_success: "builder-flow-success",
      on_failure: "builder-flow-failure",
      result: "builder-flow-result",
      terminal: "builder-flow-terminal",
    };
    let target;
    if (match?.[3]) {
      target = document.querySelector(`[data-builder-action-field="${match[3]}"]`);
    } else if (match) {
      centerBuilderActionState(state.selectedBuilderState);
      target = document.querySelector(
        `[data-builder-action-state="${CSS.escape(state.selectedBuilderState)}"]`
        + `[data-builder-action-index="${match[2]}"]`,
      );
    } else if (stateMatch?.[2] && stateFieldTargets[stateMatch[2]]) {
      target = $(stateFieldTargets[stateMatch[2]]);
    } else {
      target = document.querySelector(`[data-builder-flow-state="${state.selectedBuilderState}"]`);
    }
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

$("builder-target-preview-image").addEventListener("load", () => {
  $("builder-target-preview-image").hidden = false;
  $("builder-target-preview-empty").hidden = true;
});

$("builder-target-preview-image").addEventListener("error", () => {
  $("builder-target-preview-image").hidden = true;
  $("builder-target-preview-empty").hidden = false;
  $("builder-target-preview-empty").textContent = "Target preview could not be displayed";
});

let builderActionResizeFrame = null;

window.addEventListener("resize", () => {
  if ($("workspace-build").classList.contains("state-actions-mode")) {
    if (state.builderActionColumnLayoutMobile !== null
      && state.builderActionColumnLayoutMobile !== builderActionUsesSingleColumn()) {
      renderBuilderStateSections();
      return;
    }
    window.cancelAnimationFrame(builderActionResizeFrame);
    builderActionResizeFrame = window.requestAnimationFrame(() => {
      builderActionResizeFrame = null;
      renderBuilderActionViewport();
      renderBuilderActionConnectors();
      renderBuilderStateMinimap();
    });
    const library = $("builder-action-library");
    moveBuilderActionLibrary(
      Number.parseFloat(library.style.left || "14"),
      Number.parseFloat(library.style.top || "70"),
    );
  }
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
