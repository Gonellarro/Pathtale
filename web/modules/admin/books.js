import { authFetch, escapeHtml, API_BASE } from "../state.js";
import { openAdminBookTierModal } from "./users.js";

export let currentAdminBooks = [];

export async function loadAdminBooks() {
  const container = document.getElementById("admin-books-table-wrap");
  const countLbl = document.getElementById("admin-books-count");
  if (!container) return;

  try {
    const res = await authFetch(`${API_BASE}/api/admin/books`);
    const data = await res.json();
    const books = data.books || [];
    currentAdminBooks = books;

    if (countLbl) countLbl.textContent = `Total: ${books.length} libro${books.length === 1 ? '' : 's'}`;

    container.innerHTML = `
      <table class="library-table">
        <thead>
          <tr>
            <th>Portada</th>
            <th>Título</th>
            <th>Narrador</th>
            <th>Nivel Tier</th>
            <th>Estado</th>
            <th>Secciones</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          ${books.map(b => {
            const isVisible = b.is_visible !== 0;
            const cleanNarrator = escapeHtml((b.narrator_name || 'DaveFX').replace(/\s*\(.*?\)/g, "").trim());
            return `
            <tr>
              <td class="td-thumb">
                ${b.cover_image 
                  ? `<img src="/api/books/${b.book_id}/asset/${b.cover_image}?v=${Date.now()}" alt="${escapeHtml(b.title)}" class="table-thumb-img">`
                  : `📜`}
              </td>
              <td class="td-title">
                <a href="#" class="admin-book-title-link" data-id="${b.book_id}" style="color:var(--accent-gold); text-decoration:none; font-weight:bold;">${escapeHtml(b.title)}</a>
                <br><small style="color:var(--text-muted)">ID: ${b.book_id}</small>
              </td>
              <td class="td-narrator" style="font-weight:500;">${cleanNarrator}</td>
              <td>
                <span class="admin-badge admin-badge-tier">
                  🔒 ${escapeHtml(b.tier_name || 'Demo Gratuita')}
                </span>
              </td>
              <td>
                <button class="btn-secondary btn-sm btn-toggle-visible-book" data-id="${b.book_id}" data-visible="${isVisible ? '1' : '0'}" style="color:${isVisible ? 'var(--success)' : '#ef4444'}">
                  ${isVisible ? '👁️ Visible' : '🙈 Oculto'}
                </button>
              </td>
              <td>${b.total_sections || 0} caps.</td>
              <td class="td-actions">
                <button class="btn-secondary btn-sm btn-tier-book" data-id="${b.book_id}" data-title="${escapeHtml(b.title)}" data-tier="${b.tier_id || 1}">🏷️ Tier</button>
                <button class="btn-secondary btn-sm btn-delete-book" data-id="${b.book_id}" style="color: #ff6b6b">🗑️</button>
              </td>
            </tr>
          `;
          }).join("")}
        </tbody>
      </table>
    `;

    const openEditForBookId = (bid) => {
      const bObj = currentAdminBooks.find(item => item.book_id === bid);
      if (bObj) {
        openEditExistingBookModal(bObj);
      }
    };

    container.querySelectorAll(".admin-book-title-link").forEach(link => {
      link.onclick = (e) => {
        e.preventDefault();
        openEditForBookId(link.getAttribute("data-id"));
      };
    });

    container.querySelectorAll(".btn-toggle-visible-book").forEach(btn => {
      btn.onclick = async () => {
        const bid = btn.getAttribute("data-id");
        const currentVis = btn.getAttribute("data-visible") === "1";
        try {
          const res = await authFetch(`${API_BASE}/api/admin/books/${bid}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ is_visible: !currentVis })
          });
          if (res.ok) {
            loadAdminBooks();
          }
        } catch (err) {
          console.error("Error toggling book visibility:", err);
        }
      };
    });

    container.querySelectorAll(".btn-tier-book").forEach(btn => {
      btn.onclick = () => {
        const bid = btn.getAttribute("data-id");
        const btitle = btn.getAttribute("data-title");
        const btier = btn.getAttribute("data-tier");
        openAdminBookTierModal(bid, btitle, btier);
      };
    });

    container.querySelectorAll(".btn-delete-book").forEach(btn => {
      btn.onclick = () => {
        const bid = btn.getAttribute("data-id");
        if (confirm(`¿Eliminar el libro '${bid}' del catálogo?`)) {
          deleteBook(bid);
        }
      };
    });
  } catch (err) {
    console.error("Error loading admin books:", err);
  }
}

async function deleteBook(bookId) {
  try {
    const res = await authFetch(`${API_BASE}/api/admin/books/${bookId}`, { method: "DELETE" });
    if (res.ok) loadAdminBooks();
  } catch (err) {
    alert("Error al eliminar libro.");
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
  if (ext !== 'epub' && ext !== 'pdf') {
    alert("Por favor, selecciona un archivo .epub o .pdf válido.");
    return;
  }

  if (zone) zone.classList.add("hidden");
  if (progress) progress.classList.remove("hidden");
  if (progressMsg) progressMsg.textContent = `Analizando archivo '${file.name}'...`;

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await authFetch(`${API_BASE}/api/admin/books/inspect`, {
      method: "POST",
      body: formData
    });

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

  if (modalTitle) modalTitle.textContent = `✨ Configuración de Importación del Librojuego`;
  if (modalSubtitle) modalSubtitle.textContent = `Archivo analizado correctamente. Revisa y ajusta los metadatos y la voz antes de iniciar la sintetización:`;
  if (confirmBtn) confirmBtn.textContent = `Confirmar e Importar Libro 🚀`;
  if (regenContainer) regenContainer.classList.add("hidden");

  document.getElementById("pre-import-temp-id").value = tempFileId || "";
  document.getElementById("pre-import-edit-book-id").value = "";
  document.getElementById("pre-import-title").value = inspection.suggested_title || filename;
  document.getElementById("pre-import-author").value = inspection.suggested_author || "Desconocido";
  document.getElementById("pre-import-language").value = inspection.suggested_language || "es";
  document.getElementById("pre-import-start-node").value = inspection.suggested_start_node || "sec_001";
  document.getElementById("pre-import-tier").value = "1";
  const coverInput = document.getElementById("pre-import-cover-file");
  if (coverInput) coverInput.value = "";

  const updateVoiceOptions = async () => {
    const lang = document.getElementById("pre-import-language").value;
    const voiceSelect = document.getElementById("pre-import-voice-select");
    if (!voiceSelect) return;

    try {
      const res = await authFetch(`${API_BASE}/api/admin/narrators`);
      const data = await res.json();
      const narrators = data.narrators || [];
      const filtered = narrators.filter(n => !n.language || n.language.toLowerCase().startsWith(lang.toLowerCase()));
      const listToUse = filtered.length > 0 ? filtered : narrators;

      voiceSelect.innerHTML = listToUse.map(n => {
        const engineTag = n.engine_name || (n.engine_code ? n.engine_code.toUpperCase() : 'TTS');
        const valStr = `${n.narrator_id}:${n.engine_code || 'piper'}:${n.voice_code}`;
        return `<option value="${valStr}" data-narrator-id="${n.narrator_id}">${escapeHtml(n.display_name)} (${engineTag})</option>`;
      }).join("");
    } catch (err) {
      console.warn("Could not fetch DB narrators for dropdown:", err);
    }
  };

  updateVoiceOptions();
  document.getElementById("pre-import-language").onchange = updateVoiceOptions;

  const btnClose = document.getElementById("btn-close-modal-pre-import");
  const btnCancel = document.getElementById("btn-cancel-pre-import");
  const form = document.getElementById("form-pre-import");

  const closeModal = () => modal.classList.remove("open");
  if (btnClose) btnClose.onclick = closeModal;
  if (btnCancel) btnCancel.onclick = closeModal;

  if (form) {
    form.onsubmit = async (e) => {
      e.preventDefault();
      await submitBookConfigForm();
      closeModal();
    };
  }

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

  if (modalTitle) modalTitle.textContent = `✏️ Editar Librojuego: ${book.title}`;
  if (modalSubtitle) modalSubtitle.textContent = `Edita los metadatos del libro o regenera sus audios con la voz seleccionada:`;
  if (confirmBtn) confirmBtn.textContent = `Guardar Cambios 💾`;
  if (regenContainer) regenContainer.classList.remove("hidden");
  if (regenCheck) regenCheck.checked = false;

  document.getElementById("pre-import-temp-id").value = "";
  document.getElementById("pre-import-edit-book-id").value = book.book_id || "";
  document.getElementById("pre-import-title").value = book.title || "";
  document.getElementById("pre-import-author").value = book.author || "";
  document.getElementById("pre-import-language").value = book.language || "es";
  document.getElementById("pre-import-start-node").value = book.start_node || "sec_001";
  document.getElementById("pre-import-tier").value = book.tier_id || "1";
  const coverInput = document.getElementById("pre-import-cover-file");
  if (coverInput) coverInput.value = "";

  const updateVoiceOptions = async () => {
    const lang = document.getElementById("pre-import-language").value;
    const voiceSelect = document.getElementById("pre-import-voice-select");
    if (!voiceSelect) return;

    try {
      const res = await authFetch(`${API_BASE}/api/admin/narrators`);
      const data = await res.json();
      const narrators = data.narrators || [];
      const filtered = narrators.filter(n => !n.language || n.language.toLowerCase().startsWith(lang.toLowerCase()));
      const listToUse = filtered.length > 0 ? filtered : narrators;

      voiceSelect.innerHTML = listToUse.map(n => {
        const engineTag = n.engine_name || (n.engine_code ? n.engine_code.toUpperCase() : 'TTS');
        const valStr = `${n.narrator_id}:${n.engine_code || 'piper'}:${n.voice_code}`;
        return `<option value="${valStr}" data-narrator-id="${n.narrator_id}">${escapeHtml(n.display_name)} (${engineTag})</option>`;
      }).join("");

      if (book && book.narrator_id) {
        const matchingOpt = Array.from(voiceSelect.options).find(opt => opt.getAttribute("data-narrator-id") == book.narrator_id);
        if (matchingOpt) matchingOpt.selected = true;
      }
    } catch (err) {
      console.warn("Could not fetch DB narrators for dropdown:", err);
    }
  };

  updateVoiceOptions();
  document.getElementById("pre-import-language").onchange = updateVoiceOptions;

  const btnClose = document.getElementById("btn-close-modal-pre-import");
  const btnCancel = document.getElementById("btn-cancel-pre-import");
  const form = document.getElementById("form-pre-import");

  const closeModal = () => modal.classList.remove("open");
  if (btnClose) btnClose.onclick = closeModal;
  if (btnCancel) btnCancel.onclick = closeModal;

  if (form) {
    form.onsubmit = async (e) => {
      e.preventDefault();
      await submitBookConfigForm();
      closeModal();
    };
  }

  modal.classList.add("open");
}

async function submitBookConfigForm() {
  const editBookId = document.getElementById("pre-import-edit-book-id").value;
  const tempFileId = document.getElementById("pre-import-temp-id").value;
  const title = document.getElementById("pre-import-title").value.trim();
  const author = document.getElementById("pre-import-author").value.trim();
  const language = document.getElementById("pre-import-language").value;
  const startNode = document.getElementById("pre-import-start-node").value.trim();
  const voiceSelectEl = document.getElementById("pre-import-voice-select");
  const selectedOpt = voiceSelectEl ? voiceSelectEl.selectedOptions[0] : null;
  const narratorId = selectedOpt ? parseInt(selectedOpt.getAttribute("data-narrator-id") || "1") : 1;
  const voiceValue = voiceSelectEl ? voiceSelectEl.value : "";
  let ttsEngine = "auto";
  let voiceName = "default";
  if (voiceValue.includes(":")) {
    const parts = voiceValue.split(":");
    ttsEngine = parts[1] || "auto";
    voiceName = parts[2] || "default";
  }

  const zone = document.getElementById("book-upload-zone");
  const progress = document.getElementById("upload-progress");
  const progressMsg = document.getElementById("upload-progress-msg");

  if (editBookId) {
    if (zone) zone.classList.add("hidden");
    if (progress) progress.classList.remove("hidden");
    if (progressMsg) {
      progressMsg.textContent = regenCheck
        ? `Actualizando metadatos y regenerando audios TTS para '${title}' con voz '${voiceName}'... Por favor espera unos minutos.`
        : `Guardando cambios para '${title}'...`;
    }

    try {
      const res = await authFetch(`${API_BASE}/api/admin/books/${editBookId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          author,
          language,
          start_node: startNode,
          narrator_id: narratorId,
          tier_id: tierId,
          tts_engine: ttsEngine,
          voice_name: voiceName,
          regenerate_audios: regenCheck
        })
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Error al actualizar libro.");

      if (coverFile) {
        if (progressMsg) progressMsg.textContent = `Subiendo nueva portada para '${title}'...`;
        const formData = new FormData();
        formData.append("file", coverFile);
        const resCover = await authFetch(`${API_BASE}/api/admin/books/${editBookId}/cover`, {
          method: "POST",
          body: formData
        });
        if (!resCover.ok) {
          const errCover = await resCover.json();
          alert(`⚠️ Libro actualizado pero hubo un problema al subir la portada: ${errCover.detail}`);
        }
      }

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
    if (progressMsg) progressMsg.textContent = `Importando y sintetizando audios TTS para '${title}' con voz '${voiceName}'... Por favor espera unos minutos.`;

    try {
      const res = await authFetch(`${API_BASE}/api/admin/books/confirm_import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          temp_file_id: tempFileId,
          title,
          author,
          language,
          narrator_id: narratorId,
          tts_engine: ttsEngine,
          voice_name: voiceName,
          start_node: startNode,
          tier_id: tierId,
          generate_audios: true
        })
      });
      const data = await res.json();

      if (!res.ok) throw new Error(data.detail || "Error al importar libro");

      const createdBookId = data.book_id;
      if (createdBookId && coverFile) {
        if (progressMsg) progressMsg.textContent = `Subiendo portada personalizada para '${title}'...`;
        const formData = new FormData();
        formData.append("file", coverFile);
        const resCover = await authFetch(`${API_BASE}/api/admin/books/${createdBookId}/cover`, {
          method: "POST",
          body: formData
        });
        if (!resCover.ok) {
          const errCover = await resCover.json();
          alert(`⚠️ Libro importado pero hubo un problema al subir la portada: ${errCover.detail}`);
        }
      }

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
    const res = await authFetch(`${API_BASE}/api/admin/books/${bookId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title,
        author,
        language,
        start_node: startNode,
        narrator_id: narratorId,
        tier_id: tierId
      })
    });
    if (!res.ok) throw new Error("Error al guardar cambios de metadatos.");

    if (synthesizeAudios) {
      alert(`🎙️ Iniciando sintetización de audios para '${title}' (${language})...`);
      authFetch(`${API_BASE}/api/books/${bookId}/regenerate_audios`, { method: "POST" });
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
