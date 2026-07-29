/**
 * Library Module for PathTale (Book catalog rendering, view modes, and starting games)
 */

import { state, authFetch, escapeHtml, API_BASE } from "./state.js";
import { openAuthModal } from "./auth.js";

const libraryGrid = document.getElementById("library-grid");

export function setLibraryViewMode(mode) {
  state.libraryViewMode = mode;
  localStorage.setItem("alj_library_view", mode);
  
  const btnGrid = document.getElementById("btn-view-grid");
  const btnTable = document.getElementById("btn-view-table");
  
  if (mode === "table") {
    if (libraryGrid) libraryGrid.classList.add("view-table");
    if (btnGrid) btnGrid.classList.remove("active");
    if (btnTable) btnTable.classList.add("active");
  } else {
    if (libraryGrid) libraryGrid.classList.remove("view-table");
    if (btnGrid) btnGrid.classList.add("active");
    if (btnTable) btnTable.classList.remove("active");
  }
}

export async function checkLastActiveGame(startGameFn) {
  const heroActions = document.getElementById("hero-actions");
  const btnContinue = document.getElementById("btn-hero-continue");
  if (!heroActions || !btnContinue) return;

  const uid = (state.currentUser && state.currentUser.user_id) ? state.currentUser.user_id : 1;
  try {
    const res = await authFetch(`${API_BASE}/api/games/${uid}/last_active`);
    const data = await res.json();
    if (data && data.has_active_game && data.book_id) {
      heroActions.classList.remove("hidden");
      btnContinue.onclick = () => {
        if (startGameFn) startGameFn(data.book_id, false);
      };
    } else {
      heroActions.classList.add("hidden");
    }
  } catch (err) {
    console.warn("Could not check last active game:", err);
    heroActions.classList.add("hidden");
  }
}

export async function loadInProgressSection(startGameFn) {
  const section = document.getElementById("section-continue-reading");
  const grid = document.getElementById("continue-cards-grid");
  if (!section || !grid) return;

  const uid = (state.currentUser && state.currentUser.user_id) ? state.currentUser.user_id : 1;
  try {
    const res = await authFetch(`${API_BASE}/api/games/${uid}/in_progress?limit=3`);
    const data = await res.json();
    const books = data.in_progress || [];

    if (!Array.isArray(books) || books.length === 0) {
      section.classList.add("hidden");
      return;
    }

    section.classList.remove("hidden");
    grid.innerHTML = books.map(b => `
      <div class="continue-card" data-book-id="${b.book_id}">
        <div class="continue-thumb-wrap">
          ${b.cover_image_url 
            ? `<img src="${b.cover_image_url}?v=${Date.now()}" alt="${escapeHtml(b.title)}" class="continue-thumb-img">` 
            : `<div class="book-cover-placeholder" style="font-size:1.5rem">📜</div>`}
        </div>
        <div class="continue-info">
          <p class="continue-genre">${escapeHtml(b.genre || "Ficción Interactiva")}</p>
          <h3 class="continue-book-title">${escapeHtml(b.title)}</h3>
          <div class="continue-progress-row">
            <div class="continue-progress-bar-wrap">
              <div class="continue-progress-bar-fill" style="width: ${b.progress_percent || 0}%"></div>
            </div>
            <span class="continue-pct-lbl">${b.progress_percent || 0}%</span>
          </div>
          <div class="continue-meta-row">
            <span>⏱ ${escapeHtml(b.estimated_duration || "30 min")}</span>
            <span>📖 ${b.total_sections || 0} caps.</span>
          </div>
        </div>
      </div>
    `).join("");

    grid.querySelectorAll(".continue-card").forEach(card => {
      card.onclick = () => {
        const bookId = card.getAttribute("data-book-id");
        if (startGameFn) startGameFn(bookId, false);
      };
    });
  } catch (err) {
    console.warn("Could not load in-progress games:", err);
    section.classList.add("hidden");
  }
}

