const form = document.querySelector("#runForm");
const runBtn = document.querySelector("#runBtn");
const cancelBtn = document.querySelector("#cancelBtn");
const resetBtn = document.querySelector("#resetBtn");
const advancedToggle = document.querySelector("#advancedToggle");
const commandPreview = document.querySelector("#commandPreview");
const jobStatus = document.querySelector("#jobStatus");
const logBox = document.querySelector("#logBox");
const outputPath = document.querySelector("#outputPath");
const openOutputBtn = document.querySelector("#openOutputBtn");
const progressBar = document.querySelector("#progressBar");
const progressLabel = document.querySelector("#progressLabel");
const elapsedLabel = document.querySelector("#elapsedLabel");

const fields = [
  "topic",
  "limit",
  "source",
  "start_year",
  "end_year",
  "degree",
  "region",
  "university",
  "output_file",
];

let pollTimer = null;
let elapsedTimer = null;
let elapsedStartedAt = null;
let elapsedFrozen = null;

function payloadFromForm() {
  const data = new FormData(form);
  const payload = {};
  fields.forEach((field) => {
    payload[field] = (data.get(field) || "").toString().trim();
  });
  payload.headless = data.get("headless") === "on";
  payload.allow_missing_summary = data.get("allow_missing_summary") === "on";
  payload.no_detail_browser_fallback = data.get("no_detail_browser_fallback") === "on";
  return payload;
}

function buildPreview(payload) {
  const parts = [
    "python",
    "cli.py",
    "--source",
    payload.source || "browser-export",
    "--topic",
    quote(payload.topic || "pobreza"),
    "--limit",
    payload.limit || "300",
    "--no-interactive",
  ];
  addOptional(parts, "--start-year", payload.start_year);
  addOptional(parts, "--end-year", payload.end_year);
  addOptional(parts, "--degree", payload.degree);
  addOptional(parts, "--region", payload.region);
  addOptional(parts, "--university", payload.university);
  addOptional(parts, "--output-file", payload.output_file);
  if (payload.headless) parts.push("--headless");
  if (payload.allow_missing_summary) parts.push("--allow-missing-summary");
  if (payload.no_detail_browser_fallback) parts.push("--no-detail-browser-fallback");
  return parts.join(" ");
}

function addOptional(parts, flag, value) {
  if (value) {
    parts.push(flag, quote(value));
  }
}

function quote(value) {
  return /\s/.test(value) ? `"${value}"` : value;
}

function refreshPreview() {
  commandPreview.textContent = buildPreview(payloadFromForm());
}

async function startRun(event) {
  event.preventDefault();
  if (runBtn.disabled) return;
  const payload = payloadFromForm();
  setRunning(true);
  logBox.textContent = "Iniciando corrida...\n";
  outputPath.textContent = "Pendiente";
  openOutputBtn.disabled = true;
  resetProgress();
  try {
    const response = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "No se pudo iniciar.");
    schedulePoll(0);
  } catch (error) {
    setStatus("failed");
    logBox.textContent = `ERROR: ${error.message}`;
    setRunning(false);
  }
}

async function cancelRun() {
  cancelBtn.disabled = true;
  try {
    const response = await fetch("/api/jobs/cancel", { method: "POST" });
    if (!response.ok && response.status !== 409) {
      const result = await response.json().catch(() => ({}));
      throw new Error(result.error || "No se pudo cancelar.");
    }
  } catch (error) {
    logBox.textContent += `\nERROR cancelando: ${error.message}`;
  } finally {
    cancelBtn.disabled = false;
  }
}

async function openOutput() {
  openOutputBtn.disabled = true;
  try {
    const response = await fetch("/api/open-output", { method: "POST" });
    if (!response.ok) {
      const result = await response.json().catch(() => ({}));
      throw new Error(result.error || "No se pudo abrir el archivo.");
    }
  } catch (error) {
    logBox.textContent += `\nERROR abriendo Excel: ${error.message}`;
  } finally {
    openOutputBtn.disabled = !outputPath.dataset.ready;
  }
}

function schedulePoll(delay) {
  clearTimeout(pollTimer);
  pollTimer = setTimeout(pollJob, delay);
}

