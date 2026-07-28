/**
 * ALJ Narrative Game Engine - PWA Frontend Client
 */

const API_BASE = "";
const USER_ID = 1; // Default single-user session ID for PWA client

// State
let currentBookId = null;
let currentGameState = null;
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;
let libraryViewMode = localStorage.getItem("alj_library_view") || "grid";

// DOM Elements
const views = {
  library: document.getElementById("view-library"),
  game: document.getElementById("view-game")
};

const navBtns = {
  library: document.getElementById("btn-nav-library"),
  history: document.getElementById("btn-nav-history"),
  settings: document.getElementById("btn-nav-settings")
};

const libraryGrid = document.getElementById("library-grid");
const audioPlayer = document.getElementById("html-audio-player");
const modalSettings = document.getElementById("modal-settings");
const drawerHistory = document.getElementById("drawer-history");

// Init App
document.addEventListener("DOMContentLoaded", () => {
  initEventListeners();
  loadSettings();
  loadLibrary();
});

function initEventListeners() {
  initVoiceControls();
  // Navigation
  document.getElementById("nav-brand").addEventListener("click", showLibraryView);
  navBtns.library.addEventListener("click", showLibraryView);
  navBtns.history.addEventListener("click", toggleHistoryDrawer);
  navBtns.settings.addEventListener("click", toggleSettingsModal);

  document.getElementById("btn-game-back").addEventListener("click", showLibraryView);
  document.getElementById("btn-game-restart").addEventListener("click", () => {
    if (currentBookId) confirmRestartGame(currentBookId);
  });
  document.getElementById("btn-close-settings").addEventListener("click", toggleSettingsModal);
  document.getElementById("btn-close-history").addEventListener("click", toggleHistoryDrawer);

  const btnGrid = document.getElementById("btn-view-grid");
  const btnTable = document.getElementById("btn-view-table");
  if (btnGrid && btnTable) {
    btnGrid.addEventListener("click", () => setLibraryViewMode("grid"));
    btnTable.addEventListener("click", () => setLibraryViewMode("table"));
  }

  // Audio Controls
  document.getElementById("btn-audio-play").addEventListener("click", toggleAudioPlay);
  document.getElementById("audio-slider").addEventListener("input", onAudioSeek);
  document.getElementById("btn-audio-speed").addEventListener("click", toggleAudioSpeed);

  audioPlayer.addEventListener("timeupdate", updateAudioProgress);
  audioPlayer.addEventListener("ended", onAudioEnded);

  // Voice Controls
  document.getElementById("btn-voice-record").addEventListener("click", toggleVoiceRecording);

  // Settings Controls
  document.getElementById("setting-theme").addEventListener("change", (e) => updateSetting("theme", e.target.value));
  document.getElementById("setting-font-size").addEventListener("change", (e) => updateSetting("fontSize", e.target.value));
  document.getElementById("setting-autoplay").addEventListener("change", (e) => updateSetting("autoplay", e.target.checked));
  document.getElementById("setting-voice-enabled").addEventListener("change", (e) => updateSetting("voiceEnabled", e.target.checked));
}

function setLibraryViewMode(mode) {
  libraryViewMode = mode;
  localStorage.setItem("alj_library_view", mode);
  
  const btnGrid = document.getElementById("btn-view-grid");
  const btnTable = document.getElementById("btn-view-table");
  
  if (mode === "table") {
    libraryGrid.classList.add("view-table");
    if (btnGrid) btnGrid.classList.remove("active");
    if (btnTable) btnTable.classList.add("active");
  } else {
    libraryGrid.classList.remove("view-table");
    if (btnGrid) btnGrid.classList.add("active");
    if (btnTable) btnTable.classList.remove("active");
  }
}

// --- VIEWS & NAVIGATION ---
function showLibraryView() {
  views.game.classList.remove("active");
  views.library.classList.add("active");
  navBtns.library.classList.add("active");
  navBtns.history.classList.add("hidden");
  if (audioPlayer) audioPlayer.pause();
  loadLibrary();
}

function showGameView() {
  views.library.classList.remove("active");
  views.game.classList.add("active");
  navBtns.library.classList.remove("active");
  navBtns.history.classList.remove("hidden");
}

// --- API & DATA FETCHING ---
async function loadLibrary() {
  libraryGrid.innerHTML = `
    <div class="loading-spinner">
      <div class="spinner"></div>
      <p>Cargando biblioteca...</p>
    </div>`;

  try {
    const res = await fetch(`${API_BASE}/api/books?user_id=${USER_ID}`);
    const data = await res.json();
    renderLibrary(data.books || []);
  } catch (err) {
    console.error("Error loading library:", err);
    libraryGrid.innerHTML = `<p class="error-msg">Error al conectar con la API del servidor.</p>`;
  }
}

