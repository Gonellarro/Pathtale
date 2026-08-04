import { authFetch, API_BASE } from "../state.js";

let eventsBound = false;

export function openAdminBookTierModal(bookId, bookTitle, currentTierId) {
  const modal = document.getElementById("modal-admin-book-tier");
  if (!modal) return;
  const title = document.getElementById("modal-admin-book-tier-title");
  const subtitle = document.getElementById("admin-book-tier-subtitle");
  const inputBookId = document.getElementById("admin-book-tier-id-input");
  const selectTier = document.getElementById("admin-book-tier-select");
  const errDiv = document.getElementById("admin-book-tier-error");
  errDiv?.classList.add("hidden");
  if (errDiv) errDiv.textContent = "";
  if (title) title.textContent = "🏷️ Membresía Requerida";
  if (subtitle) subtitle.textContent = `Asigna el nivel de membresía mínimo necesario para que los usuarios puedan reproducir '${bookTitle}':`;
  if (inputBookId) inputBookId.value = bookId;
  if (selectTier) selectTier.value = currentTierId || "1";
  modal.classList.add("open");
  bindEvents();
}

export function closeAdminBookTierModal() {
  document.getElementById("modal-admin-book-tier")?.classList.remove("open");
}

function bindEvents() {
  if (eventsBound) return;
  eventsBound = true;
  document.getElementById("btn-close-modal-admin-book-tier")?.addEventListener("click", closeAdminBookTierModal);
  document.getElementById("btn-cancel-admin-book-tier")?.addEventListener("click", closeAdminBookTierModal);
  document.getElementById("form-admin-book-tier")?.addEventListener("submit", async event => {
    event.preventDefault();
    const bookId = document.getElementById("admin-book-tier-id-input")?.value;
    const tierId = parseInt(document.getElementById("admin-book-tier-select")?.value, 10);
    const errDiv = document.getElementById("admin-book-tier-error");
    errDiv?.classList.add("hidden");
    if (errDiv) errDiv.textContent = "";
    try {
      const res = await authFetch(`${API_BASE}/api/admin/books/${encodeURIComponent(bookId)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tier_id: tierId })
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Error al actualizar el nivel del libro.");
      }
      closeAdminBookTierModal();
      const { loadAdminBooks } = await import("./books.js");
      loadAdminBooks();
    } catch (err) {
      if (errDiv) {
        errDiv.textContent = `❌ ${err.message}`;
        errDiv.classList.remove("hidden");
      }
    }
  });
}
