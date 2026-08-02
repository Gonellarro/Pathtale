import { state, authFetch, escapeHtml, API_BASE } from "../state.js";

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

export async function loadNarratorsSection() {
  const container = document.getElementById("narrators-grid");
  if (!container) return;

  try {
    const res = await authFetch(`${API_BASE}/api/narrators`);
    const data = await res.json();
    const narrators = data.narrators || [];

    if (!Array.isArray(narrators) || narrators.length === 0) {
      if (container.parentElement) container.parentElement.classList.add("hidden");
      return;
    }

    if (container.parentElement) container.parentElement.classList.remove("hidden");
    container.innerHTML = narrators.map(n => {
      const isGoogle = (n.engine_code || '').toLowerCase() === 'google';
      const engineBadge = isGoogle 
        ? `<span class="badge" style="background:rgba(59, 130, 246, 0.15); color:#60a5fa; border:1px solid rgba(59, 130, 246, 0.3); font-size:0.65rem;">⚡ Google Cloud</span>`
        : `<span class="badge" style="background:rgba(16, 185, 129, 0.15); color:#34d399; border:1px solid rgba(16, 185, 129, 0.3); font-size:0.65rem;">🎙️ Piper ONNX</span>`;

      return `
        <div class="narrator-card" data-narrator-id="${escapeHtml(String(n.id))}">
          <img src="${n.avatar_url || '/assets/narrator_davefx.jpg'}" alt="${escapeHtml(n.name)}" class="narrator-avatar">
          <div class="narrator-info">
            <h3 class="narrator-name">${escapeHtml(n.name)}</h3>
            <p class="narrator-specialty">${escapeHtml(n.specialty)}</p>
            <div style="margin-top:0.25rem;">${engineBadge}</div>
            <p class="narrator-stories-count" style="margin-top:0.35rem;">
              <span>🎧</span>
              <span>${n.story_count} historia${n.story_count === 1 ? '' : 's'}</span>
            </p>
          </div>
          <div class="narrator-arrow">›</div>
        </div>
      `;
    }).join("");
  } catch (err) {
    console.warn("Could not load narrators:", err);
  }
}