function renderLibrary(books) {
  const libraryCount = document.getElementById("library-count");
  if (libraryCount) {
    libraryCount.textContent = `Mostrando ${books.length} libro${books.length === 1 ? '' : 's'}`;
  }
  setLibraryViewMode(libraryViewMode);

  if (books.length === 0) {
    libraryGrid.innerHTML = `
      <div class="loading-spinner">
        <p>No se encontraron libros. Copia un EPUB a la carpeta <code>Libros/</code> e impórtalo.</p>
      </div>`;
    return;
  }

  libraryGrid.innerHTML = books.map(b => {
    const langFlag = (b.language && b.language.toLowerCase().startsWith("en")) ? "🇬🇧" : "🇪🇸";
    const seriesText = b.series ? `📚 ${b.series}${b.volume ? ' #' + b.volume : ''}` : "";

    return `
    <div class="book-card">
      <div class="book-cover">
        ${b.cover_image_url 
          ? `<img src="${b.cover_image_url}?v=${Date.now()}" alt="${b.title}">` 
          : `<div class="book-cover-placeholder">📜</div>`}
        <span class="book-badge">${langFlag} ${b.total_sections} secc.</span>
      </div>
      <div class="book-info">
        <h3 class="book-title">${langFlag} ${b.title}</h3>
        <p class="book-author">${b.author}${b.year ? ' • ' + b.year : ''}</p>
        ${seriesText ? `<p class="book-series">${seriesText}</p>` : ''}
        <p class="book-desc">${b.description || "Aventura interactiva."}</p>
        
        <div class="book-progress-wrap">
          <div class="book-progress-info">
            <span>Progreso</span>
            <span>${b.progress_percent || 0}%</span>
          </div>
          <div class="progress-bar-wrap">
            <div class="progress-bar-fill" style="width: ${b.progress_percent || 0}%"></div>
          </div>
        </div>
      </div>
      <div class="book-actions">
        ${b.has_savegame ? `
          <button class="btn-primary" onclick="startGame('${b.book_id}', false)">
            <span>▶ Continuar</span>
          </button>
          <button class="btn-secondary" onclick="confirmRestartGame('${b.book_id}')" title="Reiniciar Partida">
            <span>🔄</span>
          </button>
        ` : `
          <button class="btn-primary" onclick="startGame('${b.book_id}', true)">
            <span>✨ Iniciar Partida</span>
          </button>
        `}
      </div>
    </div>
  `;
  }).join("");
}

async function confirmRestartGame(bookId) {
  if (confirm("¿Estás seguro de que deseas reiniciar esta partida desde el principio?")) {
    await startGame(bookId, true);
  }
}

async function startGame(bookId, forceNew = false) {
  currentBookId = bookId;
  showGameView();

  try {
    let res;
    if (forceNew) {
      res = await fetch(`${API_BASE}/api/games`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: USER_ID, book_id: bookId })
      });
    } else {
      res = await fetch(`${API_BASE}/api/games/${USER_ID}/${bookId}`);
    }
    const state = await res.json();
    renderGameState(state);
  } catch (err) {
    console.error("Error starting game session:", err);
  }
}

async function submitChoice(choiceId, targetNode) {
  if (!currentBookId) return;

  try {
    const res = await fetch(`${API_BASE}/api/games/${USER_ID}/${currentBookId}/choice`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ choice_id: choiceId, target_node: targetNode })
    });
    const newState = await res.json();
    renderGameState(newState);
  } catch (err) {
    console.error("Error submitting choice:", err);
  }
}

