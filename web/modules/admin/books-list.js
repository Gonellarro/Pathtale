import { escapeHtml } from "../state.js";

export function renderAdminBooksList(container, books, handlers) {
  container.innerHTML = `
    <table class="library-table">
      <thead><tr><th>Portada</th><th>Título</th><th>Narrador</th><th>Nivel Tier</th><th>Estado</th><th>Secciones</th><th>Acciones</th></tr></thead>
      <tbody>${books.map((book) => {
        const visible = book.is_visible !== 0;
        const narrator = escapeHtml((book.narrator_name || "DaveFX").replace(/\s*\(.*?\)/g, "").trim());
        return `<tr>
          <td class="td-thumb">${book.cover_image ? `<img src="/api/books/${book.book_id}/asset/${book.cover_image}?v=${Date.now()}" alt="${escapeHtml(book.title)}" class="table-thumb-img">` : "📜"}</td>
          <td class="td-title"><a href="#" class="admin-book-title-link" data-id="${book.book_id}" style="color:var(--accent-gold); text-decoration:none; font-weight:bold;">${escapeHtml(book.title)}</a><br><small style="color:var(--text-muted)">ID: ${book.book_id}</small></td>
          <td class="td-narrator" style="font-weight:500;">${narrator}</td>
          <td><span class="admin-badge admin-badge-tier">🔒 ${escapeHtml(book.tier_name || "Demo Gratuita")}</span></td>
          <td><button class="btn-secondary btn-sm btn-toggle-visible-book" data-id="${book.book_id}" data-visible="${visible ? "1" : "0"}" style="color:${visible ? "var(--success)" : "#ef4444"}">${visible ? "👁️ Visible" : "🙈 Oculto"}</button></td>
          <td>${book.total_sections || 0} caps.</td>
          <td class="td-actions"><button class="btn-secondary btn-sm btn-tier-book" data-id="${book.book_id}" data-title="${escapeHtml(book.title)}" data-tier="${book.tier_id || 1}">🏷️ Tier</button><button class="btn-secondary btn-sm btn-delete-book" data-id="${book.book_id}" style="color:#ff6b6b">🗑️</button></td>
        </tr>`;
      }).join("")}</tbody>
    </table>`;

  container.querySelectorAll(".admin-book-title-link").forEach((link) => {
    link.onclick = (event) => { event.preventDefault(); handlers.onEdit(link.dataset.id); };
  });
  container.querySelectorAll(".btn-toggle-visible-book").forEach((button) => {
    button.onclick = () => handlers.onToggle(button.dataset.id, button.dataset.visible === "1");
  });
  container.querySelectorAll(".btn-tier-book").forEach((button) => {
    button.onclick = () => handlers.onTier(button.dataset.id, button.dataset.title, button.dataset.tier);
  });
  container.querySelectorAll(".btn-delete-book").forEach((button) => {
    button.onclick = () => handlers.onDelete(button.dataset.id);
  });
}
