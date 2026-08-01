/**
 * Admin Module for PathTale Dashboard
 * Manages Users CRUD, EPUB Book Imports & Metadata, Narrators, and Audit Logs.
 */

import { state, authFetch, escapeHtml, formatTimeAgo, API_BASE } from "./state.js";

let currentAdminBooks = [];

export async function loadAdminDashboard() {
  const role = state.currentUser ? (state.currentUser.role || state.currentUser.role_name) : null;
  if (!state.currentUser || role !== "admin") {
    console.warn("loadAdminDashboard: Current user is not admin", state.currentUser);
    return;
  }

  initAdminTabs();
  initAdminUploadZone();
  await Promise.all([
    loadAdminUsers(),
    loadAdminBooks(),
    loadAdminNarrators(),
    loadAdminLogs()
  ]);
}

function initAdminTabs() {
  const tabs = document.querySelectorAll(".admin-tab");
  tabs.forEach(tab => {
    tab.onclick = () => {
      tabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");

      const targetTab = tab.getAttribute("data-tab");
      document.querySelectorAll(".admin-panel").forEach(p => p.classList.add("hidden"));

      const activePanel = document.getElementById(`admin-panel-${targetTab}`);
      if (activePanel) {
        activePanel.classList.remove("hidden");
        activePanel.classList.add("active");
      }
    };
  });
}

// --- Users Management ---

let adminUsersCache = [];
let isAdminUserModalEventsBound = false;

export async function loadAdminUsers() {
  const container = document.getElementById("admin-users-table-wrap");
  const countLbl = document.getElementById("admin-users-count");
  if (!container) return;

  try {
    const res = await authFetch(`${API_BASE}/api/admin/users`);
    const data = await res.json();
    adminUsersCache = data.users || [];
    const users = adminUsersCache;

    if (countLbl) countLbl.textContent = `Total: ${users.length} usuario${users.length === 1 ? '' : 's'}`;

    container.innerHTML = `
      <table class="library-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Usuario</th>
            <th>Nombre</th>
            <th>Rol</th>
            <th>Plan / Tier</th>
            <th>Fecha Registro</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          ${users.map(u => `
            <tr>
              <td>#${u.user_id}</td>
              <td><strong>${escapeHtml(u.username)}</strong></td>
              <td>${escapeHtml(u.first_name || '-')}</td>
              <td>
                <span class="admin-badge ${u.role === 'admin' ? 'admin-badge-admin' : 'admin-badge-user'}">
                  ${u.role === 'admin' ? '⚡ ADMIN' : 'USER'}
                </span>
              </td>
              <td>
                <span class="admin-badge admin-badge-tier">
                  💳 ${escapeHtml(u.tier_name || 'Demo Gratuita')}
                </span>
              </td>
              <td>${formatTimeAgo(u.created_at)}</td>
              <td class="td-actions">
                <button class="btn-secondary btn-sm btn-edit-user" data-id="${u.user_id}">✏️ Editar</button>
                ${u.user_id !== 1 ? `<button class="btn-secondary btn-sm btn-delete-user" data-id="${u.user_id}" style="color: #ff6b6b">🗑️</button>` : ''}
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;

    // Bind edit/delete buttons
    container.querySelectorAll(".btn-edit-user").forEach(btn => {
      btn.onclick = () => {
        const uid = parseInt(btn.getAttribute("data-id"));
        const targetUser = adminUsersCache.find(u => u.user_id === uid);
        if (targetUser) openAdminUserModal(targetUser);
      };
    });

    container.querySelectorAll(".btn-delete-user").forEach(btn => {
      btn.onclick = () => {
        const uid = btn.getAttribute("data-id");
        if (confirm(`¿Eliminar usuario ID #${uid}? Esta acción no se puede deshacer.`)) {
          deleteUser(uid);
        }
      };
    });

    const btnAdd = document.getElementById("btn-admin-add-user");
    if (btnAdd) {
      btnAdd.onclick = () => openAdminUserModal(null);
    }

    initAdminUserModalEvents();
  } catch (err) {
    console.error("Error loading admin users:", err);
  }
}

