import { state } from "../state.js";
import { fetchLibraryBooks } from "./library-api.js";
import { renderLibraryGrid } from "./library-grid.js";
import { renderLibraryTable } from "./library-table.js";

state.tableSort = state.tableSort || { field: "title", order: "asc" };

export async function loadFullLibrary(startGame) {
  const container = document.getElementById("full-library-grid");
  const count = document.getElementById("library-count");
  if (container) container.innerHTML = `<div class="loading-spinner"><div class="spinner"></div><p>Cargando catálogo completo...</p></div>`;
  try {
    state.allLibraryBooks = await fetchLibraryBooks();
    if (count) count.textContent = `Mostrando ${state.allLibraryBooks.length} libro${state.allLibraryBooks.length === 1 ? "" : "s"}`;
    renderFullLibrary(state.allLibraryBooks, startGame);
  } catch (error) {
    console.error("Error loading full library:", error);
    if (container) container.innerHTML = `<p class="error-msg">Error al conectar con la API del servidor.</p>`;
  }
}

export function setLibraryViewMode(mode, startGame) {
  state.libraryViewMode = mode;
  localStorage.setItem("alj_library_view", mode);
  document.getElementById("btn-view-grid")?.classList.toggle("active", mode !== "table");
  document.getElementById("btn-view-table")?.classList.toggle("active", mode === "table");
  renderFullLibrary(state.allLibraryBooks, startGame);
}

export function sortTableBooks(books, field, startGame) {
  state.tableSort = state.tableSort.field === field
    ? { field, order: state.tableSort.order === "asc" ? "desc" : "asc" }
    : { field, order: "asc" };
  const direction = state.tableSort.order === "asc" ? 1 : -1;
  books.sort((left, right) => {
    const value = (book) => field === "genre" ? (book.series || book.genre || "") : field === "progress" ? (book.progress_percent || 0) : (book[field] || "");
    const a = value(left); const b = value(right);
    return (typeof a === "number" && typeof b === "number" ? a - b : String(a).localeCompare(String(b), "es", { sensitivity: "base" })) * direction;
  });
  renderFullLibrary(books, startGame);
}

export function renderFullLibrary(books, startGame) {
  const container = document.getElementById("full-library-grid");
  if (!container) return;
  if (!books?.length) {
    container.innerHTML = `<div class="loading-spinner"><p>No se encontraron libros en el catálogo.</p></div>`;
    return;
  }
  if (state.libraryViewMode === "table") {
    renderLibraryTable(container, books, { sortIcon, onSort: (field) => sortTableBooks(state.allLibraryBooks, field, startGame) });
  } else {
    renderLibraryGrid(container, books);
  }
  bindBookActions(container, books, startGame);
}

function sortIcon(field) {
  if (state.tableSort.field !== field) return '<span class="sort-idle">↕</span>';
  return `<span class="sort-icon">${state.tableSort.order === "asc" ? "▲" : "▼"}</span>`;
}

function bindBookActions(container, books, startGame) {
  container.querySelectorAll("[data-action]").forEach((button) => {
    button.onclick = (event) => {
      event.stopPropagation();
      const action = button.getAttribute("data-action");
      const bookId = button.getAttribute("data-book-id");
      const book = books.find((item) => item.book_id === bookId);
      if (action === "locked" || book?.is_locked) {
        alert(`🔒 Este audiolibro requiere la membresía '${book?.tier_name || "Superior"}'. Tu plan actual no permite acceder a este contenido. Contacta con el administrador.`);
      } else if (action === "restart") {
        confirmRestartGame(bookId, startGame);
      } else if (action === "continue" || action === "start") {
        startGame?.(bookId, action === "start");
      }
    };
  });
}

export async function confirmRestartGame(bookId, startGame) {
  if (confirm("¿Estás seguro de que deseas reiniciar esta partida desde el principio?")) await startGame?.(bookId, true);
}
