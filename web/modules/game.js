/**
 * Game Module for PathTale (Reading Engine, Choices, Whisper Voice STT, Section Jump, History)
 */

import { state, authFetch, escapeHtml, formatTimeAgo, API_BASE } from "./state.js";
import { openAuthModal, updateAuthUI } from "./auth.js";
import { loadLibrary } from "./library.js";

const views = {
  library: document.getElementById("view-library"),
  game: document.getElementById("view-game")
};

const navBtns = {
  library: document.getElementById("btn-nav-library"),
  history: document.getElementById("btn-nav-history")
};

const audioPlayer = document.getElementById("html-audio-player");
const drawerHistory = document.getElementById("drawer-history");

export function showLandingView() {
  showLibraryView();
}

export function showLibraryView() {
  if (audioPlayer) audioPlayer.pause();
  if (views.game) views.game.classList.remove("active");
  if (views.library) views.library.classList.add("active");
  if (navBtns.library) navBtns.library.classList.add("active");
  updateAuthUI();
  if (state.authToken && state.currentUser) {
    loadLibrary(showLandingView);
  }
}

export function showGameView() {
  if (!state.authToken || !state.currentUser) {
    openAuthModal();
    return;
  }
  if (views.library) views.library.classList.remove("active");
  if (views.game) views.game.classList.add("active");
  if (navBtns.library) navBtns.library.classList.remove("active");
  updateAuthUI();
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
  const pct = gameState.progress_percent || 0;
  if (progBadge) progBadge.textContent = `${pct}%`;
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
    nodeTextContainer.innerHTML = paragraphs.map(p => `<p>${escapeHtml(p)}</p>`).join("");
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
    if (btnEnd) btnEnd.addEventListener("click", showLibraryView);
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

// --- VOICE RECOGNITION (WHISPER) ---

export function initVoiceControls() {
  const fileInput = document.getElementById("input-voice-file");
  if (fileInput) {
    fileInput.addEventListener("change", async (e) => {
      const file = e.target.files[0];
      if (file) await uploadAndTranscribeAudio(file);
    });
  }
}

export async function toggleVoiceRecording() {
  if (state.isRecording) {
    stopRecording();
  } else {
    await startRecording();
  }
}

export async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    state.audioChunks = [];
    state.mediaRecorder = new MediaRecorder(stream);

    state.mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) state.audioChunks.push(event.data);
    };

    state.mediaRecorder.onstop = async () => {
      const audioBlob = new Blob(state.audioChunks, { type: "audio/webm" });
      const file = new File([audioBlob], "voice_input.webm", { type: "audio/webm" });
      await uploadAndTranscribeAudio(file);
      stream.getTracks().forEach(t => t.stop());
    };

    state.mediaRecorder.start();
    state.isRecording = true;
    updateVoiceUI(true);
  } catch (err) {
    console.warn("Microphone API unavailable, opening native audio picker:", err);
    const fileInput = document.getElementById("input-voice-file");
    if (fileInput) fileInput.click();
  }
}

export function stopRecording() {
  if (state.mediaRecorder && state.isRecording) {
    state.mediaRecorder.stop();
    state.isRecording = false;
    updateVoiceUI(false);
  }
}

export function updateVoiceUI(recording) {
  const btn = document.getElementById("btn-voice-record");
  const status = document.getElementById("voice-status");
  const label = document.getElementById("voice-label");

  if (recording) {
    if (btn) btn.classList.add("recording");
    if (status) status.classList.remove("hidden");
    if (label) label.textContent = "Detener Grabación";
  } else {
    if (btn) btn.classList.remove("recording");
    if (status) status.classList.add("hidden");
    if (label) label.textContent = "Responder por Voz";
  }
}

export async function uploadAndTranscribeAudio(file) {
  const toast = document.getElementById("transcription-toast");
  const textEl = document.getElementById("transcription-text");
  
  if (toast) toast.classList.remove("hidden");
  if (textEl) textEl.textContent = "Procesando voz con Whisper AI...";

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await authFetch(`${API_BASE}/api/voice/transcribe`, {
      method: "POST",
      body: formData
    });

    const data = await res.json();
    if (data.status === "success" && data.text) {
      if (textEl) textEl.textContent = `Voz reconocida: "${data.text}"`;
      setTimeout(() => { if (toast) toast.classList.add("hidden"); }, 3000);
      await submitChoice(null, null, data.text);
    } else {
      if (textEl) textEl.textContent = "No se pudo interpretar el audio.";
      setTimeout(() => { if (toast) toast.classList.add("hidden"); }, 3000);
    }
  } catch (err) {
    console.error("Transcribe error:", err);
    if (textEl) textEl.textContent = "Error de conexión al transcribir voz.";
    setTimeout(() => { if (toast) toast.classList.add("hidden"); }, 3000);
  }
}

export function toggleHistoryDrawer() {
  if (drawerHistory) {
    drawerHistory.classList.toggle("open");
    if (drawerHistory.classList.contains("open")) {
      renderHistoryDrawer();
    }
  }
}

export async function renderHistoryDrawer() {
  if (!state.currentBookId) return;
  const listEl = document.getElementById("history-list");
  
  try {
    const res = await authFetch(`${API_BASE}/api/games/1/${encodeURIComponent(state.currentBookId)}/history`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const history = await res.json();
    
    if (!Array.isArray(history) || history.length === 0) {
      if (listEl) listEl.innerHTML = `<li class="history-item"><p>Aún no has tomado ninguna decisión en este libro.</p></li>`;
      return;
    }

    if (listEl) {
      listEl.innerHTML = history.map((item, idx) => `
        <li class="history-item">
          <span class="history-step">Paso ${history.length - idx}</span>
          <p class="history-choice">Elegiste: <strong>${escapeHtml(item.choice_text || item.to_node_id)}</strong></p>
          <span class="history-time">${formatTimeAgo(item.created_at)}</span>
        </li>
      `).join("");
    }
  } catch (err) {
    console.error("History fetch error:", err);
    if (listEl) listEl.innerHTML = `<li class="history-item"><p>No se pudo obtener el historial.</p></li>`;
  }
}