export async function loadAdminRoles(selectedRole = 'user') {
  const roleSelect = document.getElementById("admin-user-role");
  if (!roleSelect) return;

  try {
    const res = await authFetch(`${API_BASE}/api/admin/roles`);
    if (!res.ok) throw new Error("Error obteniendo roles");
    const data = await res.json();
    const roles = data.roles || [];

    if (roles.length > 0) {
      roleSelect.innerHTML = roles.map(r => {
        const isSel = r.name.toLowerCase() === (selectedRole || 'user').toLowerCase();
        const desc = r.description ? ` (${r.description})` : '';
        return `<option value="${escapeHtml(r.name)}" ${isSel ? 'selected' : ''}>${escapeHtml(r.name.toUpperCase())}${escapeHtml(desc)}</option>`;
      }).join('');
    }
  } catch (err) {
    console.error("Error loading DB roles:", err);
  }
}

async function openAdminUserModal(user = null) {
  const modal = document.getElementById("modal-admin-user");
  const titleText = document.getElementById("modal-admin-user-title-text");
  const userIdInput = document.getElementById("admin-user-id");
  const usernameInput = document.getElementById("admin-user-username");
  const nameInput = document.getElementById("admin-user-name");
  const roleSelect = document.getElementById("admin-user-role");
  const tierSelect = document.getElementById("admin-user-tier");
  const durationSelect = document.getElementById("admin-user-duration");
  const passInput = document.getElementById("admin-user-pass");
  const errDiv = document.getElementById("admin-user-error");

  if (!modal) return;

  if (errDiv) {
    errDiv.classList.add("hidden");
    errDiv.textContent = "";
  }

  const activeRole = user ? (user.role || user.role_name || "user") : "user";
  await loadAdminRoles(activeRole);

  if (user) {
    if (titleText) titleText.textContent = `Editar Usuario @${user.username}`;
    userIdInput.value = user.user_id;
    usernameInput.value = user.username;
    usernameInput.disabled = true;
    nameInput.value = user.first_name || "";
    if (roleSelect) roleSelect.value = activeRole;
    tierSelect.value = user.tier_id || "1";
    durationSelect.value = "0";
    passInput.value = "";
  } else {
    if (titleText) titleText.textContent = "Nuevo Usuario";
    userIdInput.value = "";
    usernameInput.value = "";
    usernameInput.disabled = false;
    nameInput.value = "";
    if (roleSelect) roleSelect.value = "user";
    tierSelect.value = "1";
    durationSelect.value = "0";
    passInput.value = "";
  }

  modal.classList.add("open");
}

function closeAdminUserModal() {
  const modal = document.getElementById("modal-admin-user");
  if (modal) modal.classList.remove("open");
}

