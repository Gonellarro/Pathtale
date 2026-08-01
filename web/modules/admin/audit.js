import { authFetch, escapeHtml, formatTimeAgo, API_BASE } from "../state.js";

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
