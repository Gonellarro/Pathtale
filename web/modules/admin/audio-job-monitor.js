import { fetchAdminAudioJob } from "./books-api.js";

const POLL_INTERVAL_MS = 1_000;

function delay(milliseconds) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

export async function waitForAudioJob(job, onProgress) {
  let current = job;
  while (true) {
    onProgress(current);
    if (current.state === "completed") return current;
    if (current.state === "failed") throw new Error(current.error || "La generación de audios ha fallado.");

    await delay(POLL_INTERVAL_MS);
    const response = await fetchAdminAudioJob(current.job_id);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || "No se pudo consultar el progreso de los audios.");
    current = payload.job;
  }
}
