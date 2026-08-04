import { state, authFetch, escapeHtml, API_BASE } from "../state.js";
import { openAuthModal } from "../auth.js";
import { renderHistoryDrawer } from "./history.js";
import { showGameView, showFullLibraryView } from "./views.js";
import { loadBookSupplements } from "./supplements.js";

const audioPlayer = document.getElementById("html-audio-player");

function sanitizeRichText(html) {
  const template = document.createElement("template");
  template.innerHTML = html || "";
  const allowed = new Set(["P", "BR", "STRONG", "EM", "U", "MARK", "SUB", "SUP", "SMALL"]);
  template.content.querySelectorAll("*").forEach(element => {
    [...element.attributes].forEach(attribute => element.removeAttribute(attribute.name));
    if (!allowed.has(element.tagName)) {
      element.replaceWith(document.createTextNode(element.textContent || ""));
    }
  });
  return template.innerHTML;
}

function getUserId() {
  return (state.currentUser && state.currentUser.user_id) ? state.currentUser.user_id : 1;
}

export async function startGame(bookId, forceNew = false) {
  if (!state.authToken || !state.currentUser) {
    openAuthModal();
    return;
  }
  if (state.currentBookId !== bookId || forceNew) {
    state.navigationHistory = [];
  }
  state.currentBookId = bookId;
  showGameView();

  const uid = getUserId();

  try {
    let res;
    if (forceNew) {
      res = await authFetch(`${API_BASE}/api/games`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ book_id: bookId })
      });
    } else {
      res = await authFetch(`${API_BASE}/api/games/${uid}/${encodeURIComponent(bookId)}`);
      if (res.status === 404) {
        return await startGame(bookId, true);
      }
    }

    if (!res.ok) {
      console.error("Error loading game state:", res.status);
      return;
    }

    const data = await res.json();
    if (data && data.node_id) {
      state.currentGameState = data;
      renderGameState(data);
      await loadBookSupplements(bookId, forceNew);
    }
  } catch (err) {
    console.error("Error starting game:", err);
    alert("Error al cargar la partida. Revisa la consola o los logs del servidor.");
  }
}

export async function submitChoice(choiceId, targetNode, textQuery = null) {
  if (!state.currentBookId) return;
  const uid = getUserId();

  try {
    const res = await authFetch(`${API_BASE}/api/games/${uid}/${encodeURIComponent(state.currentBookId)}/choice`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        choice_id: choiceId,
        target_node: targetNode,
        text_query: textQuery
      })
    });

    if (!res.ok) {
      console.error("Error submitting choice response status:", res.status);
      return;
    }

    const data = await res.json();
    if (data && data.node_id) {
      state.currentGameState = data;
      renderGameState(data);
    }
  } catch (err) {
    console.error("Error submitting choice:", err);
  }
}

export async function jumpToSection(target) {
  if (!state.currentBookId || !target) return;
  const uid = getUserId();

  try {
    const res = await authFetch(`${API_BASE}/api/games/${uid}/${encodeURIComponent(state.currentBookId)}/jump`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target: target })
    });

    if (!res.ok) {
      const err = await res.json();
      alert(`No se pudo ir a la sección ${target}: ${err.detail || 'Sección no encontrada'}`);
      return;
    }

    const data = await res.json();
    if (data && data.node_id) {
      state.currentGameState = data;
      renderGameState(data);
    }
  } catch (err) {
    console.error("Error jumping to section:", err);
  }
}

export async function goBackHistory() {
  if (state.navigationHistory.length <= 1) return;

  state.navigationHistory.pop();
  const previousNodeId = state.navigationHistory[state.navigationHistory.length - 1];

  if (previousNodeId) {
    state.isNavigatingBack = true;
    await jumpToSection(previousNodeId);
    state.isNavigatingBack = false;
  }
}

export function updateBackHistoryUI() {
  const btnBackHistory = document.getElementById("btn-game-history-back");
  if (btnBackHistory) {
    btnBackHistory.disabled = state.navigationHistory.length <= 1;
  }
}

