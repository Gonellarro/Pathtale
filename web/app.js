/**
 * PathTale Narrative Game Engine - PWA Frontend Client
 */

const API_BASE = "";

// Auth & Session State
let authToken = localStorage.getItem("alj_token") || null;
let currentUser = JSON.parse(localStorage.getItem("alj_user") || "null");
let authMode = "login"; // 'login' or 'register'
let landingAuthMode = "login";

// Game State
let currentBookId = null;
let currentGameState = null;
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;
let libraryViewMode = localStorage.getItem("alj_library_view") || "grid";

// Helper for authenticated API calls
function authFetch(url, options = {}) {
  const headers = options.headers || {};
  if (authToken) {
    headers["Authorization"] = `Bearer ${authToken}`;
  }
  return fetch(url, { ...options, headers });
}

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
  initAuthControls();
  loadSettings();
  showLibraryView();
});

function initEventListeners() {
  initVoiceControls();
  // Navigation
  document.getElementById("nav-brand").addEventListener("click", showLibraryView);
  if (navBtns.library) navBtns.library.addEventListener("click", showLibraryView);
  const btnProfile = document.getElementById("btn-nav-profile");
  if (btnProfile) btnProfile.addEventListener("click", toggleSettingsModal);
  if (navBtns.history) navBtns.history.addEventListener("click", toggleHistoryDrawer);

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
  const btnOpt = document.getElementById("btn-audio-options");
  if (btnOpt) btnOpt.addEventListener("click", playOptionsAudio);
  document.getElementById("audio-slider").addEventListener("input", onAudioSeek);
  document.getElementById("btn-audio-speed").addEventListener("click", toggleAudioSpeed);

  audioPlayer.addEventListener("timeupdate", updateAudioProgress);
  audioPlayer.addEventListener("play", onAudioPlay);
  audioPlayer.addEventListener("pause", onAudioPause);
  audioPlayer.addEventListener("ended", onAudioEnded);

  // Voice Controls
  document.getElementById("btn-voice-record").addEventListener("click", toggleVoiceRecording);

  // Settings Controls
  document.getElementById("setting-theme").addEventListener("change", (e) => updateSetting("theme", e.target.value));
  document.getElementById("setting-font-size").addEventListener("change", (e) => updateSetting("fontSize", e.target.value));
  document.getElementById("setting-autoplay").addEventListener("change", (e) => updateSetting("autoplay", e.target.checked));
  document.getElementById("setting-voice-enabled").addEventListener("change", (e) => updateSetting("voiceEnabled", e.target.checked));

  // Forgot password handler
  const linkForgot = document.getElementById("link-forgot-password");
  if (linkForgot) {
    linkForgot.addEventListener("click", (e) => {
      e.preventDefault();
      alert("Para restablecer tu contraseña, contacta con el administrador del sistema.");
    });
  }
}

// --- AUTHENTICATION & USER PROFILE ---

function initAuthControls() {
  const btnLogin = document.getElementById("btn-nav-login");
  const btnCloseAuth = document.getElementById("btn-close-auth");
  const tabLogin = document.getElementById("tab-auth-login");
  const tabRegister = document.getElementById("tab-auth-register");
  const authForm = document.getElementById("auth-form");
  const btnLogout = document.getElementById("btn-logout");

  // Landing Auth Elements
  const tabLandingLogin = document.getElementById("tab-landing-login");
  const tabLandingRegister = document.getElementById("tab-landing-register");
  const landingForm = document.getElementById("landing-auth-form");

  if (btnLogin) btnLogin.addEventListener("click", openAuthModal);
  if (btnCloseAuth) btnCloseAuth.addEventListener("click", closeAuthModal);
  
  if (tabLogin) tabLogin.addEventListener("click", () => setAuthMode("login"));
  if (tabRegister) tabRegister.addEventListener("click", () => setAuthMode("register"));
  if (authForm) authForm.addEventListener("submit", handleAuthSubmit);

  if (tabLandingLogin) tabLandingLogin.addEventListener("click", () => setLandingAuthMode("login"));
  if (tabLandingRegister) tabLandingRegister.addEventListener("click", () => setLandingAuthMode("register"));
  if (landingForm) landingForm.addEventListener("submit", handleLandingAuthSubmit);

  if (btnLogout) btnLogout.addEventListener("click", handleLogout);

  updateAuthUI();
  checkAuthStatus();
}