function renderGameState(state) {
  currentGameState = state;

  document.getElementById("game-book-title").textContent = state.book_title || "Librojuego";
  document.getElementById("game-progress-bar").style.width = `${state.progress_percent}%`;
  document.getElementById("game-progress-badge").textContent = `${state.progress_percent}%`;

  // Image
  const imgContainer = document.getElementById("node-image-container");
  const imgElem = document.getElementById("node-image");
  if (state.images && state.images.length > 0) {
    imgElem.src = `${state.images[0]}?v=${Date.now()}`;
    imgContainer.classList.remove("hidden");
  } else {
    imgContainer.classList.add("hidden");
  }

  // Header & Text
  document.getElementById("node-badge").textContent = state.display_number ? `Página ${state.display_number}` : (state.node_id || "");
  document.getElementById("node-title").textContent = state.title || "";
  document.getElementById("node-text").textContent = state.text || "";

  // Audio setup
  if (state.audio_url) {
    audioPlayer.src = `${state.audio_url}?v=${Date.now()}`;
    audioPlayer.playbackRate = appSettings.audioSpeed || 1.0;
    document.getElementById("btn-audio-play").classList.remove("hidden");
    if (appSettings.autoplay) {
      audioPlayer.play().catch(e => console.log("Autoplay prevented:", e));
    }
  } else {
    document.getElementById("btn-audio-play").classList.add("hidden");
  }

  // Render Choices
  const choicesList = document.getElementById("choices-list");
  if (state.choices && state.choices.length > 0) {
    choicesList.innerHTML = state.choices.map(c => `
      <div class="choice-card" onclick="submitChoice(${c.choice_id}, '${c.target_node}')">
        <span class="choice-text">[${c.choice_id}] ${c.text}</span>
        ${c.target_display_number ? `<span class="choice-page">Pág ${c.target_display_number}</span>` : ""}
      </div>
    `).join("");
  } else {
    choicesList.innerHTML = `<div class="choice-card"><span class="choice-text">🏁 FIN DE LA AVENTURA</span></div>`;
  }

  // Scroll to top of story card smoothly
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// --- AUDIO PLAYER CONTROLS ---
function toggleAudioPlay() {
  if (audioPlayer.paused) {
    audioPlayer.play();
    document.getElementById("audio-icon").textContent = "⏸";
    document.getElementById("audio-label").textContent = "Pausar Audio";
  } else {
    audioPlayer.pause();
    document.getElementById("audio-icon").textContent = "▶";
    document.getElementById("audio-label").textContent = "Escuchar Narración";
  }
}

function updateAudioProgress() {
  if (!audioPlayer.duration) return;
  const pct = (audioPlayer.currentTime / audioPlayer.duration) * 100;
  document.getElementById("audio-slider").value = pct;
  document.getElementById("audio-time-current").textContent = formatTime(audioPlayer.currentTime);
  document.getElementById("audio-time-total").textContent = formatTime(audioPlayer.duration);
}

function onAudioSeek(e) {
  if (!audioPlayer.duration) return;
  const seekTime = (e.target.value / 100) * audioPlayer.duration;
  audioPlayer.currentTime = seekTime;
}

function toggleAudioSpeed() {
  const btn = document.getElementById("btn-audio-speed");
  const speeds = [1.0, 1.25, 1.5, 2.0];
  let cur = parseFloat(btn.textContent) || 1.0;
  let nextIdx = (speeds.indexOf(cur) + 1) % speeds.length;
  let nextSpeed = speeds[nextIdx];
  btn.textContent = `${nextSpeed}x`;
  audioPlayer.playbackRate = nextSpeed;
  updateSetting("audioSpeed", nextSpeed);
}

function onAudioEnded() {
  document.getElementById("audio-icon").textContent = "▶";
  document.getElementById("audio-label").textContent = "Escuchar Narración";
}

function formatTime(secs) {
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return `${m}:${s < 10 ? "0" : ""}${s}`;
}

// --- VOICE RECORDING & WHISPER ---
function initVoiceControls() {
  const fileInput = document.getElementById("input-voice-file");
  fileInput.addEventListener("change", async (e) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      document.getElementById("voice-label").textContent = "Procesando Audio...";
      await sendVoiceToApi(file);
    }
  });
}

async function toggleVoiceRecording() {
  const btn = document.getElementById("btn-voice-record");
  const statusElem = document.getElementById("voice-status");
  const toast = document.getElementById("transcription-toast");
  const fileInput = document.getElementById("input-voice-file");

  // Check if browser allows getUserMedia (requires HTTPS or localhost)
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    // Fallback for mobile HTTP insecure context: trigger native mobile audio recorder
    fileInput.click();
    return;
  }

  if (isRecording) {
    // Stop recording
    mediaRecorder.stop();
    isRecording = false;
    btn.classList.remove("recording");
    statusElem.classList.add("hidden");
    document.getElementById("voice-label").textContent = "Procesando Audio...";
  } else {
    // Start recording
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunks = [];
      mediaRecorder = new MediaRecorder(stream);
      
      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunks.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        const blob = new Blob(audioChunks, { type: "audio/webm" });
        await sendVoiceToApi(blob);
      };

      mediaRecorder.start();
      isRecording = true;
      btn.classList.add("recording");
      statusElem.classList.remove("hidden");
      toast.classList.add("hidden");
      document.getElementById("voice-label").textContent = "Detener y Enviar";
    } catch (err) {
      console.warn("getUserMedia failed/blocked:", err);
      // Fallback to native mobile audio recorder
      fileInput.click();
    }
  }
}

