import { authFetch, escapeHtml, formatTimeAgo, API_BASE } from "../state.js";

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

export async function openAdminUserModal(user = null) {
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

export function closeAdminUserModal() {
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
