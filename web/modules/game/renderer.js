import { escapeHtml, state } from "../state.js";
import { syncAmbientRuntime } from "../ambient_audio.js";
import { loadNarrativeAudio } from "../audio.js";
import { renderHistoryDrawer } from "./history.js";
import { recordVisitedNode } from "./navigation.js";

const audioPlayer = document.getElementById("html-audio-player");

function sanitizeRichText(html) {
  const template = document.createElement("template");
  template.innerHTML = html || "";
  const allowed = new Set(["P", "BR", "STRONG", "EM", "U", "MARK", "SUB", "SUP", "SMALL"]);
  template.content.querySelectorAll("*").forEach((element) => {
    [...element.attributes].forEach((attribute) => element.removeAttribute(attribute.name));
    if (!allowed.has(element.tagName)) element.replaceWith(document.createTextNode(element.textContent || ""));
  });
  return template.innerHTML;
}

function renderGameHeader(gameState) {
  const displaySection = gameState.display_number || gameState.node_id || "";
  const narratorRaw = (gameState.narrator_name || "Narración").replace(/\s*\([^)]*\)/g, "").trim();
  const narrator = narratorRaw ? narratorRaw.charAt(0) + narratorRaw.slice(1).toLowerCase() : "Narración";
  const engineName = gameState.narrator_engine?.includes("Google") ? "Google Cloud" : "";
  const setText = (id, value) => { const element = document.getElementById(id); if (element) element.textContent = value; };
  setText("game-book-title", gameState.book_title || "Librojuego");
  setText("game-book-subtitle", [`Sección ${displaySection}`, narrator, engineName].filter(Boolean).join(" · "));
  setText("game-section-title", `Sección ${displaySection}`);
  setText("game-section-count", `Sección ${displaySection} de ${gameState.total_sections || "—"}`);
  setText("audio-track-title", gameState.book_title || "Librojuego");
  setText("audio-track-subtitle", `Sección ${displaySection}`);
  const dock = document.getElementById("global-audio-player");
  if (dock) dock.classList.remove("hidden");
  const artwork = document.getElementById("global-player-artwork");
  if (artwork) {
    const url = gameState.cover_image_url || gameState.images?.[0];
    artwork.innerHTML = url ? `<img src="${escapeHtml(url)}?v=${Date.now()}" alt="">` : "▶";
  }
  const progress = gameState.progress_percent || 0;
  setText("game-progress-badge", `${progress}%`);
  const ring = document.getElementById("game-progress-ring");
  const bar = document.getElementById("game-progress-bar");
  if (ring) ring.style.setProperty("--progress", progress);
  if (bar) bar.style.width = `${progress}%`;
}

function renderNodeContent(gameState) {
  const image = document.getElementById("node-image");
  const imageContainer = document.getElementById("node-image-container");
  if (gameState.images?.length) {
    if (image) image.src = `${gameState.images[0]}?v=${Date.now()}`;
    imageContainer?.classList.remove("hidden");
  } else {
    imageContainer?.classList.add("hidden");
  }
  const badgeText = gameState.display_number ? `Sección ${gameState.display_number}` : gameState.node_id;
  const badge = document.getElementById("node-badge");
  const title = document.getElementById("node-title");
  if (badge) badge.textContent = badgeText;
  if (title) title.textContent = gameState.title || badgeText;
  const text = document.getElementById("node-text");
  if (text) {
    const paragraphs = (gameState.text || "").split("\n\n").filter((paragraph) => paragraph.trim());
    text.innerHTML = gameState.text_html ? sanitizeRichText(gameState.text_html)
      : paragraphs.map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`).join("");
  }
}

function focusSectionStart() {
  const focusedChoice = document.activeElement?.closest?.(".btn-choice");
  focusedChoice?.blur();

  const scrollToStart = () => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
    if (document.scrollingElement) document.scrollingElement.scrollTop = 0;
    document.documentElement.scrollTop = 0;
    document.body.scrollTop = 0;
  };
  scrollToStart();
  window.requestAnimationFrame(() => {
    scrollToStart();
    window.requestAnimationFrame(scrollToStart);
  });
}

export function renderGameState(gameState) {
  if (!gameState?.node_id) return;
  syncAmbientRuntime(gameState.audio_runtime);
  recordVisitedNode(gameState.node_id);
  renderGameHeader(gameState);
  renderNodeContent(gameState);
  const optionsButton = document.getElementById("btn-audio-options");
  optionsButton?.classList.toggle("hidden", !gameState.audio_options_url);
  if (audioPlayer && gameState.audio_url) {
    if (state.supplementsOpen) state.narrativeLoadDeferred = true;
    else {
      state.narrativeLoadDeferred = false;
      loadNarrativeAudio(gameState);
    }
  }
  renderChoices(gameState.choices || []);
  renderHistoryDrawer();
  focusSectionStart();
}

export function renderChoices(choices) {
  const list = document.getElementById("choices-list");
  if (!list) return;
  if (!choices.length) {
    list.innerHTML = `<div class="end-game-card"><h4>Fin de esta aventura</h4><p>Has alcanzado el final de este camino. Puedes reiniciar o probar otro libro.</p><button class="btn-primary" id="btn-end-back-library">Volver a la Biblioteca</button></div>`;
    document.getElementById("btn-end-back-library")?.addEventListener("click", async () => {
      const { showFullLibraryView } = await import("./views.js");
      showFullLibraryView();
    });
    return;
  }
  list.innerHTML = choices.map((choice) => `
    <button class="btn-choice" data-choice-id="${choice.choice_id}" data-target-node="${choice.target_node}">
      <span class="choice-num">${choice.choice_id}</span>
      <span class="choice-text">${escapeHtml(choice.text)}</span><span class="choice-arrow">→</span>
    </button>`).join("");
}
