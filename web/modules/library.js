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

export async function loadFullLibrary(startGameFn) {
  const container = document.getElementById("full-library-grid");
  const countLbl = document.getElementById("library-count");

  if (container) {
    container.innerHTML = `
      <div class="loading-spinner">
        <div class="spinner"></div>
        <p>Cargando catálogo completo...</p>
      </div>`;
  }

  const uid = (state.currentUser && state.currentUser.user_id) ? state.currentUser.user_id : 1;

  try {
    const res = await authFetch(`${API_BASE}/api/books?user_id=${uid}`);
    const data = await res.json();
    state.allLibraryBooks = data.books || [];

    if (countLbl) {
      countLbl.textContent = `Mostrando ${state.allLibraryBooks.length} libro${state.allLibraryBooks.length === 1 ? '' : 's'}`;
    }

    renderFullLibrary(state.allLibraryBooks, startGameFn);
  } catch (err) {
    console.error("Error loading full library:", err);
    if (container) {
      container.innerHTML = `<p class="error-msg">Error al conectar con la API del servidor.</p>`;
    }
  }
}

export function setLibraryViewMode(mode, startGameFn) {
  state.libraryViewMode = mode;
  localStorage.setItem("alj_library_view", mode);

  const btnGrid = document.getElementById("btn-view-grid");
  const btnTable = document.getElementById("btn-view-table");

  if (btnGrid && btnTable) {
    if (mode === "table") {
      btnGrid.classList.remove("active");
      btnTable.classList.add("active");
    } else {
      btnTable.classList.remove("active");
      btnGrid.classList.add("active");
    }
  }

  if (state.allLibraryBooks) {
    renderFullLibrary(state.allLibraryBooks, startGameFn);
  }
}

export function renderFullLibrary(books, startGameFn) {
  const container = document.getElementById("full-library-grid");
  if (!container) return;

  if (!books || books.length === 0) {
    container.innerHTML = `
      <div class="loading-spinner">
        <p>No se encontraron libros en el catálogo.</p>
      </div>`;
    return;
  }

  if (state.libraryViewMode === "table") {
    // Compact Table View
    container.className = "library-table-wrap";
    container.innerHTML = `
      <table class="library-table">
        <thead>
          <tr>
            <th>Portada</th>
            <th>Título</th>
            <th>Autor</th>
            <th>Género / Serie</th>
            <th>Progreso</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          ${books.map(b => {
            const langFlag = (b.language && b.language.toLowerCase().startsWith("en")) ? "🇬🇧" : "🇪🇸";
            const seriesText = b.series ? `${escapeHtml(b.series)}${b.volume ? ' #' + b.volume : ''}` : (b.genre || "-");
            return `
              <tr>
                <td class="td-thumb">
                  ${b.cover_image_url 
                    ? `<img src="${b.cover_image_url}?v=${Date.now()}" alt="${escapeHtml(b.title)}" class="table-thumb-img">`
                    : `<span style="font-size:1.2rem">📜</span>`}
                </td>
                <td class="td-title">
                  <strong>${langFlag} ${escapeHtml(b.title)}</strong>
                </td>
                <td class="td-author">${escapeHtml(b.author || "Desconocido")}</td>
                <td class="td-genre">${escapeHtml(seriesText)}</td>
                <td class="td-progress">
                  <div class="table-progress-bar-wrap">
                    <div class="table-progress-bar-fill" style="width: ${b.progress_percent || 0}%"></div>
                  </div>
                  <span class="table-progress-pct">${b.progress_percent || 0}%</span>
                </td>
                <td class="td-actions">
                  ${b.has_savegame ? `
                    <button class="btn-primary btn-sm" data-action="continue" data-book-id="${b.book_id}">
                      ▶ Continuar
                    </button>
                    <button class="btn-secondary btn-sm" data-action="restart" data-book-id="${b.book_id}" title="Reiniciar">
                      🔄
                    </button>
                  ` : `
                    <button class="btn-primary btn-sm" data-action="start" data-book-id="${b.book_id}">
                      ✨ Iniciar
                    </button>
                  `}
                </td>
              </tr>
            `;
          }).join("")}
        </tbody>
      </table>
    `;
  } else {
    // Rich Cards View
    container.className = "library-grid";
    container.innerHTML = books.map(b => {
      const langFlag = (b.language && b.language.toLowerCase().startsWith("en")) ? "🇬🇧" : "🇪🇸";
      const seriesText = b.series ? `📚 ${escapeHtml(b.series)}${b.volume ? ' #' + b.volume : ''}` : "";

      return `
        <div class="book-card">
          <div class="book-cover">
            ${b.cover_image_url 
              ? `<img src="${b.cover_image_url}?v=${Date.now()}" alt="${escapeHtml(b.title)}">` 
              : `<div class="book-cover-placeholder">📜</div>`}
            <span class="book-badge">${langFlag} ${b.total_sections} secc.</span>
          </div>
          <div class="book-info">
            <h3 class="book-title">${langFlag} ${escapeHtml(b.title)}</h3>
            <p class="book-author">${escapeHtml(b.author)}${b.year ? ' • ' + b.year : ''}</p>
            ${seriesText ? `<p class="book-series">${seriesText}</p>` : ''}
            <p class="book-desc">${escapeHtml(b.description || "Aventura interactiva.")}</p>
            
            <div class="book-progress-wrap">
              <div class="book-progress-info">
                <span>Progreso</span>
                <span>${b.progress_percent || 0}%</span>
              </div>
              <div class="progress-bar-wrap">
                <div class="progress-bar-fill" style="width: ${b.progress_percent || 0}%"></div>
              </div>
            </div>
          </div>
          <div class="book-actions">
            ${b.has_savegame ? `
              <button class="btn-primary" data-action="continue" data-book-id="${b.book_id}">
                <span>▶ Continuar</span>
              </button>
              <button class="btn-secondary" data-action="restart" data-book-id="${b.book_id}" title="Reiniciar Partida">
                <span>🔄</span>
              </button>
            ` : `
              <button class="btn-primary" data-action="start" data-book-id="${b.book_id}">
                <span>✨ Iniciar Partida</span>
              </button>
            `}
          </div>
        </div>
      `;
    }).join("");
  }

  // Bind click actions
  container.querySelectorAll("[data-action]").forEach(btn => {
    btn.onclick = (e) => {
      e.stopPropagation();
      const action = btn.getAttribute("data-action");
      const bookId = btn.getAttribute("data-book-id");
      if (action === "continue" || action === "start") {
        if (startGameFn) startGameFn(bookId, action === "start");
      } else if (action === "restart") {
        confirmRestartGame(bookId, startGameFn);
      }
    };
  });
}

export async function confirmRestartGame(bookId, startGameFn) {
  if (confirm("¿Estás seguro de que deseas reiniciar esta partida desde el principio?")) {
    await startGameFn(bookId, true);
  }
}
