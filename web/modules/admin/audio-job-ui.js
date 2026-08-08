const STATUS_IDS = {
  container: "pre-import-audio-job-status",
  title: "pre-import-audio-job-title",
  count: "pre-import-audio-job-count",
  progress: "pre-import-audio-job-progress",
  current: "pre-import-audio-job-current",
};

function getElements() {
  return Object.fromEntries(Object.entries(STATUS_IDS).map(([key, id]) => [key, document.getElementById(id)]));
}

function setFormBusy(isBusy) {
  const form = document.getElementById("form-pre-import");
  if (!form) return;
  form.querySelectorAll("input:not([type='hidden']), select, #btn-confirm-pre-import").forEach((element) => {
    element.disabled = isBusy;
  });
}

function jobDetail(job) {
  if (job.current_item) return `Procesando ${job.current_item}`;
  if (job.state === "queued") return "El libro se ha importado. La cola de audio comenzará enseguida.";
  if (job.state === "completed") return "Todos los audios se han generado correctamente.";
  return "Preparando las secciones y los audios del libro…";
}

export function resetAudioJobStatus() {
  const { container, title, count, progress, current } = getElements();
  if (container) container.classList.add("hidden");
  if (title) title.textContent = "Preparando la generación de audio";
  if (count) count.textContent = "En cola";
  if (progress) progress.style.width = "0%";
  if (current) current.textContent = "El libro se ha importado. La cola de audio comenzará enseguida.";
  setFormBusy(false);
}

export function renderAudioJobStatus(job, action = "Generando audios") {
  const { container, title, count, progress, current } = getElements();
  const total = Number(job.total) || 0;
  const completed = Number(job.completed) || 0;
  const isQueued = job.state === "queued";
  const percentage = total ? Math.min(100, (completed / total) * 100) : 0;

  if (container) container.classList.remove("hidden");
  if (title) title.textContent = isQueued ? `${action}: en cola` : action;
  if (count) count.textContent = total ? `${completed}/${total}` : "Preparando…";
  if (progress) progress.style.width = `${percentage}%`;
  if (current) current.textContent = jobDetail(job);
  setFormBusy(job.state === "queued" || job.state === "running");
}

export function showAudioJobFailure(message) {
  const { container, title, current } = getElements();
  if (container) container.classList.remove("hidden");
  if (title) title.textContent = "No se pudieron generar los audios";
  if (current) current.textContent = message;
  setFormBusy(false);
}