function initAdminUserModalEvents() {
  if (isAdminUserModalEventsBound) return;
  isAdminUserModalEventsBound = true;

  const btnClose = document.getElementById("btn-close-modal-admin-user");
  const btnCancel = document.getElementById("btn-cancel-admin-user");
  const form = document.getElementById("form-admin-user");

  if (btnClose) btnClose.onclick = closeAdminUserModal;
  if (btnCancel) btnCancel.onclick = closeAdminUserModal;

  if (form) {
    form.onsubmit = async (e) => {
      e.preventDefault();
      const userId = document.getElementById("admin-user-id").value;
      const username = document.getElementById("admin-user-username").value.trim();
      const name = document.getElementById("admin-user-name").value.trim();
      const role = document.getElementById("admin-user-role").value;
      const tierId = parseInt(document.getElementById("admin-user-tier").value);
      const durationDays = parseInt(document.getElementById("admin-user-duration").value);
      const pass = document.getElementById("admin-user-pass").value.trim();
      const errDiv = document.getElementById("admin-user-error");

      if (errDiv) {
        errDiv.classList.add("hidden");
        errDiv.textContent = "";
      }

      try {
        if (userId) {
          // EDIT EXISTING USER
          const body = { first_name: name, role: role, tier_id: tierId };
          if (pass && pass.length >= 4) body.password = pass;

          const resUpdate = await authFetch(`${API_BASE}/api/admin/users/${userId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
          });

          if (!resUpdate.ok) {
            const errData = await resUpdate.json();
            throw new Error(errData.detail || "Error al actualizar datos del usuario.");
          }

          closeAdminUserModal();
          loadAdminUsers();
        } else {
          // CREATE NEW USER
          if (!username || !pass || pass.length < 4) {
            throw new Error("Nombre de usuario y contraseña (mín. 4 caracteres) son requeridos.");
          }

          const resCreate = await authFetch(`${API_BASE}/api/admin/users`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password: pass, first_name: name, role: role, tier_id: tierId })
          });

          const dataCreate = await resCreate.json();
          if (!resCreate.ok) {
            throw new Error(dataCreate.detail || "Error al crear el usuario.");
          }

          const newUserId = dataCreate.user.user_id;

          if (tierId > 1 || durationDays > 0) {
            await authFetch(`${API_BASE}/api/admin/users/${newUserId}/subscription`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ tier_id: tierId, duration_days: durationDays })
            });
          }

          closeAdminUserModal();
          loadAdminUsers();
        }
      } catch (err) {
        if (errDiv) {
          errDiv.textContent = `❌ ${err.message}`;
          errDiv.classList.remove("hidden");
        }
      }
    };
  }
}

async function deleteUser(userId) {
  try {
    const res = await authFetch(`${API_BASE}/api/admin/users/${userId}`, { method: "DELETE" });
    if (res.ok) loadAdminUsers();
  } catch (err) {
    alert("Error al eliminar usuario.");
  }
}

// --- Books & EPUB Upload Management ---

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
            <th>Autor</th>
            <th>Narrador</th>
            <th>Nivel Tier</th>
            <th>Estado</th>
            <th>Género / Serie</th>
            <th>Secciones</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          ${books.map(b => {
            const isVisible = b.is_visible !== 0;
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
              <td class="td-author">${escapeHtml(b.author || 'Desconocido')}</td>
              <td><span class="admin-badge admin-badge-narrator">🎙️ ${escapeHtml(b.narrator_name || 'DaveFX')}</span></td>
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
              <td class="td-genre">${escapeHtml(b.genre || b.series || '-')}</td>
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

    container.querySelectorAll(".btn-edit-book").forEach(btn => {
      btn.onclick = () => openEditForBookId(btn.getAttribute("data-id"));
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

let isAdminBookTierModalEventsBound = false;

function openAdminBookTierModal(bookId, bookTitle, currentTierId) {
  const modal = document.getElementById("modal-admin-book-tier");
  const title = document.getElementById("modal-admin-book-tier-title");
  const subtitle = document.getElementById("admin-book-tier-subtitle");
  const inputBookId = document.getElementById("admin-book-tier-id-input");
  const selectTier = document.getElementById("admin-book-tier-select");
  const errDiv = document.getElementById("admin-book-tier-error");

  if (!modal) return;

  if (errDiv) {
    errDiv.classList.add("hidden");
    errDiv.textContent = "";
  }

  title.textContent = `🏷️ Membresía Requerida`;
  if (subtitle) {
    subtitle.textContent = `Asigna el nivel de membresía mínimo necesario para que los usuarios puedan reproducir '${bookTitle}':`;
  }
  inputBookId.value = bookId;
  selectTier.value = currentTierId || "1";

  modal.classList.add("open");
  initAdminBookTierModalEvents();
}

function closeAdminBookTierModal() {
  const modal = document.getElementById("modal-admin-book-tier");
  if (modal) modal.classList.remove("open");
}

function initAdminBookTierModalEvents() {
  if (isAdminBookTierModalEventsBound) return;
  isAdminBookTierModalEventsBound = true;

  const btnClose = document.getElementById("btn-close-modal-admin-book-tier");
  const btnCancel = document.getElementById("btn-cancel-admin-book-tier");
  const form = document.getElementById("form-admin-book-tier");

  if (btnClose) btnClose.onclick = closeAdminBookTierModal;
  if (btnCancel) btnCancel.onclick = closeAdminBookTierModal;

  if (form) {
    form.onsubmit = async (e) => {
      e.preventDefault();
      const bookId = document.getElementById("admin-book-tier-id-input").value;
      const tierId = parseInt(document.getElementById("admin-book-tier-select").value);
      const errDiv = document.getElementById("admin-book-tier-error");

      if (errDiv) {
        errDiv.classList.add("hidden");
        errDiv.textContent = "";
      }

      try {
        const res = await authFetch(`${API_BASE}/api/admin/books/${bookId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ tier_id: tierId })
        });

        if (res.ok) {
          closeAdminBookTierModal();
          loadAdminBooks();
        } else {
          const data = await res.json();
          throw new Error(data.detail || "Error al actualizar el nivel del libro.");
        }
      } catch (err) {
        if (errDiv) {
          errDiv.textContent = `❌ ${err.message}`;
          errDiv.classList.remove("hidden");
        }
      }
    };
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

function initAdminUploadZone() {
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
  const fileName = file.name.toLowerCase();
  if (!fileName.endsWith(".epub") && !fileName.endsWith(".pdf")) {
    alert("❌ Error: El archivo debe ser de tipo .epub o .pdf");
    return;
  }

  const zone = document.getElementById("book-upload-zone");
  const progress = document.getElementById("upload-progress");
  const progressMsg = document.getElementById("upload-progress-msg");

  if (zone) zone.classList.add("hidden");
  if (progress) progress.classList.remove("hidden");
  if (progressMsg) progressMsg.textContent = `Analizando '${file.name}'... Por favor espera unos segundos.`;

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await authFetch(`${API_BASE}/api/admin/books/inspect`, {
      method: "POST",
      body: formData
    });
    const data = await res.json();

    if (res.ok && data.inspection) {
      openPreImportModal(data.temp_file_id, file.name, data.inspection);
    } else {
      alert(`❌ Error al analizar el libro: ${data.detail || "Respuesta inválida del servidor"}`);
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

  const updateVoiceOptions = () => {
    const lang = document.getElementById("pre-import-language").value;
    const voiceSelect = document.getElementById("pre-import-voice-select");
    if (!voiceSelect) return;

    if (lang === "en") {
      voiceSelect.innerHTML = `
        <option value="google:en-US-Neural2-F">Google Cloud Neural2 (Femenina - en-US-Neural2-F)</option>
        <option value="google:en-US-Neural2-D">Google Cloud Neural2 (Masculina - en-US-Neural2-D)</option>
        <option value="google:en-US-Wavenet-D">Google Cloud Wavenet (Masculina - en-US-Wavenet-D)</option>
        <option value="piper:en_US-lessac-medium.onnx">Piper Local C++ (Lessac - en_US)</option>
      `;
    } else {
      voiceSelect.innerHTML = `
        <option value="google:es-ES-Neural2-B">Google Cloud Neural2 (Masculina - es-ES-Neural2-B)</option>
        <option value="google:es-ES-Neural2-A">Google Cloud Neural2 (Femenina - es-ES-Neural2-A)</option>
        <option value="google:es-ES-Wavenet-C">Google Cloud Wavenet (Masculina - es-ES-Wavenet-C)</option>
        <option value="piper:es_ES-davefx-medium.onnx">Piper Local C++ (DaveFX - es_ES)</option>
      `;
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

  const updateVoiceOptions = () => {
    const lang = document.getElementById("pre-import-language").value;
    const voiceSelect = document.getElementById("pre-import-voice-select");
    if (!voiceSelect) return;

    if (lang === "en") {
      voiceSelect.innerHTML = `
        <option value="google:en-US-Neural2-F">Google Cloud Neural2 (Femenina - en-US-Neural2-F)</option>
        <option value="google:en-US-Neural2-D">Google Cloud Neural2 (Masculina - en-US-Neural2-D)</option>
        <option value="google:en-US-Wavenet-D">Google Cloud Wavenet (Masculina - en-US-Wavenet-D)</option>
        <option value="piper:en_US-lessac-medium.onnx">Piper Local C++ (Lessac - en_US)</option>
      `;
    } else {
      voiceSelect.innerHTML = `
        <option value="google:es-ES-Neural2-B">Google Cloud Neural2 (Masculina - es-ES-Neural2-B)</option>
        <option value="google:es-ES-Neural2-A">Google Cloud Neural2 (Femenina - es-ES-Neural2-A)</option>
        <option value="google:es-ES-Wavenet-C">Google Cloud Wavenet (Masculina - es-ES-Wavenet-C)</option>
        <option value="piper:es_ES-davefx-medium.onnx">Piper Local C++ (DaveFX - es_ES)</option>
      `;
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
  const voiceSelection = document.getElementById("pre-import-voice-select").value;
  const tierId = parseInt(document.getElementById("pre-import-tier").value);
  const regenCheck = document.getElementById("pre-import-regenerate-check")?.checked || false;
  const errDiv = document.getElementById("pre-import-error");

  let ttsEngine = "auto";
  let voiceName = "default";
  if (voiceSelection.startsWith("google:")) {
    ttsEngine = "google";
    voiceName = voiceSelection.replace("google:", "");
  } else if (voiceSelection.startsWith("piper:")) {
    ttsEngine = "piper";
    voiceName = voiceSelection.replace("piper:", "");
  }

  const zone = document.getElementById("book-upload-zone");
  const progress = document.getElementById("upload-progress");
  const progressMsg = document.getElementById("upload-progress-msg");

  if (editBookId) {
    // Mode: EDIT EXISTING BOOK
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
          tier_id: tierId,
          tts_engine: ttsEngine,
          voice_name: voiceName,
          regenerate_audios: regenCheck
        })
      });

      const data = await res.json();
      if (res.ok) {
        alert(`✅ ¡Éxito! ${data.message || "Libro actualizado correctamente."}`);
        loadAdminBooks();
      } else {
        throw new Error(data.detail || "Error al actualizar libro.");
      }
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
    // Mode: IMPORT NEW FILE
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
          tts_engine: ttsEngine,
          voice_name: voiceName,
          start_node: startNode,
          tier_id: tierId,
          generate_audios: true
        })
      });
      const data = await res.json();

      if (res.ok) {
        alert(`✅ ¡Éxito! ${data.message}`);
        loadAdminBooks();
      } else {
        throw new Error(data.detail || "Error al importar libro");
      }
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
  document.getElementById("post-upload-narrator").value = book.narrator_id || (book.language === "en" ? "2" : "1");
  document.getElementById("post-upload-tier").value = book.tier_id || "1";

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

  modal.classList.add("open");
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

