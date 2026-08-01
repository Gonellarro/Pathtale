import { authFetch, escapeHtml, API_BASE } from "../state.js";

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
