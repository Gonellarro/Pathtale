import { state, authFetch, escapeHtml, API_BASE } from "../state.js";

const CATEGORY_LABELS = {
  front_matter: "Antes de empezar",
  reference: "Reglas y consulta",
  back_matter: "Material adicional"
};

export async function loadBookSupplements(bookId, openOnStart = false) {
  const button = document.getElementById("btn-game-supplements");
  try {
    const response = await authFetch(`${API_BASE}/api/books/${encodeURIComponent(bookId)}/supplements`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    state.currentSupplements = data.supplements || [];
    if (button) button.classList.toggle("hidden", state.currentSupplements.length === 0);
    renderSupplementNavigation();
    if (openOnStart && state.currentSupplements.some(item => item.category === "front_matter")) {
      openSupplements("front_matter");
    }
  } catch (error) {
    console.error("Error loading supplemental material:", error);
    state.currentSupplements = [];
    if (button) button.classList.add("hidden");
  }
}

export function initSupplementControls() {
  const openButton = document.getElementById("btn-game-supplements");
  const closeButton = document.getElementById("btn-close-supplements");
  const modal = document.getElementById("modal-supplements");
  if (openButton) openButton.addEventListener("click", () => openSupplements());
  if (closeButton) closeButton.addEventListener("click", closeSupplements);
  if (modal) {
    modal.addEventListener("click", event => {
      if (event.target === modal) closeSupplements();
    });
  }
}

export function openSupplements(preferredCategory = null) {
  const modal = document.getElementById("modal-supplements");
  if (!modal || !state.currentSupplements?.length) return;
  const player = document.getElementById("html-audio-player");
  if (player) player.pause();
  state.supplementsOpen = true;
  modal.classList.add("open");
  const preferred = preferredCategory
    ? state.currentSupplements.find(item => item.category === preferredCategory)
    : null;
  renderSupplement(preferred || state.currentSupplements[0]);
}

export function closeSupplements() {
  const modal = document.getElementById("modal-supplements");
  if (modal) modal.classList.remove("open");
  const player = document.getElementById("html-audio-player");
  const shouldAutoplay = state.supplementsOpen && state.appSettings.autoplay;
  state.supplementsOpen = false;
  if (!player) return;

  const narrative = state.currentGameState?.audio_url;
  if (state.currentAudioType !== "narrative" && narrative) {
    state.currentAudioType = "narrative";
    player.src = `${narrative}?v=${Date.now()}`;
  }
  if (shouldAutoplay && narrative) player.play().catch(() => {});
}

function renderSupplementNavigation() {
  const navigation = document.getElementById("supplements-navigation");
  if (!navigation) return;
  const groups = Object.keys(CATEGORY_LABELS).map(category => {
    const items = (state.currentSupplements || []).filter(item => item.category === category);
    if (!items.length) return "";
    return `
      <section class="supplement-nav-group">
        <h3>${CATEGORY_LABELS[category]}</h3>
        ${items.map(item => `
          <button class="supplement-nav-item" data-supplement-id="${escapeHtml(item.id)}">
            ${escapeHtml(item.title)}
          </button>
        `).join("")}
      </section>`;
  }).join("");
  navigation.innerHTML = groups;
  navigation.querySelectorAll("[data-supplement-id]").forEach(button => {
    button.addEventListener("click", () => {
      const item = state.currentSupplements.find(candidate => candidate.id === button.dataset.supplementId);
      if (item) renderSupplement(item);
    });
  });
}

function renderSupplement(item) {
  if (!item) return;
  const content = document.getElementById("supplements-content");
  if (!content) return;
  document.querySelectorAll(".supplement-nav-item").forEach(button => {
    button.classList.toggle("active", button.dataset.supplementId === item.id);
  });
  const paragraphs = (item.text || "").split(/\n{2,}|\n/).filter(Boolean);
  const pages = item.source_pages?.length
    ? `<span class="supplement-source">Páginas ${item.source_pages.join(", ")}</span>`
    : "";
  content.innerHTML = `
    <div class="supplement-article-header">
      <span class="node-badge">${CATEGORY_LABELS[item.category] || "Contenido adicional"}</span>
      <h2>${escapeHtml(item.title)}</h2>
      ${pages}
    </div>
    <div class="supplement-text">${paragraphs.map(paragraph => `<p>${escapeHtml(paragraph)}</p>`).join("")}</div>
    ${item.images?.length ? `<div class="supplement-images">${item.images.map(image => `
      <img src="${escapeHtml(image)}" alt="Ilustración de ${escapeHtml(item.title)}" loading="lazy">
    `).join("")}</div>` : ""}
    ${item.audio_url ? `<button id="btn-play-supplement" class="btn-primary supplement-audio-button">▶ Escuchar este contenido</button>` : ""}
  `;
  const playButton = document.getElementById("btn-play-supplement");
  if (playButton) {
    playButton.addEventListener("click", () => {
      const player = document.getElementById("html-audio-player");
      if (!player) return;
      state.currentAudioType = "supplement";
      player.src = `${item.audio_url}?v=${Date.now()}`;
      player.play().catch(() => {});
    });
  }
}
