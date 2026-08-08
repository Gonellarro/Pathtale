import { escapeHtml } from "../state.js";
import { bindBookInfoModal } from "./book-info-modal.js";

function stars(rating) {
  return rating != null ? "★".repeat(Math.max(0, Math.min(5, Math.floor(Number(rating))))) : "Sin valoraciones";
}

export function renderLibraryGrid(container, books) {
  container.className = "library-grid";
  container.innerHTML = books.map((book) => {
    const flag = book.language?.toLowerCase().startsWith("en") ? "🇬🇧" : "🇪🇸";
    const series = book.series ? `<p class="book-series" style="margin-top:.25rem;">📚 ${escapeHtml(book.series)}${book.volume ? ` #${book.volume}` : ""}</p>` : "";
    return `<div class="book-card ${book.is_locked ? "card-locked" : ""}">
      <div class="book-cover">${book.cover_image_url ? `<img src="${book.cover_image_url}?v=${Date.now()}" alt="${escapeHtml(book.title)}">` : "<div class=\"book-cover-placeholder\">📜</div>"}
      <span class="book-badge">${flag} ${book.total_sections} secc.</span>${book.is_locked ? `<span class="card-status-badge tier-locked-badge" style="background:#ef4444;color:#fff">🔒 ${escapeHtml(book.tier_name)}</span>` : ""}</div>
      <div class="book-info"><h3 class="book-title book-info-title-trigger" data-book-info-id="${escapeHtml(book.book_id)}">${flag} ${escapeHtml(book.title)}</h3>
      <p class="book-author">${escapeHtml(book.author)}${book.year ? ` • ${book.year}` : ""}</p><p class="book-library-rating">${stars(book.rating)}</p>
      <p class="book-narrator" style="font-size:.8rem;color:var(--accent-gold);margin:.35rem 0;display:flex;align-items:center;gap:.3rem;"><svg style="width:13px;height:13px;stroke:currentColor;fill:none;" viewBox="0 0 24 24" stroke-width="2" aria-hidden="true"><path d="M3 18v-6a9 9 0 0 1 18 0v6"></path><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"></path></svg><span>${escapeHtml(book.narrator || "DAVEFX")}</span></p>${series}
      <p class="book-desc">${escapeHtml(book.description || "Aventura interactiva.")}</p><div class="book-progress-wrap"><div class="book-progress-info"><span>Progreso</span><span>${book.progress_percent || 0}%</span></div><div class="progress-bar-wrap"><div class="progress-bar-fill" style="width:${book.progress_percent || 0}%"></div></div></div></div>
      <div class="book-actions">${renderActions(book)}</div></div>`;
  }).join("");
  bindBookInfoModal(container, books);
}

function renderActions(book) {
  if (book.is_locked) return `<button class="btn-secondary" data-action="locked" data-book-id="${book.book_id}" style="color:#ef4444"><span>🔒 Requiere ${escapeHtml(book.tier_name)}</span></button>`;
  if (book.has_savegame) return `<button class="btn-primary" data-action="continue" data-book-id="${book.book_id}"><span>▶ Continuar</span></button><button class="btn-secondary" data-action="restart" data-book-id="${book.book_id}" title="Reiniciar Partida"><span>🔄</span></button>`;
  return `<button class="btn-primary" data-action="start" data-book-id="${book.book_id}"><span>✨ Iniciar Partida</span></button>`;
}
