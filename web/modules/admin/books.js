import { openAdminBookTierModal } from "./book-tier-modal.js";
import { deleteAdminBook, fetchAdminBooks, updateAdminBook } from "./books-api.js";
import { renderAdminBooksList } from "./books-list.js";
import { openEditExistingBookModal } from "./book-edit-flow.js";

export let currentAdminBooks = [];

export async function loadAdminBooks() {
  const container = document.getElementById("admin-books-table-wrap");
  const countLabel = document.getElementById("admin-books-count");
  if (!container) return;
  try {
    const response = await fetchAdminBooks();
    const data = await response.json();
    const books = data.books || [];
    currentAdminBooks = books;
    if (countLabel) countLabel.textContent = `Total: ${books.length} libro${books.length === 1 ? "" : "s"}`;
    renderAdminBooksList(container, books, {
      onEdit: (bookId) => {
        const book = currentAdminBooks.find((item) => item.book_id === bookId);
        if (book) openEditExistingBookModal(book, loadAdminBooks);
      },
      onToggle: async (bookId, visible) => {
        try {
          const response = await updateAdminBook(bookId, { is_visible: !visible });
          if (response.ok) await loadAdminBooks();
        } catch (error) {
          console.error("Error toggling book visibility:", error);
        }
      },
      onTier: (bookId, title, tier) => openAdminBookTierModal(bookId, title, tier),
      onDelete: (bookId, isHidden) => confirmBookDeletion(bookId, isHidden),
    });
  } catch (error) {
    console.error("Error loading admin books:", error);
  }
}

function confirmBookDeletion(bookId, isHidden) {
  if (isHidden) {
    const warning = `El libro '${bookId}' ya está oculto.\n\nLa siguiente acción lo eliminará definitivamente de la base de datos y del disco. Esta operación no se puede deshacer.\n\n¿Continuar?`;
    if (confirm(warning)) deleteBook(bookId, true);
    return;
  }
  if (confirm(`¿Ocultar el libro '${bookId}' del catálogo?`)) deleteBook(bookId, false);
}

async function deleteBook(bookId, hard) {
  try {
    const response = await deleteAdminBook(bookId, hard);
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || "operación no permitida");
    }
    await loadAdminBooks();
  } catch (error) {
    alert(`Error al eliminar libro: ${error.message || "operación no permitida"}`);
  }
}
