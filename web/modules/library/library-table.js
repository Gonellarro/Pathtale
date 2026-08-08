import { escapeHtml } from "../state.js";
import { bindBookInfoModal } from "./book-info-modal.js";

function stars(rating) {
  return rating != null ? "★".repeat(Math.max(0, Math.min(5, Math.floor(Number(rating))))) : "—";
}

export function renderLibraryTable(container, books, { sortIcon, onSort }) {
  container.className = "library-table-wrap";
  container.innerHTML = `<table class="library-table"><thead><tr>
    <th>Portada</th><th class="sortable-th" data-sort="title">Título ${sortIcon("title")}</th><th>Valoración</th>
    <th class="sortable-th" data-sort="author">Autor ${sortIcon("author")}</th><th class="sortable-th" data-sort="genre">Género / Serie ${sortIcon("genre")}</th>
    <th class="sortable-th" data-sort="narrator">Narrador ${sortIcon("narrator")}</th><th class="sortable-th" data-sort="progress">Progreso ${sortIcon("progress")}</th><th>Acciones</th>
  </tr></thead><tbody>${books.map((book) => {
    const flag = book.language?.toLowerCase().startsWith("en") ? "🇬🇧" : "🇪🇸";
    const series = book.series ? `${book.series}${book.volume ? ` #${book.volume}` : ""}` : (book.genre || "-");
    const narrator = escapeHtml((book.narrator || "DAVEFX").replace(/\s*\(.*?\)/g, "").trim());
    return `<tr class="${book.is_locked ? "row-locked" : ""}">
      <td class="td-thumb">${book.cover_image_url ? `<img src="${book.cover_image_url}?v=${Date.now()}" alt="${escapeHtml(book.title)}" class="table-thumb-img">` : "<span style=\"font-size:1.2rem\">📜</span>"}</td>
      <td class="td-title"><strong data-book-info-id="${escapeHtml(book.book_id)}" class="book-info-title-trigger">${flag} ${escapeHtml(book.title)}</strong>${book.is_locked ? `<br><span class="admin-badge" style="background:rgba(239,68,68,.15);color:#ef4444;border:1px solid rgba(239,68,68,.3);margin-top:.2rem;font-size:.68rem">🔒 ${escapeHtml(book.tier_name)}</span>` : ""}</td>
      <td class="td-book-rating">${stars(book.rating)}</td><td class="td-author">${escapeHtml(book.author || "Desconocido")}</td><td class="td-genre">${escapeHtml(series)}</td>
      <td class="td-narrator" style="font-size:.82rem;color:var(--text-primary)">${narrator}</td>
      <td class="td-progress"><div class="table-progress-bar-wrap"><div class="table-progress-bar-fill" style="width:${book.progress_percent || 0}%"></div></div><span class="table-progress-pct">${book.progress_percent || 0}%</span></td>
      <td class="td-actions">${renderActions(book)}</td></tr>`;
  }).join("")}</tbody></table>`;
  container.querySelectorAll(".sortable-th").forEach((header) => {
    header.onclick = () => onSort(header.getAttribute("data-sort"));
  });
  bindBookInfoModal(container, books);
}

function renderActions(book) {
  if (book.is_locked) return `<button class="btn-secondary btn-sm" data-action="locked" data-book-id="${book.book_id}" style="color:#ef4444">🔒 ${escapeHtml(book.tier_name)}</button>`;
  if (book.has_savegame) return `<button class="btn-primary btn-sm" data-action="continue" data-book-id="${book.book_id}">▶ Continuar</button><button class="btn-secondary btn-sm" data-action="restart" data-book-id="${book.book_id}" title="Reiniciar">🔄</button>`;
  return `<button class="btn-primary btn-sm" data-action="start" data-book-id="${book.book_id}">✨ Iniciar</button>`;
}
