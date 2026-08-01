import { state, authFetch, escapeHtml, API_BASE } from "../state.js";

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

state.tableSort = state.tableSort || { field: "title", order: "asc" };

function getSortIcon(field) {
  if (state.tableSort && state.tableSort.field === field) {
    return `<span class="sort-icon">${state.tableSort.order === "asc" ? "▲" : "▼"}</span>`;
  }
  return `<span class="sort-idle">↕</span>`;
}

export function sortTableBooks(books, field, startGameFn) {
  if (state.tableSort.field === field) {
    state.tableSort.order = state.tableSort.order === "asc" ? "desc" : "asc";
  } else {
    state.tableSort.field = field;
    state.tableSort.order = "asc";
  }

  const mult = state.tableSort.order === "asc" ? 1 : -1;

  books.sort((a, b) => {
    let valA = a[field] || "";
    let valB = b[field] || "";

    if (field === "genre") {
      valA = a.series || a.genre || "";
      valB = b.series || b.genre || "";
    } else if (field === "progress") {
      valA = a.progress_percent || 0;
      valB = b.progress_percent || 0;
    }

    if (typeof valA === "number" && typeof valB === "number") {
      return (valA - valB) * mult;
    }

    return String(valA).localeCompare(String(valB), "es", { sensitivity: "base" }) * mult;
  });

  renderFullLibrary(books, startGameFn);
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
    container.className = "library-table-wrap";
    container.innerHTML = `
      <table class="library-table">
        <thead>
          <tr>
            <th>Portada</th>
            <th class="sortable-th" data-sort="title">Título ${getSortIcon('title')}</th>
            <th class="sortable-th" data-sort="author">Autor ${getSortIcon('author')}</th>
            <th class="sortable-th" data-sort="genre">Género / Serie ${getSortIcon('genre')}</th>
            <th class="sortable-th" data-sort="progress">Progreso ${getSortIcon('progress')}</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          ${books.map(b => {
            const langFlag = (b.language && b.language.toLowerCase().startsWith("en")) ? "🇬🇧" : "🇪🇸";
            const seriesText = b.series ? `${b.series}${b.volume ? ' #' + b.volume : ''}` : (b.genre || "-");
            const isLocked = b.is_locked;
            return `
              <tr class="${isLocked ? 'row-locked' : ''}">
                <td class="td-thumb">
                  ${b.cover_image_url 
                    ? `<img src="${b.cover_image_url}?v=${Date.now()}" alt="${escapeHtml(b.title)}" class="table-thumb-img">`
                    : `<span style="font-size:1.2rem">📜</span>`}
                </td>
                <td class="td-title">
                  <strong>${langFlag} ${escapeHtml(b.title)}</strong>
                  ${isLocked ? `<br><span class="admin-badge" style="background:rgba(239, 68, 68, 0.15); color:#ef4444; border:1px solid rgba(239, 68, 68, 0.3); margin-top:0.2rem; font-size:0.68rem">🔒 ${escapeHtml(b.tier_name)}</span>` : ''}
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
                  ${isLocked ? `
                    <button class="btn-secondary btn-sm" data-action="locked" data-book-id="${b.book_id}" style="color:#ef4444">
                      🔒 ${escapeHtml(b.tier_name)}
                    </button>
                  ` : b.has_savegame ? `
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

    container.querySelectorAll(".sortable-th").forEach(th => {
      th.onclick = () => {
        const field = th.getAttribute("data-sort");
        sortTableBooks(state.allLibraryBooks, field, startGameFn);
      };
    });
  } else {
    container.className = "library-grid";
    container.innerHTML = books.map(b => {
      const langFlag = (b.language && b.language.toLowerCase().startsWith("en")) ? "🇬🇧" : "🇪🇸";
      const seriesText = b.series ? `📚 ${escapeHtml(b.series)}${b.volume ? ' #' + b.volume : ''}` : "";
      const isLocked = b.is_locked;

      return `
        <div class="book-card ${isLocked ? 'card-locked' : ''}">
          <div class="book-cover">
            ${b.cover_image_url 
              ? `<img src="${b.cover_image_url}?v=${Date.now()}" alt="${escapeHtml(b.title)}">` 
              : `<div class="book-cover-placeholder">📜</div>`}
            <span class="book-badge">${langFlag} ${b.total_sections} secc.</span>
            ${isLocked ? `<span class="card-status-badge tier-locked-badge" style="background:#ef4444; color:#fff">🔒 ${escapeHtml(b.tier_name)}</span>` : ''}
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
            ${isLocked ? `
              <button class="btn-secondary" data-action="locked" data-book-id="${b.book_id}" style="color:#ef4444">
                <span>🔒 Requiere ${escapeHtml(b.tier_name)}</span>
              </button>
            ` : b.has_savegame ? `
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

  container.querySelectorAll("[data-action]").forEach(btn => {
    btn.onclick = (e) => {
      e.stopPropagation();
      const action = btn.getAttribute("data-action");
      const bookId = btn.getAttribute("data-book-id");
      const book = books.find(b => b.book_id === bookId);

      if (action === "locked" || (book && book.is_locked)) {
        alert(`🔒 Este audiolibro requiere la membresía '${book ? book.tier_name : 'Superior'}'. Tu plan actual no permite acceder a este contenido. Contacta con el administrador.`);
        return;
      }

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