function updateAuthUI() {
  const btnLogin = document.getElementById("btn-nav-login");
  const btnNavLib = document.getElementById("btn-nav-library");
  const btnNavProf = document.getElementById("btn-nav-profile");
  const profileName = document.getElementById("profile-user-name");
  const profileSub = document.getElementById("profile-user-sub");
  const btnLogout = document.getElementById("btn-logout");

  const landingTagline = document.getElementById("landing-tagline");
  const libraryToolbar = document.getElementById("library-toolbar");
  const libraryGrid = document.getElementById("library-grid");

  if (currentUser && authToken) {
    if (btnNavLib) btnNavLib.classList.remove("hidden");
    if (btnNavProf) btnNavProf.classList.remove("hidden");
    if (btnLogin) btnLogin.classList.add("hidden");

    if (landingTagline) landingTagline.classList.add("hidden");
    if (libraryToolbar) libraryToolbar.classList.remove("hidden");
    if (libraryGrid) libraryGrid.classList.remove("hidden");

    if (profileName) profileName.textContent = currentUser.first_name || currentUser.username;
    if (profileSub) profileSub.textContent = `Cuenta: @${currentUser.username}`;
    if (btnLogout) btnLogout.classList.remove("hidden");
  } else {
    if (btnNavLib) btnNavLib.classList.add("hidden");
    if (btnNavProf) btnNavProf.classList.add("hidden");
    if (btnLogin) btnLogin.classList.remove("hidden");

    if (landingTagline) landingTagline.classList.remove("hidden");
    if (libraryToolbar) libraryToolbar.classList.add("hidden");
    if (libraryGrid) libraryGrid.classList.add("hidden");

    if (profileName) profileName.textContent = "Invitado";
    if (profileSub) profileSub.textContent = "Modo local / No registrado";
    if (btnLogout) btnLogout.classList.add("hidden");
  }
}

async function checkAuthStatus() {
  if (!authToken) return;
  try {
    const res = await authFetch(`${API_BASE}/api/auth/me`);
    const data = await res.json();
    if (data.authenticated && data.user) {
      currentUser = data.user;
      localStorage.setItem("alj_user", JSON.stringify(currentUser));
      updateAuthUI();
      if (data.stats) {
        const booksEl = document.getElementById("stat-books");
        const decEl = document.getElementById("stat-decisions");
        if (booksEl) booksEl.textContent = data.stats.books_started || 0;
        if (decEl) decEl.textContent = data.stats.decisions_made || 0;
      }
    } else {
      handleLogout();
    }
  } catch (err) {
    console.log("Could not refresh auth status:", err);
  }
}

function openAuthModal() {
  if (currentUser && authToken) {
    toggleSettingsModal();
    return;
  }
  setAuthMode("login");
  const modalAuth = document.getElementById("modal-auth");
  if (modalAuth) modalAuth.classList.add("open");
}

function closeAuthModal() {
  const modalAuth = document.getElementById("modal-auth");
  if (modalAuth) modalAuth.classList.remove("open");
  const errEl = document.getElementById("auth-error-msg");
  if (errEl) errEl.classList.add("hidden");
}

function setAuthMode(mode) {
  authMode = mode;
  const tabLogin = document.getElementById("tab-auth-login");
  const tabRegister = document.getElementById("tab-auth-register");
  const modalTitle = document.getElementById("auth-modal-title");
  const submitBtn = document.getElementById("btn-auth-submit");
  const errEl = document.getElementById("auth-error-msg");

  if (errEl) errEl.classList.add("hidden");

  if (mode === "register") {
    if (tabLogin) tabLogin.classList.remove("active");
    if (tabRegister) tabRegister.classList.add("active");
    if (modalTitle) modalTitle.textContent = "Crear nueva cuenta";
    if (submitBtn) submitBtn.textContent = "Registrarse y Entrar";
  } else {
    if (tabLogin) tabLogin.classList.add("active");
    if (tabRegister) tabRegister.classList.remove("active");
    if (modalTitle) modalTitle.textContent = "Iniciar Sesión";
    if (submitBtn) submitBtn.textContent = "Iniciar Sesión";
  }
}

