/**
 * Admin Module for PathTale Dashboard
 * Manages Users CRUD, EPUB Book Imports & Metadata, Narrators, and Audit Logs.
 */

import { state, authFetch, escapeHtml, formatTimeAgo, API_BASE } from "./state.js";

export async function loadAdminDashboard() {
  if (!state.currentUser || state.currentUser.role !== "admin") return;

  initAdminTabs();
  initAdminUploadZone();
  loadAdminUsers();
  loadAdminBooks();
  loadAdminNarrators();
  loadAdminLogs();
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

export async function loadAdminUsers() {
  const container = document.getElementById("admin-users-table-wrap");
  const countLbl = document.getElementById("admin-users-count");
  if (!container) return;

  try {
    const res = await authFetch(`${API_BASE}/api/admin/users`);
    const data = await res.json();
    const users = data.users || [];

    if (countLbl) countLbl.textContent = `Total: ${users.length} usuario${users.length === 1 ? '' : 's'}`;

    container.innerHTML = `
      <table class="library-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Usuario</th>
            <th>Nombre</th>
            <th>Rol</th>
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
                <span class="card-status-badge ${u.role === 'admin' ? 'en_curso' : 'nuevo'}">
                  ${u.role === 'admin' ? '⚡ ADMIN' : 'USER'}
                </span>
              </td>
              <td>${formatTimeAgo(u.created_at)}</td>
              <td class="td-actions">
                <button class="btn-secondary btn-sm btn-edit-user" data-id="${u.user_id}" data-name="${escapeHtml(u.first_name || '')}" data-role="${u.role}">✏️ Editar</button>
                ${u.user_id !== 1 ? `<button class="btn-secondary btn-sm btn-delete-user" data-id="${u.user_id}" style="color: #ff6b6b">🗑️</button>` : ''}
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;

    // Bind edit/delete
    container.querySelectorAll(".btn-edit-user").forEach(btn => {
      btn.onclick = () => {
        const uid = btn.getAttribute("data-id");
        const fname = btn.getAttribute("data-name");
        const urole = btn.getAttribute("data-role");
        promptEditUser(uid, fname, urole);
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
      btnAdd.onclick = () => promptCreateUser();
    }
  } catch (err) {
    console.error("Error loading admin users:", err);
  }
}

async function promptCreateUser() {
  const username = prompt("Nombre de usuario (login):");
  if (!username) return;
  const password = prompt("Contraseña (mín. 4 caracteres):");
  if (!password) return;
  const name = prompt("Nombre visible (opcional):") || username;
  const isAdmin = confirm("¿Otorgar permisos de Administrador (ADMIN)? OK = Sí, Cancelar = Usuario Normal");

  try {
    const res = await authFetch(`${API_BASE}/api/admin/users`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username,
        password,
        first_name: name,
        role: isAdmin ? "admin" : "user"
      })
    });
    const data = await res.json();
    if (res.ok) {
      alert(`✅ Usuario '${username}' creado correctamente.`);
      loadAdminUsers();
    } else {
      alert(`❌ Error: ${data.detail}`);
    }
  } catch (err) {
    alert(`❌ Error al conectar: ${err.message}`);
  }
}

async function promptEditUser(userId, currentName, currentRole) {
  const newName = prompt("Nuevo nombre visible:", currentName);
  if (newName === null) return;
  const newRole = confirm(`¿Rol actual: ${currentRole}? Presiona OK para ADMIN o Cancelar para USER`) ? "admin" : "user";
  const newPass = prompt("Nueva contraseña (deja en blanco para mantener la actual):");

  try {
    const body = { first_name: newName, role: newRole };
    if (newPass && newPass.trim()) body.password = newPass.trim();

    const res = await authFetch(`${API_BASE}/api/admin/users/${userId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    if (res.ok) {
      loadAdminUsers();
    }
  } catch (err) {
    alert("Error al actualizar usuario.");
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

    if (countLbl) countLbl.textContent = `Total: ${books.length} libro${books.length === 1 ? '' : 's'}`;

    container.innerHTML = `
      <table class="library-table">
        <thead>
          <tr>
            <th>Portada</th>
            <th>Título</th>
            <th>Autor</th>
            <th>Narrador</th>
            <th>Género / Serie</th>
            <th>Secciones</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          ${books.map(b => `
            <tr>
              <td class="td-thumb">
                ${b.cover_image 
                  ? `<img src="/api/books/${b.book_id}/asset/${b.cover_image}?v=${Date.now()}" alt="${escapeHtml(b.title)}" class="table-thumb-img">`
                  : `📜`}
              </td>
              <td class="td-title"><strong>${escapeHtml(b.title)}</strong><br><small style="color:var(--text-muted)">ID: ${b.book_id}</small></td>
              <td class="td-author">${escapeHtml(b.author || 'Desconocido')}</td>
              <td><span class="card-status-badge en_curso">🎙️ ${escapeHtml(b.narrator_name || 'DaveFX')}</span></td>
              <td class="td-genre">${escapeHtml(b.genre || b.series || '-')}</td>
              <td>${b.total_sections || 0} caps.</td>
              <td class="td-actions">
                <button class="btn-secondary btn-sm btn-delete-book" data-id="${b.book_id}" style="color: #ff6b6b">🗑️ Eliminar</button>
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;

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
  if (!file.name.toLowerCase().endsWith(".epub")) {
    alert("❌ Error: El archivo debe ser de tipo .epub");
    return;
  }

  const zone = document.getElementById("book-upload-zone");
  const progress = document.getElementById("upload-progress");
  const progressMsg = document.getElementById("upload-progress-msg");

  if (zone) zone.classList.add("hidden");
  if (progress) progress.classList.remove("hidden");
  if (progressMsg) progressMsg.textContent = `Importando '${file.name}' y sintetizando audios TTS con Piper... Por favor espera.`;

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await authFetch(`${API_BASE}/api/admin/books/upload`, {
      method: "POST",
      body: formData
    });
    const data = await res.json();

    if (res.ok) {
      alert(`✅ ¡Éxito! ${data.message}`);
      loadAdminBooks();
    } else {
      alert(`❌ Error al importar: ${data.detail}`);
    }
  } catch (err) {
    alert(`❌ Error de comunicación: ${err.message}`);
  } finally {
    if (zone) zone.classList.remove("hidden");
    if (progress) progress.classList.add("hidden");
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
    const res = await authFetch(`${API_BASE}/api/admin/logs?limit=50`);
    const data = await res.json();
    const logs = data.logs || [];

    if (countLbl) countLbl.textContent = `Mostrando últimos ${logs.length} eventos`;

    container.innerHTML = `
      <table class="library-table">
        <thead>
          <tr>
            <th>Fecha</th>
            <th>Usuario</th>
            <th>Libro</th>
            <th>Acción / Nodo</th>
            <th>Decisión / Detalle</th>
          </tr>
        </thead>
        <tbody>
          ${logs.map(l => `
            <tr>
              <td>${formatTimeAgo(l.created_at)}</td>
              <td><strong>@${escapeHtml(l.username)}</strong></td>
              <td>${escapeHtml(l.book_title || l.book_id)}</td>
              <td><span class="card-status-badge nuevo">${escapeHtml(l.action_type || 'node_visit')}</span> <code>${escapeHtml(l.node_id)}</code></td>
              <td>${escapeHtml(l.choice_made || '-')}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  } catch (err) {
    console.error("Error loading admin logs:", err);
  }
}
