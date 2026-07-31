/**
 * Statistics Module for PathTale Interactive Gamebooks
 * Displays user progress, endings discovered, decisions made, and community global statistics.
 */

import { state, authFetch, API_BASE, escapeHtml } from "./state.js";

export async function loadUserStats() {
  const rawUid = (state.currentUser && state.currentUser.user_id) ? state.currentUser.user_id : 1;
  const uid = parseInt(String(rawUid).split(":")[0], 10) || 1;
  const startedEl = document.getElementById("user-stats-books-started");
  const completedEl = document.getElementById("user-stats-books-completed");
  const endingsEl = document.getElementById("user-stats-endings-reached");
  const decisionsEl = document.getElementById("user-stats-decisions");
  const listWrap = document.getElementById("stats-book-list");

  try {
    const res = await authFetch(`${API_BASE}/api/stats/user/${uid}`);
    if (!res.ok) throw new Error("Error obteniendo estadísticas del usuario");
    const data = await res.json();

    if (startedEl) startedEl.textContent = data.books_started || 0;
    if (completedEl) completedEl.textContent = data.books_completed || 0;
    if (endingsEl) endingsEl.textContent = data.endings_reached || 0;
    if (decisionsEl) decisionsEl.textContent = data.decisions_made || 0;

    if (listWrap) {
      if (!data.books_progress || data.books_progress.length === 0) {
        listWrap.innerHTML = `
          <div class="stats-empty-state">
            <p>Aún no has comenzado ningún libro. ¡Explora la biblioteca y comienza tu primera aventura!</p>
          </div>
        `;
      } else {
        listWrap.innerHTML = data.books_progress.map(b => {
          const coverUrl = b.cover_image ? `${API_BASE}/api/books/${b.book_id}/asset/${b.cover_image}` : '/assets/covers/default_cover.jpg';
          const totalEndings = b.total_endings || 0;
          const reachedEndings = b.endings_reached || 0;
          const endingPct = totalEndings > 0 ? Math.min(100, Math.round((reachedEndings / totalEndings) * 100)) : 0;
          const isCompleted = reachedEndings > 0;

          return `
            <div class="stats-book-card ${isCompleted ? 'completed' : ''}">
              <img src="${escapeHtml(coverUrl)}" alt="${escapeHtml(b.title)}" class="stats-book-cover" onerror="this.src='/assets/covers/default_cover.jpg'">
              <div class="stats-book-content">
                <div class="stats-book-header">
                  <h3 class="stats-book-title">${escapeHtml(b.title)}</h3>
                  ${isCompleted ? '<span class="badge-status success">Completado</span>' : '<span class="badge-status in-progress">En lectura</span>'}
                </div>

                <div class="stats-progress-group">
                  <div class="stats-progress-lbl-row">
                    <span>Progreso de Lectura</span>
                    <strong>${b.progress_percent}%</strong>
                  </div>
                  <div class="stats-progress-bar-bg">
                    <div class="stats-progress-bar-fill" style="width: ${b.progress_percent}%;"></div>
                  </div>
                </div>

                <div class="stats-progress-group">
                  <div class="stats-progress-lbl-row">
                    <span>Finales Descubiertos (${reachedEndings} de ${totalEndings || '?'})</span>
                    <strong>${endingPct}%</strong>
                  </div>
                  <div class="stats-progress-bar-bg endings">
                    <div class="stats-progress-bar-fill endings" style="width: ${endingPct}%;"></div>
                  </div>
                </div>
              </div>
            </div>
          `;
        }).join('');
      }
    }
  } catch (err) {
    console.error("Error loading user statistics:", err);
    if (listWrap) {
      listWrap.innerHTML = `
        <div class="stats-empty-state">
          <p>No se pudieron cargar tus estadísticas personales.</p>
        </div>
      `;
    }
  }

  // Load Global Community Statistics
  loadGlobalStats();
}