// --- Narrators Management ---

export async function loadAdminNarrators() {
  const container = document.getElementById("admin-narrators-grid");
  const countLbl = document.getElementById("admin-narrators-count");
  if (!container) return;

  try {
    const res = await authFetch(`${API_BASE}/api/admin/narrators`);
    const data = await res.json();
    const narrators = data.narrators || [];

    if (countLbl) countLbl.textContent = `Total: ${narrators.length} narrador${narrators.length === 1 ? '' : 'es'}`;

    container.innerHTML = narrators.map(n => `
      <div class="narrator-card">
        <img src="${n.avatar_url}" alt="${escapeHtml(n.name)}" class="narrator-avatar">
        <div class="narrator-info">
          <h3 class="narrator-name">${escapeHtml(n.display_name || n.name)}</h3>
          <p class="narrator-specialty">${escapeHtml(n.specialty || '-')}</p>
          <p class="narrator-stories-count">🎧 ${n.story_count || 0} historia${n.story_count === 1 ? '' : 's'}</p>
        </div>
        <button class="btn-secondary btn-sm btn-delete-narrator" data-id="${n.narrator_id}" style="color:#ff6b6b">🗑️</button>
      </div>
    `).join("");

    container.querySelectorAll(".btn-delete-narrator").forEach(btn => {
      btn.onclick = (e) => {
        e.stopPropagation();
        const nid = btn.getAttribute("data-id");
        if (confirm(`¿Eliminar narrador ID #${nid}?`)) {
          deleteNarrator(nid);
        }
      };
    });

    const btnAdd = document.getElementById("btn-admin-add-narrator");
    if (btnAdd) {
      btnAdd.onclick = () => promptCreateNarrator();
    }
  } catch (err) {
    console.error("Error loading admin narrators:", err);
  }
}

