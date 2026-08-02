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
            : `<div class="book-cover-placeholder">
                 <svg class="landing-svg-icon" style="width:32px;height:32px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>
               </div>`}
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
            <span><svg style="width:13px;height:13px;vertical-align:-2px;margin-right:4px;stroke:var(--accent-gold);fill:none;" viewBox="0 0 24 24" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>${escapeHtml(b.estimated_duration || "30 min")}</span>
            <span><svg style="width:13px;height:13px;vertical-align:-2px;margin-right:4px;stroke:var(--accent-gold);fill:none;" viewBox="0 0 24 24" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>${b.total_sections || 0} caps.</span>
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
        ? `<span class="badge" style="background:rgba(59, 130, 246, 0.15); color:#60a5fa; border:1px solid rgba(59, 130, 246, 0.3); font-size:0.65rem;"><svg style="width:11px;height:11px;vertical-align:-1px;margin-right:3px;fill:currentColor;" viewBox="0 0 24 24"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>Google Cloud</span>`
        : `<span class="badge" style="background:rgba(16, 185, 129, 0.15); color:#34d399; border:1px solid rgba(16, 185, 129, 0.3); font-size:0.65rem;"><svg style="width:11px;height:11px;vertical-align:-1px;margin-right:3px;stroke:currentColor;fill:none;" viewBox="0 0 24 24" stroke-width="2"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path></svg>Piper ONNX</span>`;

      const count = Number(n.story_count ?? n.book_count ?? 0);

      return `
        <div class="narrator-card" data-narrator-id="${escapeHtml(String(n.id))}">
          <img src="${n.avatar_url || '/assets/narrator_davefx.jpg'}" alt="${escapeHtml(n.name)}" class="narrator-avatar">
          <div class="narrator-info">
            <h3 class="narrator-name">${escapeHtml(n.name)}</h3>
            <p class="narrator-specialty">${escapeHtml(n.specialty)}</p>
            <div style="margin-top:0.25rem;">${engineBadge}</div>
            <p class="narrator-stories-count" style="margin-top:0.35rem;">
              <svg style="width:13px;height:13px;vertical-align:-2px;margin-right:3px;stroke:var(--accent-gold);fill:none;" viewBox="0 0 24 24" stroke-width="2"><path d="M3 18v-6a9 9 0 0 1 18 0v6"></path><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"></path></svg>
              <span>${count} historia${count === 1 ? '' : 's'}</span>
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