export function renderGameState(gameState) {
  if (!gameState || !gameState.node_id) return;

  if (!state.isNavigatingBack) {
    if (state.navigationHistory.length === 0 || state.navigationHistory[state.navigationHistory.length - 1] !== gameState.node_id) {
      state.navigationHistory.push(gameState.node_id);
    }
  }
  updateBackHistoryUI();

  const titleEl = document.getElementById("game-book-title");
  const progBadge = document.getElementById("game-progress-badge");
  const progBar = document.getElementById("game-progress-bar");

  if (titleEl) titleEl.textContent = gameState.book_title || "Librojuego";
  const playerDock = document.getElementById("global-audio-player");
  const playerTitle = document.getElementById("audio-track-title");
  const playerSubtitle = document.getElementById("audio-track-subtitle");
  const playerArtwork = document.getElementById("global-player-artwork");
  if (playerDock) playerDock.classList.remove("hidden");
  if (playerTitle) playerTitle.textContent = gameState.book_title || "Librojuego";
  if (playerSubtitle) playerSubtitle.textContent = `Sección ${gameState.display_number || ""}`;
  if (playerArtwork) {
    playerArtwork.innerHTML = gameState.images?.[0]
      ? `<img src="${escapeHtml(gameState.images[0])}?v=${Date.now()}" alt="">`
      : "▶";
  }
  const pct = gameState.progress_percent || 0;
  if (progBadge) {
    progBadge.textContent = `${pct}%`;
    progBadge.style.setProperty("--progress", pct);
  }
  if (progBar) progBar.style.width = `${pct}%`;

  const nodeImgContainer = document.getElementById("node-image-container");
  const nodeImg = document.getElementById("node-image");
  if (gameState.images && gameState.images.length > 0) {
    if (nodeImg) nodeImg.src = `${gameState.images[0]}?v=${Date.now()}`;
    if (nodeImgContainer) nodeImgContainer.classList.remove("hidden");
  } else {
    if (nodeImgContainer) nodeImgContainer.classList.add("hidden");
  }

  const badgeText = gameState.display_number ? `Sección ${gameState.display_number}` : gameState.node_id;
  const nodeBadge = document.getElementById("node-badge");
  const nodeTitle = document.getElementById("node-title");
  if (nodeBadge) nodeBadge.textContent = badgeText;
  if (nodeTitle) nodeTitle.textContent = gameState.title || badgeText;

  const nodeTextContainer = document.getElementById("node-text");
  const paragraphs = (gameState.text || "").split("\n\n").filter(p => p.trim());
  if (nodeTextContainer) {
    nodeTextContainer.innerHTML = gameState.text_html
      ? sanitizeRichText(gameState.text_html)
      : paragraphs.map(p => `<p>${escapeHtml(p)}</p>`).join("");
  }

  const btnOpt = document.getElementById("btn-audio-options");
  if (btnOpt) {
    if (gameState.audio_options_url) {
      btnOpt.classList.remove("hidden");
    } else {
      btnOpt.classList.add("hidden");
    }
  }

  if (audioPlayer && gameState.audio_url) {
    state.currentAudioType = "narrative";
    audioPlayer.src = `${gameState.audio_url}?v=${Date.now()}`;
    if (state.appSettings.autoplay) {
      audioPlayer.play().catch(() => {});
    }
  }

  renderChoices(gameState.choices || []);
  renderHistoryDrawer();
}

export function renderChoices(choices) {
  const choicesList = document.getElementById("choices-list");
  if (!choicesList) return;
  
  if (choices.length === 0) {
    choicesList.innerHTML = `
      <div class="end-game-card">
        <h4>Fin de esta aventura</h4>
        <p>Has alcanzado el final de este camino. Puedes reiniciar o probar otro libro.</p>
        <button class="btn-primary" id="btn-end-back-library">Volver a la Biblioteca</button>
      </div>`;
    const btnEnd = document.getElementById("btn-end-back-library");
    if (btnEnd) btnEnd.addEventListener("click", showFullLibraryView);
    return;
  }

  choicesList.innerHTML = choices.map(c => `
    <button class="btn-choice" data-choice-id="${c.choice_id}" data-target-node="${c.target_node}">
      <span class="choice-num">${c.choice_id}</span>
      <span class="choice-text">${escapeHtml(c.text)}</span>
      <span class="choice-arrow">→</span>
    </button>
  `).join("");
}
