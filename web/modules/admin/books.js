import { openAdminBookTierModal } from "./book-tier-modal.js";
import { fetchAdminBooks, updateAdminBook, deleteAdminBook, inspectAdminBook, regenerateBookAudios } from "./books-api.js";
import { populateBookNarrators } from "./book-narrator-selector.js";
import { readBookConfigForm } from "./book-form-data.js";
import { submitBookEdit, submitBookImport } from "./book-config-submit.js";
import { setPreImportFields, bindPreImportModal } from "./book-modal.js";
import { renderAdminBooksList } from "./books-list.js";

export let currentAdminBooks = [];

export async function loadAdminBooks() {
  const container = document.getElementById("admin-books-table-wrap");
  const countLbl = document.getElementById("admin-books-count");
  if (!container) return;

  try {
    const res = await fetchAdminBooks();
    const data = await res.json();
    const books = data.books || [];
    currentAdminBooks = books;

    if (countLbl) countLbl.textContent = `Total: ${books.length} libro${books.length === 1 ? '' : 's'}`;

    renderAdminBooksList(container, books, {
      onEdit: (bookId) => {
        const book = currentAdminBooks.find((item) => item.book_id === bookId);
        if (book) openEditExistingBookModal(book);
      },
      onToggle: async (bookId, visible) => {
        try {
          const response = await updateAdminBook(bookId, { is_visible: !visible });
          if (response.ok) loadAdminBooks();
        } catch (error) { console.error("Error toggling book visibility:", error); }
      },
      onTier: (bookId, title, tier) => openAdminBookTierModal(bookId, title, tier),
      onDelete: (bookId, isHidden) => {
        if (isHidden) {
          const warning = `El libro '${bookId}' ya está oculto.\n\nLa siguiente acción lo eliminará definitivamente de la base de datos y del disco. Esta operación no se puede deshacer.\n\n¿Continuar?`;
          if (confirm(warning)) deleteBook(bookId, true);
          return;
        }
        if (confirm(`¿Ocultar el libro '${bookId}' del catálogo?`)) deleteBook(bookId, false);
      },
    });
  } catch (err) {
    console.error("Error loading admin books:", err);
  }
}

async function deleteBook(bookId, hard = false) {
  try {
    const res = await deleteAdminBook(bookId, hard);
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || "operación no permitida");
    }
    loadAdminBooks();
  } catch (err) {
    alert(`Error al eliminar libro: ${err.message || "operación no permitida"}`);
  }
}

export function initAdminUploadZone() {
  const zone = document.getElementById("book-upload-zone");
  const input = document.getElementById("input-book-upload");
  const progress = document.getElementById("upload-progress");
  const progressMsg = document.getElementById("upload-progress-msg");

  if (!zone || !input) return;

  zone.onclick = () => input.click();

  zone.ondragover = (e) => {
    e.preventDefault();
    zone.classList.add("dragover");
  };

  zone.ondragleave = () => zone.classList.remove("dragover");

  zone.ondrop = (e) => {
    e.preventDefault();
    zone.classList.remove("dragover");
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleEpubUpload(e.dataTransfer.files[0]);
    }
  };

  input.onchange = () => {
    if (input.files && input.files[0]) {
      handleEpubUpload(input.files[0]);
    }
  };
}

async function handleEpubUpload(file) {
  const zone = document.getElementById("book-upload-zone");
  const progress = document.getElementById("upload-progress");
  const progressMsg = document.getElementById("upload-progress-msg");

  const ext = file.name.split('.').pop().toLowerCase();
  if (ext !== 'epub') {
    alert("Por favor, selecciona un EPUB normalizado (.epub) válido.");
    return;
  }

  if (zone) zone.classList.add("hidden");
  if (progress) progress.classList.remove("hidden");
  if (progressMsg) progressMsg.textContent = `Analizando archivo '${file.name}'...`;

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await inspectAdminBook(formData);

    const data = await res.json();
    if (res.ok) {
      openPreImportModal(data.temp_file_id, data.filename, data.inspection);
    } else {
      alert(`❌ Error al analizar el archivo: ${data.detail || "Error desconocido"}`);
    }
  } catch (err) {
    alert(`❌ Error de comunicación: ${err.message}`);
  } finally {
    if (zone) zone.classList.remove("hidden");
    if (progress) progress.classList.add("hidden");
  }
}

export function openPreImportModal(tempFileId, filename, inspection) {
  const modal = document.getElementById("modal-pre-import");
  if (!modal) return;

  const modalTitle = document.getElementById("modal-pre-import-title");
  const modalSubtitle = document.getElementById("pre-import-subtitle");
  const confirmBtn = document.getElementById("btn-confirm-pre-import");
  const regenContainer = document.getElementById("pre-import-regenerate-container");
  const generateAudiosContainer = document.getElementById("pre-import-generate-audios-container");
  const generateAudiosCheck = document.getElementById("pre-import-generate-audios-check");

  if (modalTitle) modalTitle.textContent = `✨ Configuración de Importación del Librojuego`;
  if (modalSubtitle) modalSubtitle.textContent = `Archivo analizado correctamente. Revisa y ajusta los metadatos y la voz antes de iniciar la sintetización:`;
  if (confirmBtn) confirmBtn.textContent = `Confirmar e Importar Libro 🚀`;
  if (regenContainer) regenContainer.classList.add("hidden");
  if (generateAudiosContainer) generateAudiosContainer.classList.remove("hidden");
  if (generateAudiosCheck) generateAudiosCheck.checked = false;

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

  bindPreImportModal(submitBookConfigForm);

  modal.classList.add("open");
}

