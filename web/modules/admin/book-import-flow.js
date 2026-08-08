import { inspectAdminBook } from "./books-api.js";
import { populateBookNarrators } from "./book-narrator-selector.js";
import { readBookConfigForm } from "./book-form-data.js";
import { submitBookImport } from "./book-config-submit.js";
import { setPreImportFields, bindPreImportModal } from "./book-modal.js";
import { waitForAudioJob } from "./audio-job-monitor.js";

export function initAdminUploadZone(onImported) {
  const zone = document.getElementById("book-upload-zone");
  const input = document.getElementById("input-book-upload");
  if (!zone || !input) return;

  zone.onclick = () => input.click();
  zone.ondragover = (event) => {
    event.preventDefault();
    zone.classList.add("dragover");
  };
  zone.ondragleave = () => zone.classList.remove("dragover");
  zone.ondrop = (event) => {
    event.preventDefault();
    zone.classList.remove("dragover");
    if (event.dataTransfer.files?.[0]) handleEpubUpload(event.dataTransfer.files[0], onImported);
  };
  input.onchange = () => {
    if (input.files?.[0]) handleEpubUpload(input.files[0], onImported);
  };
}

async function handleEpubUpload(file, onImported) {
  const zone = document.getElementById("book-upload-zone");
  const progress = document.getElementById("upload-progress");
  const progressMsg = document.getElementById("upload-progress-msg");
  if (file.name.split(".").pop()?.toLowerCase() !== "epub") {
    alert("Por favor, selecciona un EPUB normalizado (.epub) válido.");
    return;
  }

  if (zone) zone.classList.add("hidden");
  if (progress) progress.classList.remove("hidden");
  if (progressMsg) progressMsg.textContent = `Analizando archivo '${file.name}'...`;
  const formData = new FormData();
  formData.append("file", file);
  try {
    const response = await inspectAdminBook(formData);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Error desconocido");
    openPreImportModal(data.temp_file_id, data.filename, data.inspection, onImported);
  } catch (error) {
    alert(`❌ Error al analizar el archivo: ${error.message}`);
  } finally {
    if (zone) zone.classList.remove("hidden");
    if (progress) progress.classList.add("hidden");
  }
}

export function openPreImportModal(tempFileId, filename, inspection, onImported = () => {}) {
  const modal = document.getElementById("modal-pre-import");
  if (!modal) return;

  const modalTitle = document.getElementById("modal-pre-import-title");
  const modalSubtitle = document.getElementById("pre-import-subtitle");
  const confirmBtn = document.getElementById("btn-confirm-pre-import");
  const regenContainer = document.getElementById("pre-import-regenerate-container");
  const generateAudiosContainer = document.getElementById("pre-import-generate-audios-container");
  const generateAudiosCheck = document.getElementById("pre-import-generate-audios-check");
  const errorBox = document.getElementById("pre-import-error");
  if (modalTitle) modalTitle.textContent = "✨ Configuración de Importación del Librojuego";
  if (modalSubtitle) modalSubtitle.textContent = "Archivo analizado correctamente. Revisa y ajusta los metadatos y la voz antes de iniciar la sintetización:";
  if (confirmBtn) confirmBtn.textContent = "Confirmar e Importar Libro 🚀";
  if (regenContainer) regenContainer.classList.add("hidden");
  if (generateAudiosContainer) generateAudiosContainer.classList.remove("hidden");
  if (generateAudiosCheck) generateAudiosCheck.checked = false;
  if (errorBox) {
    errorBox.classList.add("hidden");
    errorBox.textContent = "";
  }

  setPreImportFields({
    tempFileId,
    title: inspection.suggested_title || filename,
    author: inspection.suggested_author || "Desconocido",
    language: inspection.suggested_language || "es",
    startNode: inspection.suggested_start_node || "sec_001",
    tierId: "1",
  });
  const refreshNarrators = () => populateBookNarrators(
    document.getElementById("pre-import-voice-select"),
    document.getElementById("pre-import-language").value,
  );
  refreshNarrators();
  document.getElementById("pre-import-language").onchange = refreshNarrators;
  bindPreImportModal(() => submitImportConfig(onImported));
  modal.classList.add("open");
}

async function submitImportConfig(onImported) {
  const config = readBookConfigForm();
  const errorBox = document.getElementById("pre-import-error");
  const zone = document.getElementById("book-upload-zone");
  const progress = document.getElementById("upload-progress");
  const progressMsg = document.getElementById("upload-progress-msg");
  if (zone) zone.classList.add("hidden");
  if (progress) progress.classList.remove("hidden");
  if (progressMsg) {
    progressMsg.textContent = config.generateAudios
      ? `Importando y sintetizando audios TTS para '${config.title}'... Por favor espera unos minutos.`
      : `Importando la estructura y los contenidos de '${config.title}' sin generar audios...`;
  }
  try {
    const data = await submitBookImport(config);
    if (data.audio_job) {
      await waitForAudioJob(data.audio_job, (job) => {
        if (!progressMsg) return;
        const total = job.total || "…";
        const current = job.current_item ? ` · ${job.current_item}` : "";
        progressMsg.textContent = `Generando audios: ${job.completed}/${total}${current}`;
      });
      alert(`✅ ¡Éxito! ${data.message} Audios generados.`);
    } else {
      alert(`✅ ¡Éxito! ${data.message}`);
    }
    await onImported();
  } catch (error) {
    if (errorBox) {
      errorBox.classList.remove("hidden");
      errorBox.textContent = error.message;
    } else {
      alert(`❌ Error al importar: ${error.message}`);
    }
    throw error;
  } finally {
    if (zone) zone.classList.remove("hidden");
    if (progress) progress.classList.add("hidden");
  }
}