async function sendVoiceToApi(audioBlob) {
  const toast = document.getElementById("transcription-toast");
  const toastText = document.getElementById("transcription-text");

  const formData = new FormData();
  formData.append("audio", audioBlob, "recording.webm");

  try {
    const res = await fetch(`${API_BASE}/api/games/${USER_ID}/${currentBookId}/voice`, {
      method: "POST",
      body: formData
    });
    const result = await res.json();
    document.getElementById("voice-label").textContent = "Responder por Voz";

    if (result.transcription) {
      toastText.textContent = `Transcripción: "${result.transcription}"`;
      toast.classList.remove("hidden");
    }

    if (result.matched) {
      renderGameState(result);
    } else {
      alert(result.message || "No se pudo hacer coincidir la voz con ninguna opción.");
    }
  } catch (err) {
    console.error("Error sending voice input:", err);
    document.getElementById("voice-label").textContent = "Responder por Voz";
  }
}

// --- SETTINGS & HISTORY DRAWER ---
function toggleSettingsModal() {
  modalSettings.classList.toggle("open");
}

async function toggleHistoryDrawer() {
  drawerHistory.classList.toggle("open");
  if (drawerHistory.classList.contains("open") && currentBookId) {
    try {
      const res = await fetch(`${API_BASE}/api/games/${USER_ID}/${currentBookId}/history`);
      const data = await res.json();
      const list = document.getElementById("history-list");
      list.innerHTML = (data.history || []).map(h => `
        <li class="history-item">
          <strong>${h.to_node_id}</strong>: ${h.choice_text || "Inicio"}
        </li>
      `).join("");
    } catch (err) {
      console.error("Error fetching history:", err);
    }
  }
}

let appSettings = {
  theme: "dark",
  fontSize: "font-md",
  autoplay: false,
  voiceEnabled: true,
  audioSpeed: 1.0
};

function setTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
}

function setFontSize(fontClass) {
  const body = document.body;
  body.classList.remove("font-sm", "font-md", "font-lg", "font-xl");
  body.classList.add(fontClass);
}

async function loadSettings() {
  const localTheme = localStorage.getItem("alj_theme") || "dark";
  const localFont = localStorage.getItem("alj_font_size") || "font-md";
  const localAutoplay = localStorage.getItem("alj_autoplay") === "true";
  const localVoice = localStorage.getItem("alj_voice") !== "false";
  const localSpeed = parseFloat(localStorage.getItem("alj_speed") || "1.0");

  appSettings = {
    theme: localTheme,
    fontSize: localFont,
    autoplay: localAutoplay,
    voiceEnabled: localVoice,
    audioSpeed: localSpeed
  };

  applySettingsToUI();

  try {
    const res = await fetch(`${API_BASE}/api/users/${USER_ID}/settings`);
    const data = await res.json();
    if (data && data.settings && Object.keys(data.settings).length > 0) {
      appSettings = { ...appSettings, ...data.settings };
      applySettingsToUI();
    }
  } catch (err) {
    console.log("Using local settings (offline/server sync skipped)");
  }
}

function applySettingsToUI() {
  setTheme(appSettings.theme);
  setFontSize(appSettings.fontSize);

  const themeEl = document.getElementById("setting-theme");
  const fontEl = document.getElementById("setting-font-size");
  const autoEl = document.getElementById("setting-autoplay");
  const voiceEl = document.getElementById("setting-voice-enabled");

  if (themeEl) themeEl.value = appSettings.theme;
  if (fontEl) fontEl.value = appSettings.fontSize;
  if (autoEl) autoEl.checked = !!appSettings.autoplay;
  if (voiceEl) voiceEl.checked = appSettings.voiceEnabled !== false;

  if (audioPlayer && appSettings.audioSpeed) {
    audioPlayer.playbackRate = appSettings.audioSpeed;
  }
}

function updateSetting(key, value) {
  appSettings[key] = value;

  if (key === "theme") localStorage.setItem("alj_theme", value);
  if (key === "fontSize") localStorage.setItem("alj_font_size", value);
  if (key === "autoplay") localStorage.setItem("alj_autoplay", value);
  if (key === "voiceEnabled") localStorage.setItem("alj_voice", value);
  if (key === "audioSpeed") localStorage.setItem("alj_speed", value);

  applySettingsToUI();

  fetch(`${API_BASE}/api/users/${USER_ID}/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ settings: appSettings })
  }).catch(() => {});
}
