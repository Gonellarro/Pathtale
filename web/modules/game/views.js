import { state } from "../state.js";
import { openAuthModal, updateAuthUI } from "../auth.js";
import { checkLastActiveGame, loadInProgressSection, loadFeaturedLibrary, loadNarratorsSection, loadFullLibrary } from "../library.js";
import { loadAdminDashboard } from "../admin.js";
import { startGame } from "./engine.js";

const views = {
  home: document.getElementById("view-home"),
  library: document.getElementById("view-library"),
  admin: document.getElementById("view-admin"),
  stats: document.getElementById("view-stats"),
  game: document.getElementById("view-game")
};

const navBtns = {
  library: document.getElementById("btn-nav-library"),
  history: document.getElementById("btn-nav-history"),
  admin: document.getElementById("btn-nav-admin")
};

const audioPlayer = document.getElementById("html-audio-player");

export function showLandingView() {
  showHomeView();
}

export function showHomeView() {
  if (audioPlayer) audioPlayer.pause();
  document.querySelectorAll(".view").forEach(v => { v.classList.remove("active"); v.classList.add("hidden"); });
  if (views.home) { views.home.classList.add("active"); views.home.classList.remove("hidden"); }
  document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
  updateAuthUI();

  const authContent = document.getElementById("authenticated-home-content");

  if (state.authToken && state.currentUser) {
    if (authContent) authContent.classList.remove("hidden");
    checkLastActiveGame(startGame);
    loadInProgressSection(startGame);
    loadFeaturedLibrary(startGame);
    loadNarratorsSection();
  } else {
    if (authContent) authContent.classList.add("hidden");
  }
}

export function showFullLibraryView() {
  if (audioPlayer) audioPlayer.pause();
  document.querySelectorAll(".view").forEach(v => { v.classList.remove("active"); v.classList.add("hidden"); });
  if (views.library) { views.library.classList.add("active"); views.library.classList.remove("hidden"); }
  document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
  if (navBtns.library) navBtns.library.classList.add("active");
  updateAuthUI();
  loadFullLibrary(startGame);
}

export function showAdminView() {
  if (!state.authToken) {
    openAuthModal();
    return;
  }

  const role = state.currentUser ? (state.currentUser.role || state.currentUser.role_name) : null;
  if (role !== "admin") {
    alert("Acceso denegado: Se requiere rol de Administrador.");
    return;
  }

  if (audioPlayer) audioPlayer.pause();
  document.querySelectorAll(".view").forEach(v => { v.classList.remove("active"); v.classList.add("hidden"); });
  if (views.admin) { views.admin.classList.add("active"); views.admin.classList.remove("hidden"); }

  document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
  if (navBtns.admin) navBtns.admin.classList.add("active");

  updateAuthUI();
  loadAdminDashboard();
}

export function showGameView() {
  if (!state.authToken || !state.currentUser) {
    openAuthModal();
    return;
  }
  document.querySelectorAll(".view").forEach(v => { v.classList.remove("active"); v.classList.add("hidden"); });
  if (views.game) { views.game.classList.add("active"); views.game.classList.remove("hidden"); }
  document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
  updateAuthUI();
}