export async function loadGlobalStats() {
  const globalWrap = document.getElementById("global-stats-highlights");
  if (!globalWrap) return;

  try {
    const res = await authFetch(`${API_BASE}/api/stats/global`);
    if (!res.ok) throw new Error("Error obteniendo estadísticas globales");
    const data = await res.json();

    const mostRead = data.most_read_book;
    const highestRated = data.highest_rated_book;
    const mostEndings = data.most_endings_book;

    const getCover = (book) => (book && book.cover_image) ? `${API_BASE}/api/books/${book.book_id}/asset/${book.cover_image}` : '/assets/covers/default_cover.jpg';

    globalWrap.innerHTML = `
      <!-- Card 1: Libro más leído -->
      <div class="global-stat-card">
        <div class="global-card-badge">Más Leído</div>
        <div class="global-card-body">
          <img src="${escapeHtml(getCover(mostRead))}" alt="${escapeHtml(mostRead ? mostRead.title : 'Libro')}" class="global-book-cover" onerror="this.src='/assets/covers/default_cover.jpg'">
          <div class="global-card-info">
            <h4 class="global-card-title">${escapeHtml(mostRead ? mostRead.title : 'No disponible')}</h4>
            <p class="global-card-sub">${mostRead ? (mostRead.total_visits || 0) + ' secciones leídas' : 'Comunidad activa'}</p>
          </div>
        </div>
      </div>

      <!-- Card 2: Mejor Valorado -->
      <div class="global-stat-card">
        <div class="global-card-badge">Mejor Valorado</div>
        <div class="global-card-body">
          <img src="${escapeHtml(getCover(highestRated))}" alt="${escapeHtml(highestRated ? highestRated.title : 'Libro')}" class="global-book-cover" onerror="this.src='/assets/covers/default_cover.jpg'">
          <div class="global-card-info">
            <h4 class="global-card-title">${escapeHtml(highestRated ? highestRated.title : 'No disponible')}</h4>
            <p class="global-card-sub">Valoración: ${highestRated ? (highestRated.rating || 4.8) + ' / 5.0' : '5.0 ★'}</p>
          </div>
        </div>
      </div>

      <!-- Card 3: Más Finales Descubiertos -->
      <div class="global-stat-card">
        <div class="global-card-badge">Mayor Rejugabilidad</div>
        <div class="global-card-body">
          <img src="${escapeHtml(getCover(mostEndings))}" alt="${escapeHtml(mostEndings ? mostEndings.title : 'Libro')}" class="global-book-cover" onerror="this.src='/assets/covers/default_cover.jpg'">
          <div class="global-card-info">
            <h4 class="global-card-title">${escapeHtml(mostEndings ? mostEndings.title : 'No disponible')}</h4>
            <p class="global-card-sub">${mostEndings ? (mostEndings.endings_count || 0) + ' finales alcanzados' : 'Múltiples finales'}</p>
          </div>
        </div>
      </div>

      <!-- Card 4: Métricas Globales de la Comunidad -->
      <div class="global-stat-card metrics-summary">
        <div class="global-card-badge">Comunidad PathTale</div>
        <div class="global-summary-rows">
          <div class="summary-row">
            <span>Total Lecturas Realizadas</span>
            <strong>${data.total_reads || 0}</strong>
          </div>
          <div class="summary-row">
            <span>Decisiones Tomadas</span>
            <strong>${data.total_decisions || 0}</strong>
          </div>
          <div class="summary-row">
            <span>Finales Desbloqueados</span>
            <strong>${data.total_endings_unlocked || 0}</strong>
          </div>
        </div>
      </div>
    `;
  } catch (err) {
    console.error("Error loading global statistics:", err);
    if (globalWrap) {
      globalWrap.innerHTML = `<p class="stats-empty-state">No se pudieron cargar las estadísticas generales de la comunidad.</p>`;
    }
  }
}

export function showStatsView() {
  document.querySelectorAll(".view").forEach(v => {
    v.classList.remove("active");
    v.classList.add("hidden");
  });
  const viewStats = document.getElementById("view-stats");
  if (viewStats) {
    viewStats.classList.add("active");
    viewStats.classList.remove("hidden");
  }

  // Highlight navbar tab
  document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
  const btnStats = document.getElementById("btn-nav-stats");
  if (btnStats) btnStats.classList.add("active");

  loadUserStats();
}
