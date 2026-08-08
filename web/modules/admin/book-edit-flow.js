import { populateBookNarrators } from "./book-narrator-selector.js";
import { readBookConfigForm } from "./book-form-data.js";
import { submitBookEdit } from "./book-config-submit.js";
import { setPreImportFields, bindPreImportModal } from "./book-modal.js";

export function openEditExistingBookModal(book, onUpdated = () => {}) {
  const modal = document.getElementById("modal-pre-import");
  if (!modal) return;
  const modalTitle = document.getElementById("modal-pre-import-title");
  const modalSubtitle = document.getElementById("pre-import-subtitle");
  const confirmBtn = document.getElementById("btn-confirm-pre-import");
  const regenContainer = document.getElementById("pre-import-regenerate-container");
  const regenCheck = document.getElementById("pre-import-regenerate-check");
  const generateAudiosContainer = document.getElementById("pre-import-generate-audios-container");
  if (modalTitle) modalTitle.textContent = `✏️ Editar Librojuego: ${book.title}`;
  if (modalSubtitle) modalSubtitle.textContent = "Edita los metadatos del libro o regenera sus audios con la voz seleccionada:";
  if (confirmBtn) confirmBtn.textContent = "Guardar Cambios 💾";
  if (regenContainer) regenContainer.classList.remove("hidden");
  if (regenCheck) regenCheck.checked = false;
  if (generateAudiosContainer) generateAudiosContainer.classList.add("hidden");

  setPreImportFields({
    editBookId: book.book_id,
    title: book.title,
    author: book.author,
    language: book.language,
    startNode: book.start_node,
    tierId: book.tier_id,
  });
  const refreshNarrators = () => populateBookNarrators(
    document.getElementById("pre-import-voice-select"),
    document.getElementById("pre-import-language").value,
    book.narrator_id || null,
  );
  refreshNarrators();
  document.getElementById("pre-import-language").onchange = refreshNarrators;
  bindPreImportModal(() => submitEditConfig(onUpdated));
  modal.classList.add("open");
}

async function submitEditConfig(onUpdated) {
  const config = readBookConfigForm();
  const errorBox = document.getElementById("pre-import-error");
  const zone = document.getElementById("book-upload-zone");
  const progress = document.getElementById("upload-progress");
  const progressMsg = document.getElementById("upload-progress-msg");
  if (zone) zone.classList.add("hidden");
  if (progress) progress.classList.remove("hidden");
  if (progressMsg) {
    progressMsg.textContent = config.regenCheck
      ? `Actualizando metadatos y regenerando audios TTS para '${config.title}'... Por favor espera unos minutos.`
      : `Guardando cambios para '${config.title}'...`;
  }
  try {
    const data = await submitBookEdit(config);
    alert(`✅ ¡Éxito! ${data.message || "Libro actualizado correctamente."}`);
    await onUpdated();
  } catch (error) {
    if (errorBox) {
      errorBox.classList.remove("hidden");
      errorBox.textContent = error.message;
    } else {
      alert(`❌ Error al actualizar: ${error.message}`);
    }
    throw error;
  } finally {
    if (zone) zone.classList.remove("hidden");
    if (progress) progress.classList.add("hidden");
  }
}
