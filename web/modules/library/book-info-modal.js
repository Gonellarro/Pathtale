import { authFetch, escapeHtml, API_BASE } from "../state.js";

let activeBookForInfo = null;

function closeBookInfoModal() {
  document.getElementById("modal-book-info")?.classList.remove("open");
}

function renderBookRatingStars(value = 0) {
  const stars = document.getElementById("book-rating-stars");
  if (!stars) return;
  stars.dataset.value = String(value);
  stars.innerHTML = [1, 2, 3, 4, 5].map(n => `
    <button type="button" class="book-rating-star ${n <= value ? "selected" : ""}" data-rating="${n}" aria-label="${n} de 5 estrellas" aria-checked="${n === value}">★</button>
  `).join("");
  stars.querySelectorAll(".book-rating-star").forEach(button => {
    button.addEventListener("mouseenter", () => {
      const hovered = Number(button.dataset.rating);
      stars.querySelectorAll(".book-rating-star").forEach((star, index) => {
        star.classList.toggle("hovered", index < hovered);
      });
    });
    button.addEventListener("click", async () => {
      if (!activeBookForInfo) return;
      const rating = Number(button.dataset.rating);
      try {
        const res = await authFetch(`${API_BASE}/api/books/${encodeURIComponent(activeBookForInfo.book_id)}/rating`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ rating })
        });
        if (!res.ok) throw new Error(`rating ${res.status}`);
        renderBookRatingStars(rating);
        const status = document.getElementById("book-rating-status");
        if (status) status.textContent = "Valoración guardada";
      } catch (err) {
        console.error("Error guardando valoración:", err);
        const status = document.getElementById("book-rating-status");
        if (status) status.textContent = "No se pudo guardar la valoración";
      }
    });
  });
  stars.onmouseleave = () => {
    const selected = Number(stars.dataset.value || 0);
    stars.querySelectorAll(".book-rating-star").forEach((star, index) => {
      star.classList.toggle("hovered", index < selected);
    });
  };
}

export async function openBookInfoModal(book) {
  if (!book) return;
  activeBookForInfo = book;
  const modal = document.getElementById("modal-book-info");
  const cover = document.getElementById("book-info-cover");
  const title = document.getElementById("book-info-title");
  const author = document.getElementById("book-info-author");
  const meta = document.getElementById("book-info-meta");
  const description = document.getElementById("book-info-description");
  const status = document.getElementById("book-rating-status");
  if (title) title.textContent = book.title || "Información del libro";
  if (author) author.textContent = book.author ? `Por ${book.author}` : "";
  if (meta) {
    const characteristics = [book.year, book.language, book.genre, book.series, book.narrator, book.total_sections ? `${book.total_sections} secciones` : null, book.estimated_duration].filter(Boolean);
    meta.innerHTML = characteristics.map(item => `<span>${escapeHtml(String(item))}</span>`).join("");
  }
  if (description) description.textContent = book.description || "Sin descripción disponible.";
  if (cover) {
    cover.src = book.cover_image_url || "";
    cover.alt = book.title || "Portada del libro";
    cover.classList.toggle("hidden", !book.cover_image_url);
  }
  if (status) status.textContent = "";
  renderBookRatingStars(0);
  modal?.classList.add("open");
  try {
    const res = await authFetch(`${API_BASE}/api/books/${encodeURIComponent(book.book_id)}/rating`);
    if (res.ok) {
      const data = await res.json();
      renderBookRatingStars(data.rating?.rating || 0);
    }
  } catch (err) {
    console.warn("No se pudo cargar la valoración:", err);
  }
}

export function bindBookInfoModal(container, books) {
  container.querySelectorAll("[data-book-info-id]").forEach(titleEl => {
    titleEl.onclick = (event) => {
      event.stopPropagation();
      const book = books.find(item => item.book_id === titleEl.dataset.bookInfoId);
      openBookInfoModal(book);
    };
  });
  const modal = document.getElementById("modal-book-info");
  const close = document.getElementById("btn-close-book-info");
  if (modal && !modal.dataset.bound) {
    modal.dataset.bound = "true";
    close?.addEventListener("click", closeBookInfoModal);
    modal.addEventListener("click", event => {
      if (event.target === modal) closeBookInfoModal();
    });
  }
}