function setLandingAuthMode(mode) {
  landingAuthMode = mode;
  const tabLogin = document.getElementById("tab-landing-login");
  const tabRegister = document.getElementById("tab-landing-register");
  const submitBtn = document.getElementById("btn-landing-submit");
  const errEl = document.getElementById("landing-auth-error");

  if (errEl) errEl.classList.add("hidden");

  if (mode === "register") {
    if (tabLogin) tabLogin.classList.remove("active");
    if (tabRegister) tabRegister.classList.add("active");
    if (submitBtn) submitBtn.textContent = "Crear Mi Cuenta y Entrar";
  } else {
    if (tabLogin) tabLogin.classList.add("active");
    if (tabRegister) tabRegister.classList.remove("active");
    if (submitBtn) submitBtn.textContent = "Entrar a la Aventura";
  }
}

async function handleLandingAuthSubmit(e) {
  if (e) e.preventDefault();
  const usernameInput = document.getElementById("landing-username");
  const passwordInput = document.getElementById("landing-password");
  const errEl = document.getElementById("landing-auth-error");
  const submitBtn = document.getElementById("btn-landing-submit");

  const username = usernameInput ? usernameInput.value.trim() : "";
  const password = passwordInput ? passwordInput.value : "";

  if (!username || !password) return;

  if (errEl) errEl.classList.add("hidden");
  if (submitBtn) submitBtn.disabled = true;

  const endpoint = landingAuthMode === "register" ? "/api/auth/register" : "/api/auth/login";

  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });
    const data = await res.json();

    if (!res.ok || data.status !== "success") {
      throw new Error(data.detail || "Error de autenticación");
    }

    authToken = data.user.token;
    currentUser = { user_id: data.user.user_id, username: data.user.username, first_name: data.user.first_name };

    localStorage.setItem("alj_token", authToken);
    localStorage.setItem("alj_user", JSON.stringify(currentUser));

    updateAuthUI();
    showLibraryView();
    checkAuthStatus();
  } catch (err) {
    if (errEl) {
      errEl.textContent = err.message || "Error al autenticar";
      errEl.classList.remove("hidden");
    }
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
}

async function handleAuthSubmit(e) {
  if (e) e.preventDefault();
  const usernameInput = document.getElementById("auth-username");
  const passwordInput = document.getElementById("auth-password");
  const errEl = document.getElementById("auth-error-msg");
  const submitBtn = document.getElementById("btn-auth-submit");

  const username = usernameInput ? usernameInput.value.trim() : "";
  const password = passwordInput ? passwordInput.value : "";

  if (!username || !password) return;

  if (errEl) errEl.classList.add("hidden");
  if (submitBtn) submitBtn.disabled = true;

  const endpoint = authMode === "register" ? "/api/auth/register" : "/api/auth/login";

  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });
    const data = await res.json();

    if (!res.ok || data.status !== "success") {
      throw new Error(data.detail || "Error de autenticación");
    }

    authToken = data.user.token;
    currentUser = { user_id: data.user.user_id, username: data.user.username, first_name: data.user.first_name };

    localStorage.setItem("alj_token", authToken);
    localStorage.setItem("alj_user", JSON.stringify(currentUser));

    updateAuthUI();
    closeAuthModal();
    showLibraryView();
    checkAuthStatus();
  } catch (err) {
    if (errEl) {
      errEl.textContent = err.message || "Error al iniciar sesión";
      errEl.classList.remove("hidden");
    }
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
}