async function pollJob() {
  try {
    const response = await fetch("/api/jobs/current");
    const job = await response.json();
    renderJob(job);
    if (job.status === "running") {
      schedulePoll(1200);
    } else {
      setRunning(false);
      stopElapsed(job.finished_at, job.started_at);
    }
  } catch (error) {
    setStatus("failed");
    logBox.textContent += `\nERROR consultando estado: ${error.message}`;
    setRunning(false);
  }
}

function renderJob(job) {
  setStatus(job.status || "idle");
  const logs = Array.isArray(job.logs) ? job.logs.join("\n") : "Sin corrida activa.";
  logBox.textContent = logs || "Sin corrida activa.";
  logBox.scrollTop = logBox.scrollHeight;

  const path = job.output_path || "";
  outputPath.textContent = path || "Pendiente";
  if (path) {
    outputPath.dataset.ready = "1";
    openOutputBtn.disabled = false;
  } else {
    delete outputPath.dataset.ready;
    openOutputBtn.disabled = true;
  }

  const progress = job.progress || { current: 0, total: 0 };
  updateProgress(progress.current, progress.total);

  if (job.status === "running" && job.started_at && !elapsedStartedAt) {
    startElapsed(job.started_at);
  }
}

function setStatus(status) {
  jobStatus.textContent = status;
  jobStatus.className = `status-pill ${status}`;
}

function setRunning(isRunning) {
  runBtn.disabled = isRunning;
  cancelBtn.hidden = !isRunning;
  cancelBtn.disabled = false;
}

function resetProgress() {
  updateProgress(0, Number(document.querySelector("#limit").value) || 0);
  startElapsed(Date.now() / 1000);
}

function updateProgress(current, total) {
  const safeTotal = total > 0 ? total : 0;
  const safeCurrent = Math.min(Math.max(current, 0), safeTotal || current);
  progressLabel.textContent = `${safeCurrent} / ${safeTotal || "?"}`;
  const pct = safeTotal > 0 ? Math.min(100, (safeCurrent / safeTotal) * 100) : 0;
  progressBar.style.width = `${pct}%`;
}

function startElapsed(startedAt) {
  stopElapsed();
  elapsedStartedAt = startedAt;
  elapsedTimer = setInterval(() => {
    const seconds = Math.max(0, Date.now() / 1000 - elapsedStartedAt);
    elapsedLabel.textContent = formatElapsed(seconds);
  }, 500);
}

function stopElapsed(finishedAt, startedAt) {
  if (elapsedTimer) {
    clearInterval(elapsedTimer);
    elapsedTimer = null;
  }
  if (finishedAt && startedAt) {
    elapsedFrozen = finishedAt - startedAt;
    elapsedLabel.textContent = formatElapsed(elapsedFrozen);
  }
  elapsedStartedAt = null;
}

function formatElapsed(seconds) {
  const m = Math.floor(seconds / 60).toString().padStart(2, "0");
  const s = Math.floor(seconds % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

function resetForm() {
  form.reset();
  document.querySelector("#topic").value = "pobreza";
  document.querySelector("#limit").value = "300";
  refreshPreview();
}

function applyAdvancedMode() {
  const on = advancedToggle.checked;
  document.body.classList.toggle("advanced-on", on);
  try {
    localStorage.setItem("renati.advanced", on ? "1" : "0");
  } catch (_) {
    /* ignore */
  }
}

function restoreAdvancedMode() {
  let stored = "0";
  try {
    stored = localStorage.getItem("renati.advanced") || "0";
  } catch (_) {
    /* ignore */
  }
  advancedToggle.checked = stored === "1";
  applyAdvancedMode();
}

form.addEventListener("input", refreshPreview);
form.addEventListener("change", refreshPreview);
form.addEventListener("submit", startRun);
form.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    event.preventDefault();
    form.requestSubmit();
  }
});
resetBtn.addEventListener("click", resetForm);
cancelBtn.addEventListener("click", cancelRun);
openOutputBtn.addEventListener("click", openOutput);
advancedToggle.addEventListener("change", applyAdvancedMode);

restoreAdvancedMode();
refreshPreview();
pollJob();
