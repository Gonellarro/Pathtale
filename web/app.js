/**
 * PathTale Narrative Game Engine - Main Application Entrypoint (ES Module)
 */

import { state } from "./modules/state.js";
import { initAuthControls } from "./modules/auth.js";
import { loadSettings, updateSetting, toggleSettingsModal } from "./modules/settings.js";
import { 
  toggleAudioPlay, playOptionsAudio, onAudioSeek, toggleAudioSpeed, 
  updateAudioProgress, onAudioPlay, onAudioPause, onAudioEnded 
} from "./modules/audio.js";
import { setLibraryViewMode, confirmRestartGame } from "./modules/library.js";
import { 
  showHomeView, showFullLibraryView, showAdminView, showGameView, startGame, submitChoice, 
  jumpToSection, goBackHistory, initVoiceControls, toggleVoiceRecording, 
  toggleHistoryDrawer 
} from "./modules/game.js";
import { showStatsView } from "./modules/stats.js";

const audioPlayer = document.getElementById("html-audio-player");
const navBtns = {
  library: document.getElementById("btn-nav-library"),
  admin: document.getElementById("btn-nav-admin"),
  stats: document.getElementById("btn-nav-stats"),
  history: document.getElementById("btn-nav-history")
};

document.addEventListener("DOMContentLoaded", () => {
  initEventListeners();
  initAuthControls(showHomeView, showHomeView);
  loadSettings();
  showHomeView();
});

function initEventListeners() {
  initVoiceControls();

  // Navigation
  const navBrand = document.getElementById("nav-brand");
  if (navBrand) navBrand.addEventListener("click", showHomeView);
  if (navBtns.library) navBtns.library.addEventListener("click", showFullLibraryView);
  if (navBtns.stats) navBtns.stats.addEventListener("click", showStatsView);
  if (navBtns.admin) navBtns.admin.addEventListener("click", showAdminView);
  const btnProfile = document.getElementById("btn-nav-profile");
  if (btnProfile) btnProfile.addEventListener("click", toggleSettingsModal);
  if (navBtns.history) navBtns.history.addEventListener("click", toggleHistoryDrawer);

  // View mode toggles for full library view
  const btnViewGrid = document.getElementById("btn-view-grid");
  const btnViewTable = document.getElementById("btn-view-table");
  if (btnViewGrid) btnViewGrid.onclick = () => setLibraryViewMode("grid", startGame);
  if (btnViewTable) btnViewTable.onclick = () => setLibraryViewMode("table", startGame);

  // Game Toolbar
  const btnGameBack = document.getElementById("btn-game-back");
  if (btnGameBack) btnGameBack.addEventListener("click", showHomeView);

  const btnGameRestart = document.getElementById("btn-game-restart");
  if (btnGameRestart) {
    btnGameRestart.addEventListener("click", () => {
      if (state.currentBookId) confirmRestartGame(state.currentBookId, startGame);
    });
  }

  const btnHistoryBack = document.getElementById("btn-game-history-back");
  if (btnHistoryBack) btnHistoryBack.addEventListener("click", goBackHistory);

  const btnGoto = document.getElementById("btn-game-goto");
  const inputGoto = document.getElementById("input-goto-section");
  if (btnGoto && inputGoto) {
    const handleGoto = () => {
      const val = inputGoto.value.trim();
      if (val) jumpToSection(val);
    };
    btnGoto.addEventListener("click", handleGoto);
    inputGoto.addEventListener("keydown", (e) => {
      if (e.key === "Enter") handleGoto();
    });
  }

  // Modals & Drawers
  const btnCloseSettings = document.getElementById("btn-close-settings");
  if (btnCloseSettings) btnCloseSettings.addEventListener("click", toggleSettingsModal);

  const btnCloseHistory = document.getElementById("btn-close-history");
  if (btnCloseHistory) btnCloseHistory.addEventListener("click", toggleHistoryDrawer);

  // Library View Toggle
  const btnGrid = document.getElementById("btn-view-grid");
  const btnTable = document.getElementById("btn-view-table");
  if (btnGrid && btnTable) {
    btnGrid.addEventListener("click", () => setLibraryViewMode("grid"));
    btnTable.addEventListener("click", () => setLibraryViewMode("table"));
  }

  // Library Event Delegation (Card Clicks)
  const libraryGrid = document.getElementById("library-grid");
  if (libraryGrid) {
    libraryGrid.addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-action]");
      if (!btn) return;
      const action = btn.getAttribute("data-action");
      const bookId = btn.getAttribute("data-book-id");

      if (action === "continue") {
        startGame(bookId, false);
      } else if (action === "restart") {
        confirmRestartGame(bookId, startGame);
      } else if (action === "start") {
        startGame(bookId, true);
      }
    });
  }

  // Story Choice Delegation
  const choicesList = document.getElementById("choices-list");
  if (choicesList) {
    choicesList.addEventListener("click", (e) => {
      const btn = e.target.closest(".btn-choice");
      if (!btn) return;
      const choiceId = parseInt(btn.getAttribute("data-choice-id"), 10);
      const targetNode = btn.getAttribute("data-target-node");
      submitChoice(choiceId, targetNode);
    });
  }

  // Audio Controls
  const btnAudioPlay = document.getElementById("btn-audio-play");
  if (btnAudioPlay) btnAudioPlay.addEventListener("click", toggleAudioPlay);

  const btnOpt = document.getElementById("btn-audio-options");
  if (btnOpt) btnOpt.addEventListener("click", playOptionsAudio);

  const audioSlider = document.getElementById("audio-slider");
  if (audioSlider) audioSlider.addEventListener("input", onAudioSeek);

  const btnSpeed = document.getElementById("btn-audio-speed");
  if (btnSpeed) btnSpeed.addEventListener("click", toggleAudioSpeed);

  if (audioPlayer) {
    audioPlayer.addEventListener("timeupdate", updateAudioProgress);
    audioPlayer.addEventListener("play", onAudioPlay);
    audioPlayer.addEventListener("pause", onAudioPause);
    audioPlayer.addEventListener("ended", onAudioEnded);
  }

  // Voice Controls
  const btnVoiceRecord = document.getElementById("btn-voice-record");
  if (btnVoiceRecord) btnVoiceRecord.addEventListener("click", toggleVoiceRecording);

  // Settings Controls
  const selTheme = document.getElementById("setting-theme");
  if (selTheme) selTheme.addEventListener("change", (e) => updateSetting("theme", e.target.value));

  const selFont = document.getElementById("setting-font-size");
  if (selFont) selFont.addEventListener("change", (e) => updateSetting("fontSize", e.target.value));

  const chkAuto = document.getElementById("setting-autoplay");
  if (chkAuto) chkAuto.addEventListener("change", (e) => updateSetting("autoplay", e.target.checked));

  const chkVoice = document.getElementById("setting-voice-enabled");
  if (chkVoice) chkVoice.addEventListener("change", (e) => updateSetting("voiceEnabled", e.target.checked));

  // Forgot Password Link
  const linkForgot = document.getElementById("link-forgot-password");
  if (linkForgot) {
    linkForgot.addEventListener("click", (e) => {
      e.preventDefault();
      alert("Para restablecer tu contraseña, contacta con el administrador del sistema.");
    });
  }
}