async function handleLogout() {
  if (authToken) {
    try {
      await authFetch(`${API_BASE}/api/auth/logout`, { method: "POST" });
    } catch (e) {}
  }
  authToken = null;
  currentUser = null;
  localStorage.removeItem("alj_token");
  localStorage.removeItem("alj_user");
  updateAuthUI();
  const modalSettings = document.getElementById("modal-settings");
  if (modalSettings) modalSettings.classList.remove("open");
  showLandingView();
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

// --- API & DATA FETCHING ---
async function loadLibrary() {
  if (!authToken || !currentUser) {
    showLandingView();
    return;
  }

  libraryGrid.innerHTML = `
    <div class="loading-spinner">
      <div class="spinner"></div>
      <p>Cargando biblioteca...</p>
    </div>`;

  try {
    const res = await authFetch(`${API_BASE}/api/books`);
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
  if (!authToken || !currentUser) {
    openAuthModal();
    return;
  }
  currentBookId = bookId;
  showGameView();

  try {
    let res;
    if (forceNew) {
      res = await authFetch(`${API_BASE}/api/games`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ book_id: bookId })
      });
    } else {
      res = await authFetch(`${API_BASE}/api/games/1/${bookId}`);
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
    const res = await authFetch(`${API_BASE}/api/games/1/${currentBookId}/choice`, {
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

let currentAudioType = "narrative";

function renderGameState(state) {
  currentGameState = state;
  currentAudioType = "narrative";

  document.getElementById("game-book-title").textContent = state.book_title || "Librojuego";
  document.getElementById("game-progress-bar").style.width = `${state.progress_percent || 0}%`;
  document.getElementById("game-progress-badge").textContent = `${state.progress_percent || 0}%`;

  const nodeImgContainer = document.getElementById("node-image-container");
  const nodeImg = document.getElementById("node-image");
  if (state.images && state.images.length > 0) {
    nodeImg.src = `${state.images[0]}?v=${Date.now()}`;
    nodeImgContainer.classList.remove("hidden");
  } else {
    nodeImgContainer.classList.add("hidden");
  }

  const badgeText = state.display_number ? `Sección ${state.display_number}` : state.node_id;
  document.getElementById("node-badge").textContent = badgeText;
  document.getElementById("node-title").textContent = state.title || badgeText;

  const nodeTextContainer = document.getElementById("node-text");
  const paragraphs = (state.text || "").split("\n\n").filter(p => p.trim());
  nodeTextContainer.innerHTML = paragraphs.map(p => `<p>${escapeHtml(p)}</p>`).join("");

  const btnOpt = document.getElementById("btn-audio-options");
  if (btnOpt) {
    if (state.audio_options_url) {
      btnOpt.classList.remove("hidden");
    } else {
      btnOpt.classList.add("hidden");
    }
  }

  if (state.audio_url) {
    audioPlayer.src = `${state.audio_url}?v=${Date.now()}`;
    if (appSettings.autoplay) {
      audioPlayer.play().catch(() => {});
    }
  }

  renderChoices(state.choices || []);
  renderHistoryDrawer();
}

function renderChoices(choices) {
  const choicesList = document.getElementById("choices-list");
  
  if (choices.length === 0) {
    choicesList.innerHTML = `
      <div class="end-game-card">
        <h4>Fin de esta aventura</h4>
        <p>Has alcanzado el final de este camino. Puedes reiniciar o probar otro libro.</p>
        <button class="btn-primary" onclick="showLibraryView()">Volver a la Biblioteca</button>
      </div>`;
    return;
  }

  choicesList.innerHTML = choices.map(c => `
    <button class="btn-choice" onclick="submitChoice(${c.choice_id}, '${c.target_node}')">
      <span class="choice-num">${c.choice_id}</span>
      <span class="choice-text">${escapeHtml(c.text)}</span>
      <span class="choice-arrow">→</span>
    </button>
  `).join("");
}

// --- AUDIO PLAYER CONTROLS ---

function toggleAudioPlay() {
  if (audioPlayer.paused) {
    if (!audioPlayer.src && currentGameState) {
      currentAudioType = "narrative";
      audioPlayer.src = `${currentGameState.audio_url}?v=${Date.now()}`;
    }
    audioPlayer.play().catch(err => console.log("Audio play error:", err));
  } else {
    audioPlayer.pause();
  }
}

function playOptionsAudio() {
  if (!currentGameState || !currentGameState.audio_options_url) return;
  currentAudioType = "options";
  audioPlayer.src = `${currentGameState.audio_options_url}?v=${Date.now()}`;
  audioPlayer.play().catch(err => console.log("Options play error:", err));
}

function onAudioPlay() {
  const label = document.getElementById("audio-label");
  const icon = document.getElementById("audio-icon");
  const btn = document.getElementById("btn-audio-play");
  if (icon) icon.textContent = "⏸";
  if (label) {
    label.textContent = (currentAudioType === "options") ? "Pausar Opciones" : "Pausar Narración";
  }
  if (btn) btn.classList.add("playing");
}

function onAudioPause() {
  const label = document.getElementById("audio-label");
  const icon = document.getElementById("audio-icon");
  const btn = document.getElementById("btn-audio-play");
  if (icon) icon.textContent = "▶";
  if (label) label.textContent = "Escuchar Narración";
  if (btn) btn.classList.remove("playing");
}

function onAudioEnded() {
  if (currentAudioType === "narrative" && currentGameState && currentGameState.audio_options_url) {
    currentAudioType = "options";
    audioPlayer.src = `${currentGameState.audio_options_url}?v=${Date.now()}`;
    audioPlayer.play().catch(() => {
      resetAudioToNarrative();
    });
  } else {
    resetAudioToNarrative();
  }
}

function resetAudioToNarrative() {
  currentAudioType = "narrative";
  if (currentGameState && currentGameState.audio_url) {
    audioPlayer.src = `${currentGameState.audio_url}?v=${Date.now()}`;
  }
  onAudioPause();
}

function updateAudioProgress() {
  if (!audioPlayer.duration) return;
  const current = audioPlayer.currentTime;
  const total = audioPlayer.duration;
  const pct = (current / total) * 100;

  document.getElementById("audio-slider").value = pct;
  document.getElementById("audio-time-current").textContent = formatTime(current);
  document.getElementById("audio-time-total").textContent = formatTime(total);
}

function onAudioSeek(e) {
  if (!audioPlayer.duration) return;
  const pct = e.target.value;
  audioPlayer.currentTime = (pct / 100) * audioPlayer.duration;
}

function toggleAudioSpeed() {
  const btn = document.getElementById("btn-audio-speed");
  const speeds = [1.0, 1.25, 1.5, 2.0];
  let nextIdx = (speeds.indexOf(audioPlayer.playbackRate) + 1) % speeds.length;
  let newSpeed = speeds[nextIdx];

  audioPlayer.playbackRate = newSpeed;
  btn.textContent = `${newSpeed.toFixed(1)}x`;
  updateSetting("audioSpeed", newSpeed);
}

// --- VOICE RECOGNITION (WHISPER) ---

function initVoiceControls() {
  const fileInput = document.getElementById("input-voice-file");
  if (fileInput) {
    fileInput.addEventListener("change", async (e) => {
      const file = e.target.files[0];
      if (file) await uploadAndTranscribeAudio(file);
    });
  }
}

async function toggleVoiceRecording() {
  if (isRecording) {
    stopRecording();
  } else {
    await startRecording();
  }
}

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks = [];
    mediaRecorder = new MediaRecorder(stream);

    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) audioChunks.push(event.data);
    };

    mediaRecorder.onstop = async () => {
      const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
      const file = new File([audioBlob], "voice_input.webm", { type: "audio/webm" });
      await uploadAndTranscribeAudio(file);
      stream.getTracks().forEach(t => t.stop());
    };

    mediaRecorder.start();
    isRecording = true;
    updateVoiceUI(true);
  } catch (err) {
    console.warn("Microphone API unavailable, opening native audio picker:", err);
    const fileInput = document.getElementById("input-voice-file");
    if (fileInput) fileInput.click();
  }
}