export async function loadCategoryTags() {
  const filterBar = document.getElementById("filter-tags-bar");
  if (!filterBar) return;

  try {
    const res = await authFetch(`${API_BASE}/api/tags`);
    const data = await res.json();
    const tags = data.tags || [];

    const defaultPills = `
      <button class="tag-pill active" data-tag="Todos">TODOS</button>
      <button class="tag-pill" data-tag="EN CURSO">EN CURSO</button>
    `;

    const tagPills = tags.map(t => `<button class="tag-pill" data-tag="${escapeHtml(t)}">${escapeHtml(t.toUpperCase())}</button>`).join("");
    filterBar.innerHTML = defaultPills + tagPills;

    filterBar.querySelectorAll(".tag-pill").forEach(btn => {
      btn.onclick = () => {
        filterBar.querySelectorAll(".tag-pill").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        const tag = btn.getAttribute("data-tag");
        loadLibrary(null, null, tag, 6);
      };
    });
  } catch (err) {
    console.warn("Could not load category tags:", err);
  }
}

export async function loadLibrary(onShowLanding, startGameFn, tag = "Todos", limit = 6) {
  checkLastActiveGame(startGameFn);
  loadInProgressSection(startGameFn);
  loadCategoryTags();

  const libraryGrid = document.getElementById("library-grid");
  if (libraryGrid) {
    libraryGrid.innerHTML = `
      <div class="loading-spinner" style="grid-column: 1/-1;">
        <div class="spinner"></div>
        <p>Cargando biblioteca...</p>
      </div>`;
  }

  const uid = (state.currentUser && state.currentUser.user_id) ? state.currentUser.user_id : 1;

  try {
    const res = await authFetch(`${API_BASE}/api/books?limit=${limit}&tag=${encodeURIComponent(tag)}&user_id=${uid}&random_sample=true`);
    const data = await res.json();
    state.allLibraryBooks = data.books || [];
    renderLibrary(state.allLibraryBooks, startGameFn);
  } catch (err) {
    console.error("Error loading library:", err);
    if (libraryGrid) {
      libraryGrid.innerHTML = `<p class="error-msg" style="grid-column: 1/-1;">Error al conectar con la API del servidor.</p>`;
    }
  }
}

export function renderLibrary(books, startGameFn) {
  const libraryGrid = document.getElementById("library-grid");
  if (!libraryGrid) return;

  if (books.length === 0) {
    libraryGrid.innerHTML = `
      <div class="loading-spinner" style="grid-column: 1/-1;">
        <p>No se encontraron libros para esta categoría.</p>
      </div>`;
    return;
  }

  libraryGrid.innerHTML = books.map(b => {
    let statusBadgeText = "Nuevo";
    let statusClass = "nuevo";

    if (b.status === "en_curso" || (b.has_savegame && b.progress_percent > 0 && b.progress_percent < 90)) {
      statusBadgeText = "En curso";
      statusClass = "en_curso";
    } else if (b.status === "completado" || b.progress_percent >= 90) {
      statusBadgeText = "Completado";
      statusClass = "completado";
    }

    const ratingVal = b.rating || 4.8;

    return `
    <div class="portrait-book-card" data-action="continue" data-book-id="${b.book_id}">
      <div class="portrait-cover-wrap">
        <span class="card-status-badge ${statusClass}">${statusBadgeText}</span>
        ${b.cover_image_url 
          ? `<img src="${b.cover_image_url}?v=${Date.now()}" alt="${escapeHtml(b.title)}" class="portrait-cover-img">` 
          : `<div class="book-cover-placeholder" style="font-size:2rem">📜</div>`}
        <div class="card-hover-play">▶</div>
      </div>
      <div class="portrait-card-info">
        <p class="portrait-genre">${escapeHtml(b.genre || "Ficción Interactiva")}</p>
        <h3 class="portrait-title">${escapeHtml(b.title)}</h3>
        <div class="portrait-rating">
          <span class="portrait-rating-stars">★★★★★</span>
          <span class="portrait-rating-val">${ratingVal}</span>
        </div>
      </div>
    </div>
  `;
  }).join("");

  libraryGrid.querySelectorAll(".portrait-book-card").forEach(card => {
    card.onclick = () => {
      const bookId = card.getAttribute("data-book-id");
      const hasSave = card.querySelector(".card-status-badge.en_curso");
      if (startGameFn) startGameFn(bookId, !hasSave);
    };
  });
}

export async function confirmRestartGame(bookId, startGameFn) {
  if (confirm("¿Estás seguro de que deseas reiniciar esta partida desde el principio?")) {
    await startGameFn(bookId, true);
  }
}
