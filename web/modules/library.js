/**
 * Library Module for PathTale (Book catalog rendering, view modes, and starting games)
 */

import { state, authFetch, API_BASE } from "./state.js";
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

export async function loadLibrary(onShowLanding) {
  if (!state.authToken || !state.currentUser) {
    if (onShowLanding) onShowLanding();
    return;
  }

  if (libraryGrid) {
    libraryGrid.innerHTML = `
      <div class="loading-spinner">
        <div class="spinner"></div>
        <p>Cargando biblioteca...</p>
      </div>`;
  }

  try {
    const res = await authFetch(`${API_BASE}/api/books`);
    const data = await res.json();
    state.allLibraryBooks = data.books || [];
    renderLibrary(state.allLibraryBooks);
  } catch (err) {
    console.error("Error loading library:", err);
    if (libraryGrid) {
      libraryGrid.innerHTML = `<p class="error-msg">Error al conectar con la API del servidor.</p>`;
    }
  }
}

export function filterLibraryByCategory(category) {
  if (category === "Todos") {
    renderLibrary(state.allLibraryBooks);
  } else if (category === "En curso") {
    renderLibrary(state.allLibraryBooks.filter(b => b.has_savegame && b.progress_percent > 0));
  } else {
    renderLibrary(state.allLibraryBooks.filter(b => 
      (b.genre && b.genre.toLowerCase().includes(category.toLowerCase())) ||
      (b.description && b.description.toLowerCase().includes(category.toLowerCase())) ||
      (b.series && b.series.toLowerCase().includes(category.toLowerCase())) ||
      (b.title && b.title.toLowerCase().includes(category.toLowerCase()))
    ));
  }
}

export function renderLibrary(books) {
  const libraryCount = document.getElementById("library-count");
  if (libraryCount) {
    libraryCount.textContent = `Mostrando ${books.length} libro${books.length === 1 ? '' : 's'}`;
  }
  setLibraryViewMode(state.libraryViewMode);

  if (!libraryGrid) return;

  if (books.length === 0) {
    libraryGrid.innerHTML = `
      <div class="loading-spinner">
        <p>No se encontraron libros. Copia un EPUB a la carpeta <code>Libros/</code> e impórtalo.</p>
      </div>`;
    return;
  }

  libraryGrid.innerHTML = books.map(b => {
    const langFlag = (b.language && b.language.toLowerCase().startsWith("en")) ? "🇬🇧" : "🇪🇸";
    const seriesText = b.series ? `📚 ${b.series}${b.volume ? ' #' + b.volume : ''}` : "";

    return `
    <div class="book-card">
      <div class="book-cover">
        ${b.cover_image_url 
          ? `<img src="${b.cover_image_url}?v=${Date.now()}" alt="${b.title}">` 
          : `<div class="book-cover-placeholder">📜</div>`}
        <span class="book-badge">${langFlag} ${b.total_sections} secc.</span>
      </div>
      <div class="book-info">
        <h3 class="book-title">${langFlag} ${b.title}</h3>
        <p class="book-author">${b.author}${b.year ? ' • ' + b.year : ''}</p>
        ${seriesText ? `<p class="book-series">${seriesText}</p>` : ''}
        <p class="book-desc">${b.description || "Aventura interactiva."}</p>
        
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

export async function confirmRestartGame(bookId, startGameFn) {
  if (confirm("¿Estás seguro de que deseas reiniciar esta partida desde el principio?")) {
    await startGameFn(bookId, true);
  }
}