function stopRecording() {
  if (mediaRecorder && isRecording) {
    mediaRecorder.stop();
    isRecording = false;
    updateVoiceUI(false);
  }
}

function updateVoiceUI(recording) {
  const btn = document.getElementById("btn-voice-record");
  const status = document.getElementById("voice-status");
  const label = document.getElementById("voice-label");

  if (recording) {
    btn.classList.add("recording");
    status.classList.remove("hidden");
    label.textContent = "Detener Grabación";
  } else {
    btn.classList.remove("recording");
    status.classList.add("hidden");
    label.textContent = "Responder por Voz";
  }
}

async function uploadAndTranscribeAudio(file) {
  const toast = document.getElementById("transcription-toast");
  const textEl = document.getElementById("transcription-text");
  
  toast.classList.remove("hidden");
  textEl.textContent = "Procesando voz con Whisper AI...";

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await authFetch(`${API_BASE}/api/voice/transcribe`, {
      method: "POST",
      body: formData
    });

    const data = await res.json();
    if (data.status === "success" && data.text) {
      textEl.textContent = `Voz reconocida: "${data.text}"`;
      setTimeout(() => toast.classList.add("hidden"), 3000);
      await submitChoice(null, null, data.text);
    } else {
      textEl.textContent = "No se pudo interpretar el audio.";
      setTimeout(() => toast.classList.add("hidden"), 3000);
    }
  } catch (err) {
    console.error("Transcribe error:", err);
    textEl.textContent = "Error de conexión al transcribir voz.";
    setTimeout(() => toast.classList.add("hidden"), 3000);
  }
}

