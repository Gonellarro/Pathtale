import { state, authFetch, escapeHtml, API_BASE } from "../state.js";

export async function loadCategoryTags(startGameFn) {
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
        loadFeaturedLibrary(startGameFn, tag, 3);
      };
    });
  } catch (err) {
    console.warn("Could not load category tags:", err);
  }
}

export async function loadFeaturedLibrary(startGameFn, tag = "Todos", limit = 3) {
  loadCategoryTags(startGameFn);

  const container = document.getElementById("home-featured-grid");
  if (container) {
    container.innerHTML = `
      <div class="loading-spinner" style="grid-column: 1/-1;">
        <div class="spinner"></div>
        <p>Cargando recomendaciones...</p>
      </div>`;
  }

  const uid = (state.currentUser && state.currentUser.user_id) ? state.currentUser.user_id : 1;

  try {
    const res = await authFetch(`${API_BASE}/api/books?limit=${limit}&tag=${encodeURIComponent(tag)}&user_id=${uid}&latest=true`);
    const data = await res.json();
    const books = data.books || [];
    renderFeaturedGrid(books, container, startGameFn);
  } catch (err) {
    console.error("Error loading featured library:", err);
    if (container) {
      container.innerHTML = `<p class="error-msg" style="grid-column: 1/-1;">Error al conectar con la API del servidor.</p>`;
    }
  }
}

export function renderFeaturedGrid(books, container, startGameFn) {
  if (!container) return;

  if (books.length === 0) {
    container.innerHTML = `
      <div class="loading-spinner" style="grid-column: 1/-1;">
        <p>No se encontraron libros para esta categoría.</p>
      </div>`;
    return;
  }

  container.innerHTML = books.map(b => {
    let statusBadgeText = "Nuevo";
    let statusClass = "nuevo";
    const isLocked = b.is_locked;

    if (isLocked) {
      statusBadgeText = `<svg style="width:11px;height:11px;vertical-align:-1px;margin-right:3px;stroke:currentColor;fill:none;" viewBox="0 0 24 24" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>${escapeHtml(b.tier_name)}`;
      statusClass = "locked";
    } else if (b.status === "en_curso" || (b.has_savegame && b.progress_percent > 0 && b.progress_percent < 90)) {
      statusBadgeText = "En curso";
      statusClass = "en_curso";
    } else if (b.status === "completado" || b.progress_percent >= 90) {
      statusBadgeText = "Completado";
      statusClass = "completado";
    }

    const ratingVal = b.rating || 4.8;
    const playSvg = `<svg style="width:20px;height:20px;fill:currentColor;margin-left:2px;" viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>`;
    const lockSvg = `<svg style="width:18px;height:18px;stroke:currentColor;fill:none;" viewBox="0 0 24 24" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>`;

    return `
    <div class="portrait-book-card ${isLocked ? 'card-locked' : ''}" data-action="continue" data-book-id="${b.book_id}">
      <div class="portrait-cover-wrap">
        <span class="card-status-badge ${statusClass}" ${isLocked ? 'style="background:rgba(239, 68, 68, 0.9); color:#fff; border:1px solid rgba(239, 68, 68, 0.4); font-size:0.68rem;"' : ''}>${statusBadgeText}</span>
        ${b.cover_image_url 
          ? `<img src="${b.cover_image_url}?v=${Date.now()}" alt="${escapeHtml(b.title)}" class="portrait-cover-img">` 
          : `<div class="book-cover-placeholder">
               <svg class="landing-svg-icon" style="width:36px;height:36px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>
             </div>`}
        <div class="card-hover-play">${isLocked ? lockSvg : playSvg}</div>
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

  container.querySelectorAll(".portrait-book-card").forEach(card => {
    card.onclick = () => {
      const bookId = card.getAttribute("data-book-id");
      const book = books.find(b => b.book_id === bookId);

      if (book && book.is_locked) {
        alert(`🔒 Este audiolibro requiere la membresía '${book.tier_name}'. Tu plan actual no permite acceder a este contenido. Contacta con el administrador.`);
        return;
      }

      const hasSave = card.querySelector(".card-status-badge.en_curso");
      if (startGameFn) startGameFn(bookId, !hasSave);
    };
  });
}