export function openEditExistingBookModal(book) {
  const modal = document.getElementById("modal-pre-import");
  if (!modal) return;

  const modalTitle = document.getElementById("modal-pre-import-title");
  const modalSubtitle = document.getElementById("pre-import-subtitle");
  const confirmBtn = document.getElementById("btn-confirm-pre-import");
  const regenContainer = document.getElementById("pre-import-regenerate-container");
  const regenCheck = document.getElementById("pre-import-regenerate-check");
  const generateAudiosContainer = document.getElementById("pre-import-generate-audios-container");

  if (modalTitle) modalTitle.textContent = `✏️ Editar Librojuego: ${book.title}`;
  if (modalSubtitle) modalSubtitle.textContent = `Edita los metadatos del libro o regenera sus audios con la voz seleccionada:`;
  if (confirmBtn) confirmBtn.textContent = `Guardar Cambios 💾`;
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

  bindPreImportModal(submitBookConfigForm);

  modal.classList.add("open");
}

async function submitBookConfigForm() {
  const config = readBookConfigForm();
  const { editBookId, title, regenCheck, generateAudios } = config;
  const errDiv = document.getElementById("pre-import-error");

  const zone = document.getElementById("book-upload-zone");
  const progress = document.getElementById("upload-progress");
  const progressMsg = document.getElementById("upload-progress-msg");

  if (editBookId) {
    if (zone) zone.classList.add("hidden");
    if (progress) progress.classList.remove("hidden");
    if (progressMsg) {
        progressMsg.textContent = regenCheck
        ? `Actualizando metadatos y regenerando audios TTS para '${title}'... Por favor espera unos minutos.`
        : `Guardando cambios para '${title}'...`;
    }

    try {
      const data = await submitBookEdit(config);

      alert(`✅ ¡Éxito! ${data.message || "Libro actualizado correctamente."}`);
      loadAdminBooks();
    } catch (err) {
      if (errDiv) {
        errDiv.classList.remove("hidden");
        errDiv.textContent = err.message;
      } else {
        alert(`❌ Error al actualizar: ${err.message}`);
      }
    } finally {
      if (zone) zone.classList.remove("hidden");
      if (progress) progress.classList.add("hidden");
    }
  } else {
    if (zone) zone.classList.add("hidden");
    if (progress) progress.classList.remove("hidden");
    if (progressMsg) {
        progressMsg.textContent = generateAudios
        ? `Importando y sintetizando audios TTS para '${title}'... Por favor espera unos minutos.`
        : `Importando la estructura y los contenidos de '${title}' sin generar audios...`;
    }

    try {
      const data = await submitBookImport(config);

      alert(`✅ ¡Éxito! ${data.message}`);
      loadAdminBooks();
    } catch (err) {
      if (errDiv) {
        errDiv.classList.remove("hidden");
        errDiv.textContent = err.message;
      } else {
        alert(`❌ Error al importar: ${err.message}`);
      }
    } finally {
      if (zone) zone.classList.remove("hidden");
      if (progress) progress.classList.add("hidden");
    }
  }
}

export function openPostUploadModal(book) {
  const modal = document.getElementById("modal-post-upload");
  if (!modal) return;

  document.getElementById("post-upload-book-id").value = book.book_id || "";
  document.getElementById("post-upload-title").value = book.title || "";
  document.getElementById("post-upload-author").value = book.author || "";
  document.getElementById("post-upload-language").value = book.language || "es";
  document.getElementById("post-upload-start-node").value = book.start_node || "sec_001";
  document.getElementById("post-upload-narrator").value = book.narrator_id || "1";
  document.getElementById("post-upload-tier").value = book.tier_id || "1";

  initPostUploadModalEvents();
  modal.classList.add("open");
}

let isPostUploadModalEventsBound = false;
function initPostUploadModalEvents() {
  if (isPostUploadModalEventsBound) return;
  isPostUploadModalEventsBound = true;

  const modal = document.getElementById("modal-post-upload");
  const btnClose = document.getElementById("btn-close-modal-post-upload");
  const btnCancel = document.getElementById("btn-cancel-post-upload");
  const form = document.getElementById("form-post-upload");

  const closeModal = () => modal.classList.remove("open");
  if (btnClose) btnClose.onclick = closeModal;
  if (btnCancel) btnCancel.onclick = async () => {
    await savePostUploadMetadata(false);
    closeModal();
  };

  if (form) {
    form.onsubmit = async (e) => {
      e.preventDefault();
      await savePostUploadMetadata(true);
      closeModal();
    };
  }
}

async function savePostUploadMetadata(synthesizeAudios = false) {
  const bookId = document.getElementById("post-upload-book-id").value;
  const title = document.getElementById("post-upload-title").value.trim();
  const author = document.getElementById("post-upload-author").value.trim();
  const language = document.getElementById("post-upload-language").value;
  const startNode = document.getElementById("post-upload-start-node").value.trim();
  const narratorId = parseInt(document.getElementById("post-upload-narrator").value);
  const tierId = parseInt(document.getElementById("post-upload-tier").value);
  const errDiv = document.getElementById("post-upload-error");

  try {
    const res = await updateAdminBook(bookId, {
        title,
        author,
        language,
        start_node: startNode,
        narrator_id: narratorId,
        tier_id: tierId
    });
    if (!res.ok) throw new Error("Error al guardar cambios de metadatos.");

    if (synthesizeAudios) {
      alert(`🎙️ Iniciando sintetización de audios para '${title}' (${language})...`);
      regenerateBookAudios(bookId);
    } else {
      alert("✅ Metadatos guardados correctamente.");
    }
    loadAdminBooks();
  } catch (err) {
    if (errDiv) {
      errDiv.classList.remove("hidden");
      errDiv.textContent = err.message;
    }
  }
}