// --- HISTORY DRAWER & VIEWS ---

function showLandingView() {
  showLibraryView();
}

function showLibraryView() {
  audioPlayer.pause();
  views.game.classList.remove("active");
  views.library.classList.add("active");
  if (navBtns.library) navBtns.library.classList.add("active");
  updateAuthUI();
  if (authToken && currentUser) {
    loadLibrary();
  }
}

function showGameView() {
  if (!authToken || !currentUser) {
    openAuthModal();
    return;
  }
  views.library.classList.remove("active");
  views.game.classList.add("active");
  if (navBtns.library) navBtns.library.classList.remove("active");
  updateAuthUI();
}

function toggleSettingsModal() {
  checkAuthStatus();
  modalSettings.classList.toggle("open");
}

function toggleHistoryDrawer() {
  drawerHistory.classList.toggle("open");
  if (drawerHistory.classList.contains("open")) {
    renderHistoryDrawer();
  }
}

async function renderHistoryDrawer() {
  if (!currentBookId) return;
  const listEl = document.getElementById("history-list");
  
  try {
    const res = await authFetch(`${API_BASE}/api/games/1/${encodeURIComponent(currentBookId)}/history`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const history = await res.json();
    
    if (!Array.isArray(history) || history.length === 0) {
      listEl.innerHTML = `<li class="history-item"><p>Aún no has tomado ninguna decisión en este libro.</p></li>`;
      return;
    }

    listEl.innerHTML = history.map((item, idx) => `
      <li class="history-item">
        <span class="history-step">Paso ${history.length - idx}</span>
        <p class="history-choice">Elegiste: <strong>${escapeHtml(item.choice_text || item.to_node_id)}</strong></p>
        <span class="history-time">${formatTimeAgo(item.created_at)}</span>
      </li>
    `).join("");
  } catch (err) {
    console.error("History fetch error:", err);
    if (listEl) listEl.innerHTML = `<li class="history-item"><p>No se pudo obtener el historial.</p></li>`;
  }
}

// --- SETTINGS & HELPERS ---

let appSettings = {
  theme: "pathtale",
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
  const localTheme = localStorage.getItem("alj_theme") || "pathtale";
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

  if (authToken) {
    try {
      const res = await authFetch(`${API_BASE}/api/users/1/settings`);
      const data = await res.json();
      if (data && data.settings && Object.keys(data.settings).length > 0) {
        appSettings = { ...appSettings, ...data.settings };
        applySettingsToUI();
      }
    } catch (err) {
      console.log("Using local settings (offline/server sync skipped)");
    }
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

  if (authToken) {
    authFetch(`${API_BASE}/api/users/1/settings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ settings: appSettings })
    }).catch(() => {});
  }
}

function escapeHtml(str) {
  if (!str) return "";
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function formatTime(seconds) {
  if (isNaN(seconds)) return "0:00";
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
}

function formatTimeAgo(isoString) {
  if (!isoString) return "";
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return "Hace un momento";
  if (diffMins < 60) return `Hace ${diffMins} min`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `Hace ${diffHours} h`;
  return date.toLocaleDateString();
}
