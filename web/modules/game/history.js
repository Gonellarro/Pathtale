import { state, authFetch, escapeHtml, formatTimeAgo, API_BASE } from "../state.js";

const drawerHistory = document.getElementById("drawer-history");

export function toggleHistoryDrawer() {
  if (drawerHistory) {
    drawerHistory.classList.toggle("open");
    if (drawerHistory.classList.contains("open")) {
      renderHistoryDrawer();
    }
  }
}

export async function renderHistoryDrawer() {
  if (!state.currentBookId) return;
  const listEl = document.getElementById("history-list");
  
  try {
    const res = await authFetch(`${API_BASE}/api/games/1/${encodeURIComponent(state.currentBookId)}/history`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const history = await res.json();
    
    if (!Array.isArray(history) || history.length === 0) {
      if (listEl) listEl.innerHTML = `<li class="history-item"><p>Aún no has tomado ninguna decisión en este libro.</p></li>`;
      return;
    }

    if (listEl) {
      listEl.innerHTML = history.map((item, idx) => `
        <li class="history-item">
          <span class="history-step">Paso ${history.length - idx}</span>
          <p class="history-choice">Elegiste: <strong>${escapeHtml(item.choice_text || item.to_node_id)}</strong></p>
          <span class="history-time">${formatTimeAgo(item.created_at)}</span>
        </li>
      `).join("");
    }
  } catch (err) {
    console.error("History fetch error:", err);
    if (listEl) listEl.innerHTML = `<li class="history-item"><p>No se pudo obtener el historial.</p></li>`;
  }
}
