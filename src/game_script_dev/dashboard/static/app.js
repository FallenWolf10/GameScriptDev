const state = {
  profiles: [],
  runs: [],
  selectedProfileId: null,
  selectedRunId: null,
  selectedRunSummary: null,
  selectedBuilderStateName: null,
  builderDraft: null,
  builderOriginalProfile: null,
  builderWorkingProfile: null,
  builderOriginalNotes: "",
  builderWorkingNotes: "",
  builderSchema: null,
  builderAssets: [],
  builderPreview: null,
  builderPreviewStatus: "Target preview not loaded",
  builderPreviewTone: "muted",
  builderDrawRect: null,
  builderDragStart: null,
  selectedBuilderRegionName: null,
  builderDirty: false,
  builderSaveStatus: "No draft loaded",
  builderSaveTone: "muted",
  builderDrag: null,
  builderScaffoldStatus: "Create a new pack under profiles/",
  builderScaffoldTone: "muted",
  builderScaffoldDraft: {
    game: "",
    mode: "",
    game_slug: "",
    pack_slug: "",
  },
  activeView: "operate",
  pollTimer: null,
  pollCount: 0,
  runtime: null,
  autoDryRunStartedByProfileId: {},
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
  lastBuilderDraftSignature: "",
  lastBuilderStateListSignature: "",
  lastBuilderStateEditorSignature: "",
  lastBuilderStateDetailSignature: "",
  lastBuilderSettingsSignature: "",
  lastBuilderGraphSignature: "",
  lastBuilderValidationSignature: "",
  lastBuilderToolbarSignature: "",
  lastBuilderActionPaletteSignature: "",
  lastBuilderScaffoldSignature: "",
  lastBuilderPackCheckSignature: "",
  lastBuilderVisualSignature: "",
  lastWorkspaceViewSignature: "",
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

async function refreshBuilderSchema() {
  if (state.builderSchema) {
    return state.builderSchema;
  }
  state.builderSchema = await api("/api/profile-schema");
  return state.builderSchema;
}

async function refreshBuilderAssets() {
  if (!state.selectedProfileId) {
    state.builderAssets = [];
    return [];
  }
  const payload = await api(`/api/profiles/${encodeURIComponent(state.selectedProfileId)}/assets`);
  state.builderAssets = payload.assets || [];
  return state.builderAssets;
}

async function refreshBuilderDraft({ force = false } = {}) {
  if (!state.selectedProfileId) {
    state.builderDraft = null;
    state.builderOriginalProfile = null;
    state.builderWorkingProfile = null;
    state.builderOriginalNotes = "";
    state.builderWorkingNotes = "";
    state.builderAssets = [];
    state.builderPreview = null;
    state.builderDrawRect = null;
    state.selectedBuilderRegionName = null;
    state.builderDirty = false;
    setBuilderStatus("No draft loaded", "muted");
    renderBuilder();
    return;
  }
  if (state.builderDirty && !force) {
    renderBuilder();
    return;
  }
  const draft = await api(`/api/profiles/${encodeURIComponent(state.selectedProfileId)}/draft`);
  state.builderDraft = draft;
  state.builderOriginalProfile = cloneValue(draft.profile);
  state.builderWorkingProfile = cloneValue(draft.profile);
  state.builderOriginalNotes = draft.notes || "";
  state.builderWorkingNotes = draft.notes || "";
  state.builderDirty = false;
  setBuilderStatus(draft.valid ? "Saved profile loaded" : "Loaded with validation issues", draft.valid ? "good" : "warn");
  const states = draft.profile?.states || [];
  if (!states.some((item) => item.name === state.selectedBuilderStateName)) {
    state.selectedBuilderStateName = states[0]?.name || null;
  }
  await refreshBuilderAssets();
  renderBuilder();
}

function cloneValue(value) {
  return value === null || value === undefined
    ? value
    : JSON.parse(JSON.stringify(value));
}

function getBuilderProfile() {
  return state.builderWorkingProfile || state.builderDraft?.profile || null;
}

function getBuilderNotes() {
  return state.builderWorkingNotes ?? state.builderDraft?.notes ?? "";
}

function setBuilderStatus(message, tone = "muted") {
  state.builderSaveStatus = message;
  state.builderSaveTone = tone;
}

async function selectProfile(profileId, { autoDryRun = false, skipInitialReadiness = false } = {}) {
  state.selectedProfileId = profileId;
  state.lastPreviewRefreshAt = 0;
  state.builderPreview = null;
  state.builderPreviewStatus = "Target preview not loaded";
  state.builderPreviewTone = "muted";
  state.builderDrawRect = null;
  state.selectedBuilderRegionName = null;
  renderProfiles();
  renderProfileSelect();
  renderProfilePackDetail();
  await refreshBuilderDraft({ force: true });
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
      await refreshBuilderDraft({ force: true });
      return;
    }
    await startRun("dry-run", null, { skipValidation: true });
    await refreshBuilderDraft({ force: true });
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
  if (state.selectedProfileId) {
    await refreshBuilderDraft({ force: true });
  }
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
    const previewRatio = preview.height > 0 ? preview.width / preview.height : 16 / 9;
    frame.style.setProperty("--target-preview-ratio", String(Math.max(previewRatio, 16 / 9)));
    image.hidden = false;
    empty.hidden = true;
    meta.textContent = `${preview.title} - ${preview.process_name || "unknown process"} - client ${preview.width}x${preview.height}`;
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
        <small>${escapeHtml(run.started_at)} - ${escapeHtml(run.status)}</small>
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
    const stateLabel = event.state ? ` state=${event.state}` : "";
    const action = event.action_type ? ` action=${event.action_type}` : "";
    const index = Number.isInteger(event.action_index) ? ` #${event.action_index}` : "";
    const summary = event.action_summary ? ` ${event.action_summary}` : "";
    const result = event.result ? ` result=${event.result}` : "";
    const reason = event.failure_reason ? ` reason=${event.failure_reason}` : "";
    item.textContent = `${event.at || ""} ${event.event || "event"}${stateLabel}${action}${index}${summary}${result}${reason}`.trim();
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
      await refreshReadiness({ includePreview: true });
      if (state.activeView === "builder") {
        await refreshBuilderDraft();
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

function setActiveView(view) {
  state.activeView = view;
  renderWorkspaceView();
}

function renderWorkspaceView() {
  const signature = state.activeView;
  if (signature === state.lastWorkspaceViewSignature) {
    return;
  }
  state.lastWorkspaceViewSignature = signature;
  const operateActive = state.activeView === "operate";
  $("operate-tab").classList.toggle("active", operateActive);
  $("builder-tab").classList.toggle("active", !operateActive);
  $("operate-view").classList.toggle("workspace-view-active", operateActive);
  $("builder-view").classList.toggle("workspace-view-active", !operateActive);
  $("workspace-mode-caption").textContent = operateActive
    ? "Run profiles, inspect readiness, and review artifacts."
    : "Scaffold packs, edit metadata and actions, and save canonical YAML.";
}

function renderBuilder() {
  renderBuilderToolbar();
  renderBuilderValidity();
  renderBuilderScaffold();
  renderBuilderSettings();
  renderBuilderStateSelect();
  renderBuilderActionPalette();
  renderBuilderGraph();
  renderBuilderValidation();
  renderBuilderPackCheck();
  renderBuilderVisualTools();
  renderBuilderStateEditor();
  renderBuilderStateDetail();
  renderBuilderYamlPreview();
}

function renderBuilderToolbar() {
  const profile = getBuilderProfile();
  const signature = JSON.stringify({
    profileId: state.selectedProfileId,
    dirty: state.builderDirty,
    valid: state.builderDraft?.valid ?? null,
    status: state.builderSaveStatus,
    tone: state.builderSaveTone,
    hasProfile: Boolean(profile),
  });
  if (signature === state.lastBuilderToolbarSignature) {
    return;
  }
  state.lastBuilderToolbarSignature = signature;
  const status = $("builder-save-status");
  status.textContent = state.builderSaveStatus;
  status.className = state.builderSaveTone === "muted" ? "muted" : `builder-status builder-status-${state.builderSaveTone}`;
  $("builder-validate-button").disabled = !profile;
  $("builder-check-pack-button").disabled = !profile;
  $("builder-revert-button").disabled = !state.builderDirty;
  $("builder-save-button").disabled = !profile || !state.builderDirty;
}

function renderBuilderValidity() {
  const badge = $("builder-validity-badge");
  const draft = state.builderDraft;
  if (!draft) {
    badge.textContent = "No Profile";
    badge.className = "badge";
    $("builder-subtitle").textContent = "Select a profile to inspect its workflow structure.";
    return;
  }
  const valid = Boolean(draft.valid);
  badge.textContent = valid ? "Schema Clean" : "Needs Review";
  badge.className = `badge ${valid ? "good" : "bad"}`;
  $("builder-subtitle").textContent = draft.load_error
    ? "Draft changes are being tracked locally, but the current profile shape does not parse cleanly yet."
    : state.builderDirty
      ? "Unsaved metadata and action edits are previewed through the backend serializer before commit."
      : "Profile pack authoring stays aligned with the existing profile schema, pack checks, and YAML serializer.";
}

function renderBuilderScaffold() {
  const target = $("builder-scaffold-form");
  const signature = JSON.stringify({
    selectedProfileId: state.selectedProfileId,
    scaffold: state.builderScaffoldDraft,
    status: state.builderScaffoldStatus,
    tone: state.builderScaffoldTone,
  });
  if (signature === state.lastBuilderScaffoldSignature) {
    return;
  }
  state.lastBuilderScaffoldSignature = signature;
  $("builder-scaffold-status").textContent = state.builderScaffoldStatus;
  $("builder-scaffold-status").className = state.builderScaffoldTone === "muted"
    ? "muted"
    : `builder-status builder-status-${state.builderScaffoldTone}`;
  target.innerHTML = "";
  target.appendChild(createBuilderField({
    label: "Game",
    name: "game",
    value: state.builderScaffoldDraft.game,
    section: "scaffold",
  }));
  target.appendChild(createBuilderField({
    label: "Mode",
    name: "mode",
    value: state.builderScaffoldDraft.mode,
    section: "scaffold",
  }));
  target.appendChild(createBuilderField({
    label: "Game Slug",
    name: "game_slug",
    value: state.builderScaffoldDraft.game_slug,
    section: "scaffold",
    placeholder: "example_game",
  }));
  target.appendChild(createBuilderField({
    label: "Pack Slug",
    name: "pack_slug",
    value: state.builderScaffoldDraft.pack_slug,
    section: "scaffold",
    placeholder: "daily_task",
  }));
  const actions = document.createElement("div");
  actions.className = "builder-inline-actions builder-field-full";
  actions.innerHTML = '<button id="builder-scaffold-button" type="button">Create Pack</button><span class="muted">Creates profile.yaml, notes.md, assets/, and validation_examples/.</span>';
  target.appendChild(actions);
}

function renderBuilderSettings() {
  const target = $("builder-settings-grid");
  const draft = state.builderDraft;
  const profile = getBuilderProfile();
  const signature = JSON.stringify({
    profileId: draft?.profile_id || null,
    profile,
    notes: getBuilderNotes(),
  });
  if (signature === state.lastBuilderSettingsSignature) {
    return;
  }
  state.lastBuilderSettingsSignature = signature;
  target.innerHTML = "";
  $("builder-profile-path").textContent = draft?.path || "No profile selected";
  if (!profile) {
    target.innerHTML = '<div class="builder-detail-section builder-field-full"><strong>Structured profile unavailable</strong><div class="builder-anchor-meta">Select a valid profile or scaffold a new pack.</div></div>';
    return;
  }
  target.appendChild(createBuilderField({
    label: "Profile Name",
    name: "name",
    value: profile.name,
    section: "profile",
  }));
  target.appendChild(createBuilderField({
    label: "Initial State",
    name: "initial_state",
    value: profile.initial_state,
    section: "profile",
    kind: "state_name",
  }));
  target.appendChild(createBuilderField({
    label: "Target Process",
    name: "target.process_name",
    value: profile.target.process_name || "",
    section: "profile",
  }));
  target.appendChild(createBuilderField({
    label: "Window Title Match",
    name: "target.window_title_contains",
    value: profile.target.window_title_contains || "",
    section: "profile",
  }));
  target.appendChild(createBuilderField({
    label: "Input Mode",
    name: "target.input_mode",
    value: profile.target.input_mode,
    section: "profile",
    kind: "input_mode",
  }));
  target.appendChild(createBuilderField({
    label: "Resolution Width",
    name: "resolution.width",
    value: profile.resolution.width,
    section: "profile",
    kind: "integer",
  }));
  target.appendChild(createBuilderField({
    label: "Resolution Height",
    name: "resolution.height",
    value: profile.resolution.height,
    section: "profile",
    kind: "integer",
  }));
  target.appendChild(createBuilderField({
    label: "Resolution Policy",
    name: "resolution.policy",
    value: profile.resolution.policy,
    section: "profile",
  }));
  target.appendChild(createBuilderField({
    label: "Default Timeout Seconds",
    name: "execution.default_timeout_seconds",
    value: profile.execution.default_timeout_seconds,
    section: "profile",
    kind: "number",
  }));
  target.appendChild(createBuilderField({
    label: "Max Retries",
    name: "execution.max_retries",
    value: profile.execution.max_retries,
    section: "profile",
    kind: "integer",
  }));
  target.appendChild(createBuilderField({
    label: "Known Limitations",
    name: "profile_pack.known_limitations",
    value: (profile.profile_pack?.known_limitations || []).join("\n"),
    section: "profile",
    multiline: true,
    fullWidth: true,
    placeholder: "One limitation per line",
    disabled: !profile.profile_pack,
  }));
  target.appendChild(createBuilderField({
    label: "Pack Notes",
    name: "notes",
    value: getBuilderNotes(),
    section: "profile",
    multiline: true,
    fullWidth: true,
    placeholder: "# Notes",
  }));
  if (profile.profile_pack) {
    target.appendChild(createBuilderField({
      label: "Pack Game",
      name: "profile_pack.game",
      value: profile.profile_pack.game,
      section: "profile",
    }));
    target.appendChild(createBuilderField({
      label: "Pack Mode",
      name: "profile_pack.game_mode",
      value: profile.profile_pack.game_mode,
      section: "profile",
    }));
    target.appendChild(createBuilderField({
      label: "Detection Strategy",
      name: "profile_pack.detection_strategy",
      value: profile.profile_pack.detection_strategy,
      section: "profile",
      kind: "detection_strategy",
    }));
    const checklist = document.createElement("div");
    checklist.className = "builder-field builder-field-full";
    checklist.innerHTML = '<span>Compatibility Checklist</span>';
    const grid = document.createElement("div");
    grid.className = "builder-checkbox-grid";
    for (const check of state.builderSchema?.required_compatibility_checks || []) {
      const row = document.createElement("label");
      row.className = "builder-checkbox";
      row.innerHTML = `<input type="checkbox" data-builder-section="profile" data-builder-field="profile_pack.compatibility.${check}" ${profile.profile_pack.compatibility?.[check] ? "checked" : ""} /><span><strong>${escapeHtml(humanizeBuilderKey(check))}</strong><code>${escapeHtml(check)}</code></span>`;
      grid.appendChild(row);
    }
    checklist.appendChild(grid);
    target.appendChild(checklist);
  }
  const summary = document.createElement("div");
  summary.className = "builder-detail-section builder-field-full";
  summary.innerHTML = `
    <strong>Profile Summary</strong>
    <div class="builder-anchor-meta">states=${profile.states.length} | regions=${(profile.regions || []).length} | interruptions=${(profile.interruptions || []).length}</div>
  `;
  target.appendChild(summary);
}

function createBuilderField({
  label,
  name,
  value,
  section,
  kind = "string",
  multiline = false,
  fullWidth = false,
  placeholder = "",
  disabled = false,
}) {
  const row = document.createElement("label");
  row.className = `builder-field${fullWidth ? " builder-field-full" : ""}`;
  row.innerHTML = `<span>${escapeHtml(label)}</span>`;
  let input;
  if (multiline) {
    input = document.createElement("textarea");
    input.value = value ?? "";
  } else if (["input_mode", "state_name", "state_name_optional", "failure_target", "detection_strategy", "result_value"].includes(kind)) {
    input = document.createElement("select");
    if (kind === "state_name_optional") {
      const empty = document.createElement("option");
      empty.value = "";
      empty.textContent = "None";
      input.appendChild(empty);
    }
    for (const optionValue of builderFieldOptions(kind)) {
      const option = document.createElement("option");
      option.value = optionValue;
      option.textContent = optionValue;
      input.appendChild(option);
    }
    input.value = value ?? "";
  } else {
    input = document.createElement("input");
    input.type = kind === "integer" || kind === "number" ? "number" : "text";
    if (kind === "integer") {
      input.step = "1";
    }
    if (kind === "number") {
      input.step = "0.1";
    }
    input.value = value ?? "";
  }
  input.dataset.builderSection = section;
  input.dataset.builderField = name;
  input.dataset.builderKind = kind;
  input.placeholder = placeholder;
  input.disabled = disabled;
  row.appendChild(input);
  return row;
}

function builderFieldOptions(kind) {
  const profile = getBuilderProfile();
  if (kind === "input_mode") {
    return state.builderSchema?.supported_input_modes || [];
  }
  if (kind === "state_name") {
    return (profile?.states || []).map((item) => item.name);
  }
  if (kind === "state_name_optional") {
    return (profile?.states || [])
      .map((item) => item.name)
      .filter((name) => name !== state.selectedBuilderStateName);
  }
  if (kind === "failure_target") {
    return ["graceful_termination", ...(profile?.states || [])
      .map((item) => item.name)
      .filter((name) => name !== state.selectedBuilderStateName)];
  }
  if (kind === "detection_strategy") {
    return state.builderSchema?.supported_detection_strategies || [];
  }
  if (kind === "result_value") {
    return ["", "success", "failure", "failed_manual_stop", "operator_stopped"];
  }
  return [];
}

function humanizeBuilderKey(value) {
  return String(value || "")
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function renderBuilderStateSelect() {
  const select = $("builder-state-select");
  const states = getBuilderProfile()?.states || [];
  const signature = JSON.stringify({
    selectedBuilderStateName: state.selectedBuilderStateName,
    states: states.map((item) => item.name),
  });
  if (signature === state.lastBuilderStateListSignature) {
    return;
  }
  state.lastBuilderStateListSignature = signature;
  select.innerHTML = "";
  if (!states.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No states";
    select.appendChild(option);
    select.disabled = true;
    return;
  }
  select.disabled = false;
  for (const item of states) {
    const option = document.createElement("option");
    option.value = item.name;
    option.textContent = item.name;
    option.selected = item.name === state.selectedBuilderStateName;
    select.appendChild(option);
  }
}

function renderBuilderActionPalette() {
  const select = $("builder-add-action-select");
  const editableTypes = state.builderSchema?.editable_action_types || [];
  const signature = JSON.stringify({
    editableTypes,
    selectedStateName: state.selectedBuilderStateName,
  });
  if (signature === state.lastBuilderActionPaletteSignature) {
    return;
  }
  state.lastBuilderActionPaletteSignature = signature;
  select.innerHTML = "";
  if (!editableTypes.length || !state.selectedBuilderStateName) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No editable actions";
    select.appendChild(option);
    select.disabled = true;
    $("builder-add-action-button").disabled = true;
    return;
  }
  select.disabled = false;
  $("builder-add-action-button").disabled = false;
  for (const actionType of editableTypes) {
    const option = document.createElement("option");
    option.value = actionType;
    option.textContent = state.builderSchema.actions?.[actionType]?.label || actionType;
    select.appendChild(option);
  }
}

function renderBuilderGraph() {
  const target = $("builder-graph");
  const draft = state.builderDraft;
  const profile = getBuilderProfile();
  const graph = draft?.graph;
  const signature = JSON.stringify({
    profileId: state.selectedProfileId,
    graph,
    initialState: profile?.initial_state || null,
  });
  if (signature === state.lastBuilderGraphSignature) {
    return;
  }
  state.lastBuilderGraphSignature = signature;
  target.innerHTML = "";
  if (!profile || !graph) {
    $("builder-graph-summary").textContent = "Structured graph unavailable";
    target.innerHTML = '<div class="builder-graph-node"><strong>No graph data</strong><div class="builder-anchor-meta">Fix the profile load error or validation problem to inspect state links.</div></div>';
    return;
  }
  const unreachable = new Set(graph.unreachable_states || []);
  const edgesBySource = new Map();
  for (const edge of graph.edges || []) {
    const existing = edgesBySource.get(edge.from) || [];
    existing.push(edge);
    edgesBySource.set(edge.from, existing);
  }
  $("builder-graph-summary").textContent = `${profile.states.length} states - ${graph.edges.length} transitions - ${graph.unreachable_states.length} unreachable`;
  for (const item of profile.states) {
    const node = document.createElement("button");
    node.type = "button";
    node.className = "builder-graph-node";
    if (item.name === profile.initial_state) {
      node.classList.add("is-initial");
    }
    if (item.terminal) {
      node.classList.add("is-terminal");
    }
    if (unreachable.has(item.name)) {
      node.classList.add("is-unreachable");
    }
    node.dataset.stateName = item.name;
    const tags = [];
    if (item.name === profile.initial_state) {
      tags.push('<span class="builder-node-tag success">initial</span>');
    }
    if (item.terminal) {
      tags.push(`<span class="builder-node-tag result">${escapeHtml(item.result || "terminal")}</span>`);
    }
    if (unreachable.has(item.name)) {
      tags.push('<span class="builder-node-tag failure">unreachable</span>');
    }
    const transitions = (edgesBySource.get(item.name) || []).map((edge) => {
      const label = edge.kind === "failure" ? "failure" : "success";
      const className = edge.kind === "failure" ? "failure" : "success";
      const suffix = edge.valid ? "" : " (missing)";
      return `<span class="builder-node-tag ${className}">${label} -> ${escapeHtml(edge.to)}${suffix}</span>`;
    }).join("");
    node.innerHTML = `
      <div class="builder-graph-node-header">
        <div class="builder-graph-node-title">
          <strong>${escapeHtml(item.name)}</strong>
        </div>
        <div class="builder-node-tags">${tags.join("")}</div>
      </div>
      <div class="builder-node-tags">${transitions || '<span class="builder-node-tag">no outgoing links</span>'}</div>
    `;
    target.appendChild(node);
  }
}

function renderBuilderStateEditor() {
  const target = $("builder-state-editor");
  const selectedState = builderSelectedState();
  const profile = getBuilderProfile();
  const signature = JSON.stringify({
    selectedProfileId: state.selectedProfileId,
    selectedStateName: selectedState?.name || null,
    selectedState,
    initialState: profile?.initial_state || null,
  });
  if (signature === state.lastBuilderStateEditorSignature) {
    return;
  }
  state.lastBuilderStateEditorSignature = signature;
  target.innerHTML = "";
  $("builder-set-initial-button").disabled = !selectedState || selectedState.name === profile?.initial_state;
  $("builder-delete-state-button").disabled = !selectedState || (profile?.states || []).length <= 1;
  if (!selectedState || !profile) {
    target.innerHTML = '<div class="builder-detail-section builder-field-full"><strong>No state selected</strong><div class="builder-anchor-meta">Choose a state before editing graph properties.</div></div>';
    return;
  }
  target.appendChild(createBuilderField({
    label: "State Name",
    name: "state.name",
    value: selectedState.name,
    section: "state",
  }));
  target.appendChild(createBuilderField({
    label: "On Success",
    name: "state.on_success",
    value: selectedState.on_success || "",
    section: "state",
    kind: "state_name_optional",
  }));
  target.appendChild(createBuilderField({
    label: "On Failure",
    name: "state.on_failure",
    value: selectedState.on_failure || "graceful_termination",
    section: "state",
    kind: "failure_target",
  }));
  target.appendChild(createBuilderField({
    label: "Result",
    name: "state.result",
    value: selectedState.result || "",
    section: "state",
    kind: "result_value",
  }));
  const terminalRow = document.createElement("label");
  terminalRow.className = "builder-checkbox builder-field-full";
  terminalRow.innerHTML = `<input id="builder-state-terminal" type="checkbox" data-builder-section="state" data-builder-field="state.terminal" ${selectedState.terminal ? "checked" : ""} /><span><strong>Terminal State</strong><code>When enabled, the runner can finish here.</code></span>`;
  target.appendChild(terminalRow);
}

function renderBuilderValidation() {
  const target = $("builder-validation-list");
  const draft = state.builderDraft;
  const errors = draft?.validation_errors || [];
  const signature = JSON.stringify({
    profileId: draft?.profile_id || null,
    loadError: draft?.load_error || null,
    errors,
  });
  if (signature === state.lastBuilderValidationSignature) {
    return;
  }
  state.lastBuilderValidationSignature = signature;
  target.innerHTML = "";
  const messages = draft?.load_error ? [draft.load_error, ...errors.filter((item) => item !== draft.load_error)] : errors;
  $("builder-validation-count").textContent = `${messages.length} issue${messages.length === 1 ? "" : "s"}`;
  if (!messages.length) {
    target.innerHTML = '<li class="muted">No validation issues reported by the backend schema.</li>';
    return;
  }
  for (const message of messages) {
    const item = document.createElement("li");
    item.textContent = message;
    target.appendChild(item);
  }
}

function renderBuilderPackCheck() {
  const target = $("builder-pack-check");
  const packCheck = state.builderDraft?.pack_check || null;
  const signature = JSON.stringify({
    selectedProfileId: state.selectedProfileId,
    packCheck,
  });
  if (signature === state.lastBuilderPackCheckSignature) {
    return;
  }
  state.lastBuilderPackCheckSignature = signature;
  if (!packCheck) {
    target.className = "builder-pack-check muted";
    target.textContent = "Pack checks will appear here for pack-shaped profiles.";
    return;
  }
  const tone = packCheck.ok
    ? (packCheck.warnings?.length ? "warn" : "good")
    : "bad";
  target.className = `builder-pack-check ${tone}`;
  target.innerHTML = `
    <div class="builder-check-summary">
      <h4>Pack Check ${packCheck.ok ? "Passed" : "Blocked"}</h4>
      <div class="builder-anchor-meta">errors=${(packCheck.errors || []).length} | warnings=${(packCheck.warnings || []).length}</div>
      <strong>Errors</strong>
      <ul class="message-list">${(packCheck.errors || []).length ? packCheck.errors.map((item) => `<li>${escapeHtml(item)}</li>`).join("") : '<li class="muted">None</li>'}</ul>
      <strong>Warnings</strong>
      <ul class="message-list">${(packCheck.warnings || []).length ? packCheck.warnings.map((item) => `<li>${escapeHtml(item)}</li>`).join("") : '<li class="muted">None</li>'}</ul>
    </div>
  `;
}

function renderBuilderVisualTools() {
  const profile = getBuilderProfile();
  const selectedState = builderSelectedState();
  const signature = JSON.stringify({
    selectedProfileId: state.selectedProfileId,
    preview: state.builderPreview,
    previewStatus: state.builderPreviewStatus,
    previewTone: state.builderPreviewTone,
    drawRect: state.builderDrawRect,
    selectedRegionName: state.selectedBuilderRegionName,
    regions: profile?.regions || [],
    anchors: selectedState
      ? {
        required_anchors: selectedState.required_anchors || [],
        optional_anchors: selectedState.optional_anchors || [],
        forbidden_anchors: selectedState.forbidden_anchors || [],
      }
      : null,
    assets: state.builderAssets,
  });
  if (signature === state.lastBuilderVisualSignature) {
    return;
  }
  state.lastBuilderVisualSignature = signature;
  renderBuilderPreviewStage(profile);
  renderBuilderRegionList(profile);
  renderBuilderAnchorList(selectedState);
  renderBuilderAssetList();
  const previewStatus = $("builder-preview-status");
  previewStatus.textContent = state.builderPreviewStatus;
  previewStatus.className = state.builderPreviewTone === "muted"
    ? "muted"
    : `builder-status builder-status-${state.builderPreviewTone}`;
  $("builder-preview-refresh-button").disabled = !state.selectedProfileId;
  $("builder-region-save-button").disabled = !profile || !state.builderDrawRect;
  $("builder-region-remove-button").disabled = !profile || !state.selectedBuilderRegionName;
  $("builder-anchor-save-button").disabled = !selectedState;
  $("builder-anchor-crop-button").disabled = !selectedState || !state.builderDrawRect;
}

function renderBuilderPreviewStage(profile) {
  const stage = $("builder-preview-stage");
  const image = $("builder-preview-image");
  const empty = $("builder-preview-empty");
  const overlay = $("builder-preview-overlay");
  const meta = $("builder-preview-meta");
  const preview = state.builderPreview;
  if (!preview) {
    image.hidden = true;
    image.removeAttribute("src");
    overlay.innerHTML = "";
    overlay.setAttribute("viewBox", "0 0 1 1");
    empty.hidden = false;
    empty.textContent = "Preview unavailable";
    meta.textContent = "Refresh the builder preview to draw regions and template crops.";
    stage.classList.remove("has-preview");
    return;
  }
  image.src = preview.data_url;
  image.hidden = false;
  empty.hidden = true;
  meta.textContent = `${preview.title} - ${preview.process_name || "unknown process"} - client ${preview.width}x${preview.height}`;
  overlay.setAttribute("viewBox", `0 0 ${preview.width} ${preview.height}`);
  overlay.innerHTML = "";
  for (const region of profile?.regions || []) {
    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("x", String(region.x));
    rect.setAttribute("y", String(region.y));
    rect.setAttribute("width", String(region.width));
    rect.setAttribute("height", String(region.height));
    rect.setAttribute(
      "class",
      region.name === state.selectedBuilderRegionName
        ? "builder-overlay-region is-selected"
        : "builder-overlay-region",
    );
    rect.dataset.regionName = region.name;
    overlay.appendChild(rect);
    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("x", String(region.x + 4));
    label.setAttribute("y", String(Math.max(14, region.y + 14)));
    label.setAttribute("class", "builder-overlay-label");
    label.textContent = region.name;
    overlay.appendChild(label);
  }
  if (state.builderDrawRect) {
    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("x", String(state.builderDrawRect.x));
    rect.setAttribute("y", String(state.builderDrawRect.y));
    rect.setAttribute("width", String(state.builderDrawRect.width));
    rect.setAttribute("height", String(state.builderDrawRect.height));
    rect.setAttribute("class", "builder-overlay-selection");
    overlay.appendChild(rect);
  }
}

function renderBuilderRegionList(profile) {
  const target = $("builder-region-list");
  const regions = profile?.regions || [];
  target.innerHTML = "";
  if (!regions.length) {
    target.innerHTML = '<li class="muted">No named regions yet</li>';
    return;
  }
  for (const region of regions) {
    const item = document.createElement("li");
    item.innerHTML = `
      <div class="builder-action-card-header">
        <strong>${escapeHtml(region.name)}</strong>
        <div class="builder-action-controls">
          <button type="button" data-builder-region-select="${escapeHtml(region.name)}">Select</button>
        </div>
      </div>
      <div class="builder-anchor-meta">x=${region.x} y=${region.y} width=${region.width} height=${region.height}</div>
    `;
    target.appendChild(item);
  }
}

function renderBuilderAnchorList(selectedState) {
  const target = $("builder-anchor-list");
  target.innerHTML = "";
  if (!selectedState) {
    target.innerHTML = '<li class="muted">Select a state to manage anchors</li>';
    return;
  }
  const buckets = [
    ["required_anchors", "Required"],
    ["optional_anchors", "Optional"],
    ["forbidden_anchors", "Forbidden"],
  ];
  let count = 0;
  for (const [bucketKey, label] of buckets) {
    for (const [index, anchor] of (selectedState[bucketKey] || []).entries()) {
      count += 1;
      const item = document.createElement("li");
      const assetPreview = anchor.asset
        ? `<img class="builder-mini-thumb" src="/api/profiles/${encodeURIComponent(state.selectedProfileId)}/assets/${encodeURIComponent(anchor.asset).replace(/%2F/g, "/")}" alt="${escapeHtml(anchor.name)}" />`
        : "";
      item.innerHTML = `
        <div class="builder-action-card-header">
          <strong>${escapeHtml(anchor.name)}</strong>
          <div class="builder-action-controls">
            <button type="button" data-builder-anchor-remove="${bucketKey}:${index}">Remove</button>
          </div>
        </div>
        <div class="builder-anchor-meta">${escapeHtml(label)} | type=${escapeHtml(anchor.type)}${anchor.text ? ` | text=${escapeHtml(anchor.text)}` : ""}${anchor.asset ? ` | asset=${escapeHtml(anchor.asset)}` : ""}</div>
        ${assetPreview}
      `;
      target.appendChild(item);
    }
  }
  if (!count) {
    target.innerHTML = '<li class="muted">No anchors in the selected state</li>';
  }
}

function renderBuilderAssetList() {
  const target = $("builder-asset-list");
  target.innerHTML = "";
  if (!state.builderAssets.length) {
    target.innerHTML = '<li class="muted">No assets in this pack yet</li>';
    return;
  }
  for (const asset of state.builderAssets) {
    const item = document.createElement("li");
    const isImage = String(asset.content_type || "").startsWith("image/");
    item.innerHTML = `
      <strong>${escapeHtml(asset.path)}</strong>
      <div class="builder-anchor-meta">${escapeHtml(asset.content_type || "file")} | ${asset.size} bytes</div>
      ${isImage ? `<img class="builder-mini-thumb" src="/api/profiles/${encodeURIComponent(state.selectedProfileId)}/assets/${encodeURIComponent(asset.path).replace(/%2F/g, "/")}" alt="${escapeHtml(asset.path)}" />` : ""}
    `;
    target.appendChild(item);
  }
}

async function refreshBuilderPreviewSnapshot() {
  if (!state.selectedProfileId) {
    return;
  }
  state.builderPreviewStatus = "Refreshing builder preview...";
  state.builderPreviewTone = "warn";
  renderBuilderVisualTools();
  try {
    state.builderPreview = await api(`/api/profiles/${encodeURIComponent(state.selectedProfileId)}/target-preview`);
    state.builderPreviewStatus = "Preview ready";
    state.builderPreviewTone = "good";
  } catch (error) {
    state.builderPreview = null;
    state.builderPreviewStatus = error.message;
    state.builderPreviewTone = "bad";
  }
  renderBuilderVisualTools();
}

function pointerToPreviewPoint(event) {
  const overlay = $("builder-preview-overlay");
  const preview = state.builderPreview;
  if (!preview) {
    return null;
  }
  const rect = overlay.getBoundingClientRect();
  if (!rect.width || !rect.height) {
    return null;
  }
  const x = Math.max(0, Math.min(preview.width, Math.round(((event.clientX - rect.left) / rect.width) * preview.width)));
  const y = Math.max(0, Math.min(preview.height, Math.round(((event.clientY - rect.top) / rect.height) * preview.height)));
  return { x, y };
}

function updateBuilderDrawRect(point) {
  if (!state.builderDragStart || !point) {
    return;
  }
  const left = Math.min(state.builderDragStart.x, point.x);
  const top = Math.min(state.builderDragStart.y, point.y);
  const width = Math.abs(state.builderDragStart.x - point.x);
  const height = Math.abs(state.builderDragStart.y - point.y);
  state.builderDrawRect = width > 0 && height > 0
    ? { x: left, y: top, width, height }
    : null;
  renderBuilderVisualTools();
}

async function saveBuilderRegionFromDraw() {
  const profile = getBuilderProfile();
  const name = $("builder-region-name").value.trim();
  if (!profile || !state.builderDrawRect || !name) {
    setBuilderStatus("Draw a rectangle and provide a region name", "bad");
    renderBuilderToolbar();
    return;
  }
  const existingIndex = (profile.regions || []).findIndex((region) => region.name === name);
  const regionPayload = { name, ...state.builderDrawRect };
  if (existingIndex >= 0) {
    profile.regions.splice(existingIndex, 1, regionPayload);
  } else {
    profile.regions.push(regionPayload);
  }
  state.selectedBuilderRegionName = name;
  markBuilderDirty(`Saved region ${name}`);
  await previewBuilderDraft();
}

async function removeSelectedBuilderRegion() {
  const profile = getBuilderProfile();
  if (!profile || !state.selectedBuilderRegionName) {
    return;
  }
  const nextRegions = (profile.regions || []).filter((region) => region.name !== state.selectedBuilderRegionName);
  profile.regions = nextRegions;
  state.selectedBuilderRegionName = null;
  $("builder-region-name").value = "";
  markBuilderDirty("Removed region");
  await previewBuilderDraft();
}

async function removeBuilderAnchor(bucketKey, index) {
  const selectedState = builderSelectedState();
  if (!selectedState || !selectedState[bucketKey]) {
    return;
  }
  selectedState[bucketKey].splice(index, 1);
  markBuilderDirty("Removed anchor");
  await previewBuilderDraft();
}

async function saveBuilderAnchor() {
  const selectedState = builderSelectedState();
  if (!selectedState) {
    return;
  }
  const bucketKey = $("builder-anchor-bucket-select").value;
  const anchorType = $("builder-anchor-type-select").value;
  const anchorName = $("builder-anchor-name").value.trim();
  const anchorText = $("builder-anchor-text").value.trim();
  if (!anchorName) {
    setBuilderStatus("Anchor name is required", "bad");
    renderBuilderToolbar();
    return;
  }
  const anchor = { name: anchorName, type: anchorType };
  if (anchorType === "text") {
    if (!anchorText) {
      setBuilderStatus("Text anchors require OCR text", "bad");
      renderBuilderToolbar();
      return;
    }
    anchor.text = anchorText;
  } else {
    const assetPath = anchorText || `assets/${anchorName}.png`;
    anchor.asset = assetPath.startsWith("assets/") ? assetPath : `assets/${assetPath}`;
  }
  const bucket = selectedState[bucketKey] || [];
  const existingIndex = bucket.findIndex((item) => item.name === anchor.name);
  if (existingIndex >= 0) {
    bucket.splice(existingIndex, 1, anchor);
  } else {
    bucket.push(anchor);
  }
  selectedState[bucketKey] = bucket;
  markBuilderDirty(`Updated anchor ${anchorName}`);
  await previewBuilderDraft();
}

async function cropBuilderTemplateAnchor() {
  if (!state.selectedProfileId || !state.builderDrawRect) {
    return;
  }
  const anchorName = $("builder-anchor-name").value.trim();
  const rawAssetName = $("builder-anchor-text").value.trim() || anchorName;
  if (!anchorName || !rawAssetName) {
    setBuilderStatus("Anchor name and asset name are required for template crops", "bad");
    renderBuilderToolbar();
    return;
  }
  const assetFileName = rawAssetName.toLowerCase().endsWith(".png") ? rawAssetName : `${rawAssetName}.png`;
  const assetPath = assetFileName.startsWith("assets/") ? assetFileName.slice("assets/".length) : assetFileName;
  const result = await api(`/api/profiles/${encodeURIComponent(state.selectedProfileId)}/assets/template-crop`, {
    method: "POST",
    body: JSON.stringify({
      asset_path: assetPath,
      x: state.builderDrawRect.x,
      y: state.builderDrawRect.y,
      width: state.builderDrawRect.width,
      height: state.builderDrawRect.height,
    }),
  });
  $("builder-anchor-type-select").value = "template";
  $("builder-anchor-text").value = result.asset.path;
  await refreshBuilderAssets();
  await saveBuilderAnchor();
}

function renderBuilderStateDetail() {
  const target = $("builder-state-detail");
  const draft = state.builderDraft;
  const profile = getBuilderProfile();
  const selectedState = profile?.states?.find((item) => item.name === state.selectedBuilderStateName) || null;
  const signature = JSON.stringify({
    profileId: state.selectedProfileId,
    selectedBuilderStateName: state.selectedBuilderStateName,
    selectedState,
    dirty: state.builderDirty,
  });
  if (signature === state.lastBuilderStateDetailSignature) {
    return;
  }
  state.lastBuilderStateDetailSignature = signature;
  target.innerHTML = "";
  if (!selectedState) {
    target.innerHTML = '<div class="builder-detail-section"><h4>No State Selected</h4><div class="muted">Choose a state to inspect anchors, actions, and transitions.</div></div>';
    return;
  }
  const header = document.createElement("div");
  header.className = "builder-detail-section";
  header.innerHTML = `
    <h4>${escapeHtml(selectedState.name)}</h4>
    <div class="builder-anchor-meta">on_success=${escapeHtml(selectedState.on_success || "none")} | on_failure=${escapeHtml(selectedState.on_failure || "graceful_termination")} | terminal=${selectedState.terminal ? "true" : "false"}${selectedState.result ? ` | result=${escapeHtml(selectedState.result)}` : ""}</div>
  `;
  target.appendChild(header);
  target.appendChild(renderAnchorSection("Required Anchors", selectedState.required_anchors));
  target.appendChild(renderAnchorSection("Optional Anchors", selectedState.optional_anchors));
  target.appendChild(renderAnchorSection("Forbidden Anchors", selectedState.forbidden_anchors));
  target.appendChild(renderActionSection("Action Timeline", selectedState));
}

function renderAnchorSection(title, anchors) {
  const section = document.createElement("section");
  section.className = "builder-detail-section";
  section.innerHTML = `<h4>${escapeHtml(title)}</h4>`;
  const list = document.createElement("ul");
  list.className = "builder-detail-list";
  if (!anchors.length) {
    list.innerHTML = '<li class="muted">None</li>';
  } else {
    for (const anchor of anchors) {
      const item = document.createElement("li");
      const detailParts = [];
      if (anchor.asset) {
        detailParts.push(`asset=${anchor.asset}`);
      }
      if (anchor.text) {
        detailParts.push(`text=${anchor.text}`);
      }
      item.innerHTML = `
        <strong>${escapeHtml(anchor.name)}</strong>
        <div class="builder-anchor-meta">type=${escapeHtml(anchor.type)}${detailParts.length ? ` | ${escapeHtml(detailParts.join(" | "))}` : ""}</div>
      `;
      list.appendChild(item);
    }
  }
  section.appendChild(list);
  return section;
}

function renderActionSection(title, selectedState) {
  const section = document.createElement("section");
  section.className = "builder-detail-section";
  section.innerHTML = `<h4>${escapeHtml(title)}</h4>`;
  const list = document.createElement("ol");
  list.className = "builder-action-list";
  list.dataset.stateName = selectedState.name;
  const actions = selectedState.actions || [];
  if (!actions.length) {
    list.innerHTML = '<li class="muted">No actions configured</li>';
  } else {
    for (const [index, action] of actions.entries()) {
      const item = document.createElement("li");
      item.className = "builder-action-card";
      item.draggable = true;
      item.dataset.stateName = selectedState.name;
      item.dataset.actionIndex = String(index);
      const label = action.label || state.builderSchema?.actions?.[action.type]?.label || action.type;
      const readonlyBanner = action.editable === false
        ? '<div class="builder-action-warning">This action is preserved, but the current editor does not support changing it yet.</div>'
        : "";
      item.innerHTML = `
        <div class="builder-action-card-header">
          <strong>${index + 1}. ${escapeHtml(label)}</strong>
          <div class="builder-action-controls">
            <button type="button" data-action-command="move-up" data-action-index="${index}">Up</button>
            <button type="button" data-action-command="move-down" data-action-index="${index}">Down</button>
            <button type="button" data-action-command="remove" data-action-index="${index}">Remove</button>
          </div>
        </div>
        <div class="builder-action-meta">${escapeHtml(formatActionData(action.data))}</div>
        ${readonlyBanner}
      `;
      if (action.editable !== false) {
        item.appendChild(renderActionFields(selectedState.name, index, action));
      }
      list.appendChild(item);
    }
  }
  section.appendChild(list);
  return section;
}

function renderActionFields(stateName, actionIndex, action) {
  const form = document.createElement("div");
  form.className = "builder-action-form";
  if (action.type === "start_continuous_input") {
    return renderContinuousInputFields(stateName, actionIndex, action);
  }
  const definition = state.builderSchema?.actions?.[action.type];
  const fields = definition?.fields || [];
  if (!fields.length) {
    form.innerHTML = '<div class="muted">No editable fields defined for this action.</div>';
    return form;
  }
  for (const field of fields) {
    const row = document.createElement("label");
    row.className = "builder-field";
    const fieldName = field.name;
    const value = action.data?.[fieldName];
    row.innerHTML = `<span>${escapeHtml(fieldName)}</span>`;
    row.appendChild(createActionFieldInput(stateName, actionIndex, action.type, field, value));
    form.appendChild(row);
  }
  return form;
}

function renderContinuousInputFields(stateName, actionIndex, action) {
  const form = document.createElement("div");
  form.className = "builder-action-form";
  const baseFields = state.builderSchema?.actions?.start_continuous_input?.fields || [];
  for (const field of baseFields) {
    if (field.name === "sequence") {
      continue;
    }
    const row = document.createElement("label");
    row.className = "builder-field";
    row.innerHTML = `<span>${escapeHtml(field.name)}</span>`;
    row.appendChild(
      createActionFieldInput(
        stateName,
        actionIndex,
        action.type,
        field,
        action.data?.[field.name],
      ),
    );
    form.appendChild(row);
  }
  const continuousType = action.data?.action || "press_key";
  const continuousDefinition = state.builderSchema?.continuous_actions?.[continuousType];
  const section = document.createElement("div");
  section.className = "builder-detail-section";
  section.innerHTML = `<h4>${escapeHtml(continuousDefinition?.label || continuousType)}</h4>`;
  if (continuousType === "sequence") {
    section.appendChild(renderContinuousSequenceEditor(stateName, actionIndex, action));
  } else {
    const nestedForm = document.createElement("div");
    nestedForm.className = "builder-action-form";
    for (const field of continuousDefinition?.fields || []) {
      const row = document.createElement("label");
      row.className = "builder-field";
      row.innerHTML = `<span>${escapeHtml(field.name)}</span>`;
      row.appendChild(
        createActionFieldInput(
          stateName,
          actionIndex,
          action.type,
          field,
          action.data?.[field.name],
          { nestedPath: field.name, nestedKind: "continuous" },
        ),
      );
      nestedForm.appendChild(row);
    }
    section.appendChild(nestedForm);
  }
  form.appendChild(section);
  return form;
}

function renderContinuousSequenceEditor(stateName, actionIndex, action) {
  const wrapper = document.createElement("div");
  wrapper.className = "builder-detail-grid";
  const sequence = Array.isArray(action.data?.sequence) ? action.data.sequence : [];
  if (!sequence.length) {
    wrapper.innerHTML = '<div class="muted">No sequence steps yet.</div>';
  } else {
    for (const [stepIndex, step] of sequence.entries()) {
      const card = document.createElement("div");
      card.className = "builder-detail-section";
      const definition = state.builderSchema?.continuous_actions?.[step.action];
      card.innerHTML = `
        <div class="builder-action-card-header">
          <strong>Step ${stepIndex + 1}</strong>
          <div class="builder-action-controls">
            <button type="button" data-sequence-command="move-up" data-action-index="${actionIndex}" data-step-index="${stepIndex}">Up</button>
            <button type="button" data-sequence-command="move-down" data-action-index="${actionIndex}" data-step-index="${stepIndex}">Down</button>
            <button type="button" data-sequence-command="remove" data-action-index="${actionIndex}" data-step-index="${stepIndex}">Remove</button>
          </div>
        </div>
      `;
      const body = document.createElement("div");
      body.className = "builder-action-form";
      const actionField = document.createElement("label");
      actionField.className = "builder-field";
      actionField.innerHTML = "<span>action</span>";
      actionField.appendChild(
        createActionFieldInput(
          stateName,
          actionIndex,
          action.type,
          { name: "action", kind: "continuous_step_action", required: true },
          step.action,
          { nestedPath: `sequence.${stepIndex}.action`, nestedKind: "sequence" },
        ),
      );
      body.appendChild(actionField);
      const runForField = document.createElement("label");
      runForField.className = "builder-field";
      runForField.innerHTML = "<span>run_for_seconds</span>";
      runForField.appendChild(
        createActionFieldInput(
          stateName,
          actionIndex,
          action.type,
          { name: "run_for_seconds", kind: "duration", required: true },
          step.run_for_seconds,
          { nestedPath: `sequence.${stepIndex}.run_for_seconds`, nestedKind: "sequence" },
        ),
      );
      body.appendChild(runForField);
      for (const field of definition?.fields || []) {
        if (field.name === "sequence") {
          continue;
        }
        const row = document.createElement("label");
        row.className = "builder-field";
        row.innerHTML = `<span>${escapeHtml(field.name)}</span>`;
        row.appendChild(
          createActionFieldInput(
            stateName,
            actionIndex,
            action.type,
            field,
            step[field.name],
            { nestedPath: `sequence.${stepIndex}.${field.name}`, nestedKind: "sequence" },
          ),
        );
        body.appendChild(row);
      }
      card.appendChild(body);
      wrapper.appendChild(card);
    }
  }
  const actions = document.createElement("div");
  actions.className = "builder-inline-actions";
  actions.innerHTML = `
    <select id="builder-sequence-action-select">
      ${continuousStepActionOptions().map((actionType) => `<option value="${escapeHtml(actionType)}">${escapeHtml(state.builderSchema?.continuous_actions?.[actionType]?.label || actionType)}</option>`).join("")}
    </select>
    <button type="button" data-sequence-command="add" data-action-index="${actionIndex}">Add Step</button>
  `;
  wrapper.appendChild(actions);
  return wrapper;
}

function createActionFieldInput(stateName, actionIndex, actionType, field, value, options = {}) {
  const kind = field.kind || "string";
  if (["key", "input_mode", "region", "state_name", "asset_path", "mouse_button", "scroll_direction", "continuous_action", "continuous_step_action"].includes(kind)) {
    const select = document.createElement("select");
    applyActionFieldDataset(select, stateName, actionIndex, actionType, field.name, kind, options);
    const required = Boolean(field.required);
    if (!required) {
      const empty = document.createElement("option");
      empty.value = "";
      empty.textContent = "Optional";
      select.appendChild(empty);
    }
    for (const optionValue of actionFieldOptions(kind)) {
      const option = document.createElement("option");
      option.value = optionValue;
      option.textContent = optionValue;
      select.appendChild(option);
    }
    select.value = value ?? "";
    return select;
  }
  if (kind === "key_list") {
    const input = document.createElement("input");
    input.type = "text";
    applyActionFieldDataset(input, stateName, actionIndex, actionType, field.name, kind, options);
    input.value = Array.isArray(value) ? value.join(", ") : "";
    input.placeholder = "comma,separated,keys";
    return input;
  }
  const input = document.createElement("input");
  applyActionFieldDataset(input, stateName, actionIndex, actionType, field.name, kind, options);
  input.value = value ?? "";
  if (kind === "duration" || kind === "number" || kind === "integer") {
    input.type = "number";
    input.step = kind === "integer" ? "1" : "0.1";
  } else {
    input.type = "text";
  }
  input.placeholder = field.required ? "Required" : "Optional";
  return input;
}

function applyActionFieldDataset(target, stateName, actionIndex, actionType, fieldName, fieldKind, options = {}) {
  target.dataset.stateName = stateName;
  target.dataset.actionIndex = String(actionIndex);
  target.dataset.actionType = actionType;
  target.dataset.fieldName = fieldName;
  target.dataset.fieldKind = fieldKind;
  if (options.nestedPath) {
    target.dataset.nestedPath = options.nestedPath;
  }
  if (options.nestedKind) {
    target.dataset.nestedKind = options.nestedKind;
  }
}

function actionFieldOptions(kind) {
  const profile = getBuilderProfile();
  if (kind === "key") {
    return state.builderSchema?.supported_keys || [];
  }
  if (kind === "input_mode") {
    return state.builderSchema?.supported_input_modes || [];
  }
  if (kind === "region") {
    return (profile?.regions || []).map((region) => region.name);
  }
  if (kind === "state_name") {
    return (profile?.states || []).map((stateItem) => stateItem.name);
  }
  if (kind === "asset_path") {
    return (state.builderAssets || []).map((asset) => `assets/${asset.path}`);
  }
  if (kind === "mouse_button") {
    return state.builderSchema?.supported_mouse_buttons || [];
  }
  if (kind === "scroll_direction") {
    return state.builderSchema?.supported_scroll_directions || [];
  }
  if (kind === "continuous_action") {
    return Object.keys(state.builderSchema?.continuous_actions || {});
  }
  if (kind === "continuous_step_action") {
    return continuousStepActionOptions();
  }
  return [];
}

function continuousStepActionOptions() {
  return Object.keys(state.builderSchema?.continuous_actions || {}).filter((actionType) => actionType !== "sequence");
}

function formatActionData(data) {
  const entries = Object.entries(data || {});
  if (!entries.length) {
    return "No extra fields";
  }
  return entries.map(([key, value]) => `${key}: ${formatValue(value)}`).join("\n");
}

function formatValue(value) {
  if (value === null || value === undefined) {
    return "null";
  }
  if (Array.isArray(value)) {
    return value.map((item) => formatValue(item)).join(", ");
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function renderBuilderYamlPreview() {
  $("builder-yaml-preview").textContent = state.builderDraft?.source || "No profile source loaded.";
}

async function previewBuilderDraft() {
  const profile = getBuilderProfile();
  if (!state.selectedProfileId || !profile) {
    return;
  }
  const draft = await api(`/api/profiles/${encodeURIComponent(state.selectedProfileId)}/draft`, {
    method: "POST",
    body: JSON.stringify({ profile, notes: getBuilderNotes() }),
  });
  state.builderDraft = draft;
  setBuilderStatus(
    state.builderDirty
      ? (draft.valid ? "Unsaved changes validated locally" : "Unsaved changes need fixes")
      : (draft.valid ? "Saved profile loaded" : "Loaded with validation issues"),
    state.builderDirty ? (draft.valid ? "warn" : "bad") : (draft.valid ? "good" : "warn"),
  );
  renderBuilder();
}

function builderSelectedState() {
  return getBuilderProfile()?.states?.find((item) => item.name === state.selectedBuilderStateName) || null;
}

function markBuilderDirty(message = "Unsaved changes") {
  state.builderDirty = true;
  setBuilderStatus(message, "warn");
}

function defaultActionData(actionType) {
  const profile = getBuilderProfile();
  if (actionType === "log") {
    return { message: "" };
  }
  if (actionType === "wait") {
    return { seconds: 1 };
  }
  if (actionType === "press_key" || actionType === "hold_key") {
    return { key: "f" };
  }
  if (actionType === "press_keys" || actionType === "hold_keys") {
    return { keys: ["f"] };
  }
  if (actionType === "repeat_key") {
    return { key: "f", repeat_for_seconds: 1, repeat_every_seconds: 0.2 };
  }
  if (actionType === "hold_key_while_repeating_key") {
    return {
      hold_key: "w",
      tap_key: "space",
      hold_seconds: 1,
      tap_every_seconds: 0.2,
    };
  }
  if (actionType === "click_point") {
    return { region: profile?.regions?.[0]?.name || "" };
  }
  if (actionType === "click_template") {
    return { target: `assets/${state.builderAssets?.[0]?.path || ""}` };
  }
  if (actionType === "hold_click") {
    return { region: profile?.regions?.[0]?.name || "", seconds: 1, input_mode: "foreground" };
  }
  if (actionType === "move_mouse") {
    return { dx: 100, dy: 0, seconds: 0.5, input_mode: "foreground" };
  }
  if (actionType === "hold_mouse_button_and_move") {
    return { button: "right", dx: 100, dy: 0, seconds: 0.5, input_mode: "foreground" };
  }
  if (actionType === "scroll_mouse") {
    return { direction: "down", steps: 1, input_mode: "foreground" };
  }
  if (actionType === "start_continuous_input") {
    return {
      name: "continuous_action",
      action: "press_key",
      key: "f",
      repeat_every_seconds: 0.2,
      seconds: 0.1,
    };
  }
  if (actionType === "wait_for_state") {
    return { state: profile?.states?.[0]?.name || "" };
  }
  if (actionType === "stop") {
    return { result: "success" };
  }
  if (actionType === "stop_continuous_input") {
    return { name: "continuous_action" };
  }
  return {};
}

function normalizeActionForEditor(actionType, data = {}) {
  return {
    type: actionType,
    label: state.builderSchema?.actions?.[actionType]?.label || actionType,
    editable: (state.builderSchema?.editable_action_types || []).includes(actionType),
    data: cloneValue(data) || {},
  };
}

async function addBuilderAction() {
  const profile = getBuilderProfile();
  const selectedState = builderSelectedState();
  const actionType = $("builder-add-action-select").value;
  if (!profile || !selectedState || !actionType) {
    return;
  }
  selectedState.actions.push(normalizeActionForEditor(actionType, defaultActionData(actionType)));
  markBuilderDirty(`Added ${state.builderSchema?.actions?.[actionType]?.label || actionType}`);
  await previewBuilderDraft();
}

async function revertBuilderDraft() {
  if (!state.builderOriginalProfile) {
    return;
  }
  state.builderWorkingProfile = cloneValue(state.builderOriginalProfile);
  state.builderWorkingNotes = state.builderOriginalNotes;
  state.builderDirty = false;
  state.builderDraft = state.builderDraft
    ? {
      ...state.builderDraft,
      profile: cloneValue(state.builderOriginalProfile),
      notes: state.builderOriginalNotes,
    }
    : state.builderDraft;
  setBuilderStatus("Reverted unsaved changes", "muted");
  await previewBuilderDraft();
}

async function saveBuilderDraft() {
  const profile = getBuilderProfile();
  if (!state.selectedProfileId || !profile) {
    return;
  }
  setBuilderStatus("Saving draft to profile.yaml...", "warn");
  renderBuilderToolbar();
  const draft = await api(`/api/profiles/${encodeURIComponent(state.selectedProfileId)}/save`, {
    method: "POST",
    body: JSON.stringify({ profile, notes: getBuilderNotes() }),
  });
  state.builderDraft = draft;
  if (draft.valid) {
    state.builderOriginalProfile = cloneValue(draft.profile);
    state.builderWorkingProfile = cloneValue(draft.profile);
    state.builderOriginalNotes = draft.notes || "";
    state.builderWorkingNotes = draft.notes || "";
    state.builderDirty = false;
    setBuilderStatus("Saved to profile.yaml", "good");
    await refreshProfiles({ refreshReadinessAfter: true });
  } else {
    setBuilderStatus("Save blocked by validation errors", "bad");
  }
  renderBuilder();
}

async function handleBuilderActionCommand(command, actionIndex) {
  const selectedState = builderSelectedState();
  if (!selectedState) {
    return;
  }
  if (command === "remove") {
    selectedState.actions.splice(actionIndex, 1);
    markBuilderDirty("Removed action");
  }
  if (command === "move-up" && actionIndex > 0) {
    [selectedState.actions[actionIndex - 1], selectedState.actions[actionIndex]] = [selectedState.actions[actionIndex], selectedState.actions[actionIndex - 1]];
    markBuilderDirty("Reordered action");
  }
  if (command === "move-down" && actionIndex < selectedState.actions.length - 1) {
    [selectedState.actions[actionIndex + 1], selectedState.actions[actionIndex]] = [selectedState.actions[actionIndex], selectedState.actions[actionIndex + 1]];
    markBuilderDirty("Reordered action");
  }
  await previewBuilderDraft();
}

function defaultContinuousStep(actionType) {
  if (actionType === "click_point") {
    return { action: actionType, region: getBuilderProfile()?.regions?.[0]?.name || "", repeat_every_seconds: 0.2, run_for_seconds: 1 };
  }
  if (actionType === "hold_click") {
    return { action: actionType, region: getBuilderProfile()?.regions?.[0]?.name || "", run_for_seconds: 1 };
  }
  if (actionType === "press_key") {
    return { action: actionType, key: "f", repeat_every_seconds: 0.2, seconds: 0.1, run_for_seconds: 1 };
  }
  if (actionType === "press_keys") {
    return { action: actionType, keys: ["f"], repeat_every_seconds: 0.2, seconds: 0.1, run_for_seconds: 1 };
  }
  if (actionType === "hold_key") {
    return { action: actionType, key: "w", run_for_seconds: 1 };
  }
  if (actionType === "hold_keys") {
    return { action: actionType, keys: ["w"], run_for_seconds: 1 };
  }
  if (actionType === "repeat_key") {
    return { action: actionType, key: "f", repeat_every_seconds: 0.2, run_for_seconds: 1 };
  }
  if (actionType === "hold_key_while_repeating_key") {
    return { action: actionType, hold_key: "w", tap_key: "space", tap_every_seconds: 0.2, run_for_seconds: 1 };
  }
  if (actionType === "scroll_mouse") {
    return { action: actionType, direction: "down", steps: 1, input_mode: "foreground", repeat_every_seconds: 0.2, run_for_seconds: 1 };
  }
  return { action: actionType, run_for_seconds: 1 };
}

async function handleSequenceCommand(command, actionIndex, stepIndex) {
  const selectedState = builderSelectedState();
  if (!selectedState) {
    return;
  }
  const action = selectedState.actions?.[actionIndex];
  if (!action) {
    return;
  }
  action.data.sequence = Array.isArray(action.data.sequence) ? action.data.sequence : [];
  if (command === "add") {
    const actionType = $("builder-sequence-action-select").value || "press_key";
    action.data.sequence.push(defaultContinuousStep(actionType));
    markBuilderDirty("Added continuous sequence step");
    await previewBuilderDraft();
    return;
  }
  if (stepIndex < 0 || stepIndex >= action.data.sequence.length) {
    return;
  }
  if (command === "remove") {
    action.data.sequence.splice(stepIndex, 1);
    markBuilderDirty("Removed continuous sequence step");
  }
  if (command === "move-up" && stepIndex > 0) {
    [action.data.sequence[stepIndex - 1], action.data.sequence[stepIndex]] = [action.data.sequence[stepIndex], action.data.sequence[stepIndex - 1]];
    markBuilderDirty("Reordered continuous sequence step");
  }
  if (command === "move-down" && stepIndex < action.data.sequence.length - 1) {
    [action.data.sequence[stepIndex + 1], action.data.sequence[stepIndex]] = [action.data.sequence[stepIndex], action.data.sequence[stepIndex + 1]];
    markBuilderDirty("Reordered continuous sequence step");
  }
  await previewBuilderDraft();
}

function coerceActionFieldValue(kind, value) {
  if (value === "") {
    return "";
  }
  if (kind === "integer") {
    return Number.parseInt(value, 10);
  }
  if (kind === "duration" || kind === "number") {
    return Number.parseFloat(value);
  }
  if (kind === "key_list") {
    return String(value)
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }
  return value;
}

function setNestedObjectValue(target, path, value) {
  const parts = String(path || "").split(".");
  let current = target;
  for (let index = 0; index < parts.length - 1; index += 1) {
    const key = parts[index];
    const nextKey = parts[index + 1];
    const numericNextKey = Number.parseInt(nextKey || "", 10);
    if (Array.isArray(current)) {
      current = current[Number.parseInt(key, 10)];
      continue;
    }
    if (!(key in current) || current[key] === null || current[key] === undefined) {
      current[key] = Number.isInteger(numericNextKey) ? [] : {};
    }
    current = current[key];
  }
  const finalKey = parts[parts.length - 1];
  if (Array.isArray(current)) {
    current[Number.parseInt(finalKey, 10)] = value;
  } else {
    current[finalKey] = value;
  }
}

function mergeMissingDefaults(target, defaults) {
  for (const [key, value] of Object.entries(defaults || {})) {
    if (target[key] === undefined) {
      target[key] = cloneValue(value);
    }
  }
}

async function updateBuilderActionField(target) {
  const selectedState = builderSelectedState();
  if (!selectedState) {
    return;
  }
  const actionIndex = Number(target.dataset.actionIndex || "-1");
  const fieldName = target.dataset.fieldName;
  const fieldKind = target.dataset.fieldKind || "string";
  const action = selectedState.actions[actionIndex];
  if (!action || !fieldName) {
    return;
  }
  const nextValue = coerceActionFieldValue(fieldKind, target.value);
  const nestedPath = target.dataset.nestedPath || "";
  if (nestedPath) {
    if (nextValue === "" || Number.isNaN(nextValue)) {
      setNestedObjectValue(action.data, nestedPath, fieldKind === "key_list" ? [] : "");
    } else {
      setNestedObjectValue(action.data, nestedPath, nextValue);
    }
    if (action.type === "start_continuous_input" && fieldKind === "continuous_step_action") {
      const sequenceMatch = nestedPath.match(/^sequence\.(\d+)\.action$/);
      if (sequenceMatch) {
        const stepIndex = Number.parseInt(sequenceMatch[1], 10);
        const defaults = defaultContinuousStep(String(nextValue || "press_key"));
        action.data.sequence[stepIndex] = {
          ...defaults,
          ...action.data.sequence[stepIndex],
          action: defaults.action,
          run_for_seconds: action.data.sequence[stepIndex]?.run_for_seconds ?? defaults.run_for_seconds,
        };
      }
    }
  } else {
    if (nextValue === "" || Number.isNaN(nextValue)) {
      delete action.data[fieldName];
    } else {
      action.data[fieldName] = nextValue;
    }
    if (action.type === "start_continuous_input" && fieldName === "action") {
      const nextActionType = String(nextValue || "press_key");
      if (nextActionType === "sequence") {
        action.data.sequence = Array.isArray(action.data.sequence) && action.data.sequence.length
          ? action.data.sequence
          : [defaultContinuousStep("press_key")];
      } else {
        delete action.data.sequence;
        mergeMissingDefaults(action.data, defaultActionData("start_continuous_input"));
        mergeMissingDefaults(
          action.data,
          defaultContinuousStep(nextActionType),
        );
        action.data.action = nextActionType;
      }
    }
  }
  markBuilderDirty(`Updated ${action.label || action.type}`);
  await previewBuilderDraft();
}

async function reorderBuilderActions(fromIndex, toIndex) {
  const selectedState = builderSelectedState();
  if (!selectedState || fromIndex === toIndex || fromIndex < 0 || toIndex < 0) {
    return;
  }
  const [moved] = selectedState.actions.splice(fromIndex, 1);
  selectedState.actions.splice(toIndex, 0, moved);
  markBuilderDirty("Reordered action");
  await previewBuilderDraft();
}

function slugifySegment(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function setNestedValue(target, path, value) {
  const parts = path.split(".");
  let current = target;
  for (let index = 0; index < parts.length - 1; index += 1) {
    current = current[parts[index]];
  }
  current[parts[parts.length - 1]] = value;
}

async function updateBuilderSetting(target) {
  const profile = getBuilderProfile();
  if (!profile) {
    return;
  }
  const field = target.dataset.builderField;
  const kind = target.dataset.builderKind || "string";
  if (!field) {
    return;
  }
  if (field === "notes") {
    state.builderWorkingNotes = target.value;
    markBuilderDirty("Updated pack notes");
    await previewBuilderDraft();
    return;
  }
  let nextValue;
  if (target instanceof HTMLInputElement && target.type === "checkbox") {
    nextValue = target.checked;
  } else if (field === "profile_pack.known_limitations") {
    nextValue = target.value
      .split(/\r?\n/)
      .map((item) => item.trim())
      .filter(Boolean);
  } else {
    nextValue = coerceActionFieldValue(kind, target.value);
  }
  if (nextValue === "" && field !== "target.process_name" && field !== "target.window_title_contains") {
    nextValue = "";
  }
  setNestedValue(profile, field, nextValue);
  markBuilderDirty(`Updated ${humanizeBuilderKey(field.split(".").at(-1))}`);
  await previewBuilderDraft();
}

function findStateIndex(profile, stateName) {
  return (profile?.states || []).findIndex((item) => item.name === stateName);
}

function replaceStateReferences(profile, previousName, nextName) {
  if (!profile || !previousName || !nextName || previousName === nextName) {
    return;
  }
  if (profile.initial_state === previousName) {
    profile.initial_state = nextName;
  }
  for (const stateItem of profile.states || []) {
    if (stateItem.on_success === previousName) {
      stateItem.on_success = nextName;
    }
    if (stateItem.on_failure === previousName) {
      stateItem.on_failure = nextName;
    }
    for (const action of stateItem.actions || []) {
      if (action.type === "wait_for_state" && action.data?.state === previousName) {
        action.data.state = nextName;
      }
    }
  }
}

function clearDeletedStateReferences(profile, deletedName, fallbackName = "") {
  if (!profile || !deletedName) {
    return;
  }
  if (profile.initial_state === deletedName) {
    profile.initial_state = fallbackName;
  }
  for (const stateItem of profile.states || []) {
    if (stateItem.on_success === deletedName) {
      stateItem.on_success = fallbackName || null;
    }
    if (stateItem.on_failure === deletedName) {
      stateItem.on_failure = "graceful_termination";
    }
    for (const action of stateItem.actions || []) {
      if (action.type === "wait_for_state" && action.data?.state === deletedName) {
        action.data.state = fallbackName || "";
      }
    }
  }
}

async function updateBuilderStateSetting(target) {
  const profile = getBuilderProfile();
  const selectedState = builderSelectedState();
  if (!profile || !selectedState) {
    return;
  }
  const field = target.dataset.builderField;
  if (!field) {
    return;
  }
  if (field === "state.terminal") {
    selectedState.terminal = Boolean(target.checked);
    if (!selectedState.terminal && selectedState.result) {
      selectedState.result = null;
    }
    markBuilderDirty("Updated terminal state");
    await previewBuilderDraft();
    return;
  }
  if (field === "state.name") {
    const nextName = target.value.trim();
    if (!nextName || nextName === selectedState.name) {
      return;
    }
    if ((profile.states || []).some((item) => item.name === nextName)) {
      setBuilderStatus(`State ${nextName} already exists`, "bad");
      renderBuilderToolbar();
      target.value = selectedState.name;
      return;
    }
    const previousName = selectedState.name;
    selectedState.name = nextName;
    replaceStateReferences(profile, previousName, nextName);
    state.selectedBuilderStateName = nextName;
    markBuilderDirty(`Renamed state ${previousName} to ${nextName}`);
    await previewBuilderDraft();
    return;
  }
  if (field === "state.on_success") {
    selectedState.on_success = target.value || null;
    markBuilderDirty("Updated success transition");
    await previewBuilderDraft();
    return;
  }
  if (field === "state.on_failure") {
    selectedState.on_failure = target.value || "graceful_termination";
    markBuilderDirty("Updated failure transition");
    await previewBuilderDraft();
    return;
  }
  if (field === "state.result") {
    selectedState.result = target.value || null;
    if (selectedState.result && !selectedState.terminal) {
      selectedState.terminal = true;
    }
    markBuilderDirty("Updated terminal result");
    await previewBuilderDraft();
  }
}

function defaultStatePayload(name) {
  return {
    name,
    required_anchors: [],
    optional_anchors: [],
    forbidden_anchors: [],
    actions: [],
    on_success: null,
    on_failure: "graceful_termination",
    terminal: false,
    result: null,
  };
}

async function addBuilderState() {
  const profile = getBuilderProfile();
  const rawName = $("builder-new-state-name").value.trim();
  const stateName = rawName || `state_${(profile?.states || []).length + 1}`;
  if (!profile) {
    return;
  }
  if ((profile.states || []).some((item) => item.name === stateName)) {
    setBuilderStatus(`State ${stateName} already exists`, "bad");
    renderBuilderToolbar();
    return;
  }
  profile.states.push(defaultStatePayload(stateName));
  if (!profile.initial_state) {
    profile.initial_state = stateName;
  }
  state.selectedBuilderStateName = stateName;
  $("builder-new-state-name").value = "";
  markBuilderDirty(`Added state ${stateName}`);
  await previewBuilderDraft();
}

async function setBuilderInitialState() {
  const profile = getBuilderProfile();
  const selectedState = builderSelectedState();
  if (!profile || !selectedState) {
    return;
  }
  profile.initial_state = selectedState.name;
  markBuilderDirty(`Set initial state to ${selectedState.name}`);
  await previewBuilderDraft();
}

async function deleteBuilderState() {
  const profile = getBuilderProfile();
  const selectedState = builderSelectedState();
  if (!profile || !selectedState || (profile.states || []).length <= 1) {
    return;
  }
  const deletedName = selectedState.name;
  profile.states = (profile.states || []).filter((item) => item.name !== deletedName);
  const fallbackName = profile.states[0]?.name || "";
  clearDeletedStateReferences(profile, deletedName, fallbackName);
  state.selectedBuilderStateName = fallbackName || null;
  markBuilderDirty(`Deleted state ${deletedName}`);
  await previewBuilderDraft();
}

async function runBuilderPackCheck() {
  if (!state.selectedProfileId) {
    return;
  }
  setBuilderStatus("Running pack checks...", "warn");
  renderBuilderToolbar();
  const result = await api(`/api/profiles/${encodeURIComponent(state.selectedProfileId)}/check-pack`, {
    method: "POST",
  });
  state.builderDraft = state.builderDraft
    ? { ...state.builderDraft, pack_check: result }
    : state.builderDraft;
  setBuilderStatus(
    result.ok ? "Pack checks passed" : "Pack checks reported blockers",
    result.ok ? (result.warnings?.length ? "warn" : "good") : "bad",
  );
  renderBuilder();
}

async function scaffoldBuilderPack() {
  const game = state.builderScaffoldDraft.game.trim();
  const mode = state.builderScaffoldDraft.mode.trim();
  const gameSlug = (state.builderScaffoldDraft.game_slug || slugifySegment(game)).trim();
  const packSlug = (state.builderScaffoldDraft.pack_slug || slugifySegment(mode)).trim();
  if (!game || !mode || !gameSlug || !packSlug) {
    state.builderScaffoldStatus = "Game, mode, and both slug fields are required";
    state.builderScaffoldTone = "bad";
    renderBuilderScaffold();
    return;
  }
  state.builderScaffoldStatus = "Creating pack scaffold...";
  state.builderScaffoldTone = "warn";
  renderBuilderScaffold();
  const result = await api("/api/scaffold-pack", {
    method: "POST",
    body: JSON.stringify({
      game,
      mode,
      game_slug: gameSlug,
      pack_slug: packSlug,
    }),
  });
  state.builderScaffoldDraft = { game: "", mode: "", game_slug: "", pack_slug: "" };
  state.builderScaffoldStatus = `Created ${result.profile_id}`;
  state.builderScaffoldTone = "good";
  await refreshProfiles({ refreshReadinessAfter: true });
  await selectProfile(result.profile_id, { autoDryRun: false });
  setActiveView("builder");
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
$("operate-tab").addEventListener("click", () => setActiveView("operate"));
$("builder-tab").addEventListener("click", async () => {
  setActiveView("builder");
  await refreshBuilderSchema();
  await refreshBuilderDraft({ force: true });
  if (!state.builderPreview) {
    await refreshBuilderPreviewSnapshot();
  }
});
$("builder-state-select").addEventListener("change", (event) => {
  state.selectedBuilderStateName = event.target.value || null;
  renderBuilderActionPalette();
  renderBuilderStateEditor();
  renderBuilderStateDetail();
});
$("builder-add-action-button").addEventListener("click", async () => {
  await addBuilderAction();
});
$("builder-validate-button").addEventListener("click", async () => {
  await previewBuilderDraft();
});
$("builder-check-pack-button").addEventListener("click", async () => {
  await runBuilderPackCheck();
});
$("builder-revert-button").addEventListener("click", async () => {
  await revertBuilderDraft();
});
$("builder-save-button").addEventListener("click", async () => {
  await saveBuilderDraft();
});
$("builder-add-state-button").addEventListener("click", async () => {
  await addBuilderState();
});
$("builder-set-initial-button").addEventListener("click", async () => {
  await setBuilderInitialState();
});
$("builder-delete-state-button").addEventListener("click", async () => {
  await deleteBuilderState();
});
$("builder-preview-refresh-button").addEventListener("click", async () => {
  await refreshBuilderPreviewSnapshot();
});
$("builder-region-save-button").addEventListener("click", async () => {
  await saveBuilderRegionFromDraw();
});
$("builder-region-remove-button").addEventListener("click", async () => {
  await removeSelectedBuilderRegion();
});
$("builder-anchor-save-button").addEventListener("click", async () => {
  await saveBuilderAnchor();
});
$("builder-anchor-crop-button").addEventListener("click", async () => {
  await cropBuilderTemplateAnchor();
});
$("builder-view").addEventListener("input", (event) => {
  if (!(event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement || event.target instanceof HTMLSelectElement)) {
    return;
  }
  if (event.target.dataset.builderSection !== "scaffold") {
    return;
  }
  const field = event.target.dataset.builderField;
  if (!field) {
    return;
  }
  state.builderScaffoldDraft[field] = event.target.value;
  renderBuilderScaffold();
});
$("builder-view").addEventListener("change", async (event) => {
  if (!(event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement || event.target instanceof HTMLSelectElement)) {
    return;
  }
  if (event.target.dataset.builderSection === "state") {
    await updateBuilderStateSetting(event.target);
    return;
  }
  if (event.target.dataset.builderSection === "profile") {
    await updateBuilderSetting(event.target);
    return;
  }
  if (event.target.dataset.builderSection !== "scaffold") {
    return;
  }
  const field = event.target.dataset.builderField;
  if (!field) {
    return;
  }
  state.builderScaffoldDraft[field] = event.target.value;
  renderBuilderScaffold();
});
$("builder-view").addEventListener("click", async (event) => {
  if (!(event.target instanceof Element)) {
    return;
  }
  const regionButton = event.target.closest("[data-builder-region-select]");
  if (regionButton) {
    const regionName = regionButton.dataset.builderRegionSelect;
    const region = (getBuilderProfile()?.regions || []).find((item) => item.name === regionName);
    state.selectedBuilderRegionName = regionName || null;
    $("builder-region-name").value = regionName || "";
    state.builderDrawRect = region
      ? { x: region.x, y: region.y, width: region.width, height: region.height }
      : state.builderDrawRect;
    renderBuilderVisualTools();
    return;
  }
  const removeAnchorButton = event.target.closest("[data-builder-anchor-remove]");
  if (removeAnchorButton) {
    const [bucketKey, indexText] = String(removeAnchorButton.dataset.builderAnchorRemove || "").split(":");
    await removeBuilderAnchor(bucketKey, Number(indexText || "-1"));
    return;
  }
  const button = event.target.closest("#builder-scaffold-button");
  if (!button) {
    return;
  }
  await scaffoldBuilderPack();
});
$("builder-preview-overlay").addEventListener("mousedown", (event) => {
  if (!(event.target instanceof Element)) {
    return;
  }
  const point = pointerToPreviewPoint(event);
  if (!point) {
    return;
  }
  state.builderDragStart = point;
  state.builderDrawRect = { x: point.x, y: point.y, width: 0, height: 0 };
  renderBuilderVisualTools();
});
$("builder-preview-overlay").addEventListener("mousemove", (event) => {
  if (!state.builderDragStart) {
    return;
  }
  updateBuilderDrawRect(pointerToPreviewPoint(event));
});
window.addEventListener("mouseup", (event) => {
  if (!state.builderDragStart) {
    return;
  }
  updateBuilderDrawRect(pointerToPreviewPoint(event));
  state.builderDragStart = null;
});
$("builder-graph").addEventListener("click", (event) => {
  if (!(event.target instanceof Element)) {
    return;
  }
  const button = event.target.closest("button[data-state-name]");
  if (!button) {
    return;
  }
  state.selectedBuilderStateName = button.dataset.stateName;
  renderBuilderStateSelect();
  renderBuilderActionPalette();
  renderBuilderStateEditor();
  renderBuilderStateDetail();
});
$("builder-state-detail").addEventListener("click", async (event) => {
  if (!(event.target instanceof Element)) {
    return;
  }
  const sequenceButton = event.target.closest("[data-sequence-command]");
  if (sequenceButton) {
    await handleSequenceCommand(
      sequenceButton.dataset.sequenceCommand,
      Number(sequenceButton.dataset.actionIndex || "-1"),
      Number(sequenceButton.dataset.stepIndex || "-1"),
    );
    return;
  }
  const button = event.target.closest("button[data-action-command]");
  if (!button) {
    return;
  }
  await handleBuilderActionCommand(
    button.dataset.actionCommand,
    Number(button.dataset.actionIndex || "-1"),
  );
});
$("builder-state-detail").addEventListener("change", async (event) => {
  if (!(event.target instanceof HTMLInputElement || event.target instanceof HTMLSelectElement)) {
    return;
  }
  if (!event.target.dataset.fieldName) {
    return;
  }
  await updateBuilderActionField(event.target);
});
$("builder-state-detail").addEventListener("dragstart", (event) => {
  if (!(event.target instanceof Element)) {
    return;
  }
  const item = event.target.closest("[data-action-index]");
  if (!item) {
    return;
  }
  state.builderDrag = {
    stateName: item.dataset.stateName || "",
    actionIndex: Number(item.dataset.actionIndex || "-1"),
  };
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = "move";
  }
});
$("builder-state-detail").addEventListener("dragover", (event) => {
  if (!(event.target instanceof Element) || !state.builderDrag) {
    return;
  }
  const item = event.target.closest("[data-action-index]");
  if (!item) {
    return;
  }
  event.preventDefault();
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = "move";
  }
});
$("builder-state-detail").addEventListener("drop", async (event) => {
  if (!(event.target instanceof Element) || !state.builderDrag) {
    return;
  }
  const item = event.target.closest("[data-action-index]");
  if (!item || item.dataset.stateName !== state.builderDrag.stateName) {
    return;
  }
  event.preventDefault();
  const fromIndex = Number(state.builderDrag.actionIndex || "-1");
  const toIndex = Number(item.dataset.actionIndex || "-1");
  state.builderDrag = null;
  await reorderBuilderActions(fromIndex, toIndex);
});
$("builder-state-detail").addEventListener("dragend", () => {
  state.builderDrag = null;
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

refreshProfiles().then(async () => {
  await refreshBuilderSchema();
  await refreshRuns();
  if (state.selectedProfileId) {
    await selectProfile(state.selectedProfileId, {
      autoDryRun: true,
      skipInitialReadiness: true,
    });
  } else {
    renderBuilder();
  }
});
scheduleNextPoll();
setActiveView("operate");

const sidebarToggle = $("sidebar-toggle");

if (sidebarToggle) {
  const isCollapsed = localStorage.getItem("sidebar-collapsed") === "true";
  if (isCollapsed) {
    document.body.classList.add("sidebar-collapsed");
  }

  sidebarToggle.addEventListener("click", () => {
    const collapsed = document.body.classList.toggle("sidebar-collapsed");
    localStorage.setItem("sidebar-collapsed", collapsed);
  });
}