async function promptCreateNarrator() {
  const name = prompt("Identificador técnico (ej: Carmen):");
  if (!name) return;
  const displayName = prompt("Nombre visible (ej: CARMEN DELGADO):") || name.toUpperCase();
  const specialty = prompt("Especialidad / Idioma (ej: Español · Drama):") || "Español · General";
  const avatarUrl = prompt("URL de la imagen de avatar:", "/assets/narrator_davefx.jpg");

  try {
    const res = await authFetch(`${API_BASE}/api/admin/narrators`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        display_name: displayName,
        specialty,
        avatar_url: avatarUrl
      })
    });
    if (res.ok) loadAdminNarrators();
  } catch (err) {
    alert("Error al crear narrador.");
  }
}

async function deleteNarrator(narratorId) {
  try {
    const res = await authFetch(`${API_BASE}/api/admin/narrators/${narratorId}`, { method: "DELETE" });
    const data = await res.json();
    if (res.ok) {
      loadAdminNarrators();
    } else {
      alert(`❌ ${data.detail}`);
    }
  } catch (err) {
    alert("Error al eliminar narrador.");
  }
}

// --- Audit & Reading Logs ---

export async function loadAdminLogs() {
  const container = document.getElementById("admin-logs-table-wrap");
  const countLbl = document.getElementById("admin-logs-count");
  if (!container) return;

  try {
    const res = await authFetch(`${API_BASE}/api/admin/logs?limit=100`);
    const data = await res.json();
    const logs = data.logs || [];

    if (countLbl) countLbl.textContent = `Mostrando últimos ${logs.length} eventos de auditoría`;

    if (logs.length === 0) {
      container.innerHTML = `
        <div class="stats-empty-state">
          <p>No se registran eventos en el historial todavía.</p>
        </div>
      `;
      return;
    }

    const actionBadgeMap = {
      login: { label: "🔑 Inicio de sesión", class: "badge-audit login" },
      book_open: { label: "📖 Apertura de libro", class: "badge-audit book" },
      ending_reached: { label: "🏆 Final alcanzado", class: "badge-audit ending" },
      logout: { label: "🚪 Cierre de sesión", class: "badge-audit logout" }
    };

    container.innerHTML = `
      <table class="library-table">
        <thead>
          <tr>
            <th>Fecha / Hora</th>
            <th>Usuario</th>
            <th>Tipo de Evento</th>
            <th>Libro</th>
            <th>Detalle</th>
          </tr>
        </thead>
        <tbody>
          ${logs.map(l => {
            const badge = actionBadgeMap[l.action_type] || { label: l.action_type, class: "badge-audit" };
            const bookName = (l.book_title && l.book_title !== '-') ? l.book_title : '-';
            const detailText = l.choice_made || '-';

            return `
              <tr>
                <td>${formatTimeAgo(l.created_at)}</td>
                <td><strong>@${escapeHtml(l.username)}</strong> ${l.first_name ? `(${escapeHtml(l.first_name)})` : ''}</td>
                <td><span class="${badge.class}">${badge.label}</span></td>
                <td>${escapeHtml(bookName)}</td>
                <td>${escapeHtml(detailText)}</td>
              </tr>
            `;
          }).join("")}
        </tbody>
      </table>
    `;
  } catch (err) {
    console.error("Error loading admin logs:", err);
  }
}
