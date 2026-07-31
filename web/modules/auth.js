/**
 * Authentication & Profile Module for PathTale
 */

import { state, authFetch, API_BASE } from "./state.js";
import { toggleSettingsModal } from "./settings.js";

export function initAuthControls(onAuthSuccess, onLogoutSuccess) {
  const btnLogin = document.getElementById("btn-nav-login");
  const btnCloseAuth = document.getElementById("btn-close-auth");
  const tabLogin = document.getElementById("tab-auth-login");
  const tabRegister = document.getElementById("tab-auth-register");
  const authForm = document.getElementById("auth-form");
  const btnLogout = document.getElementById("btn-logout");

  if (btnLogin) btnLogin.addEventListener("click", openAuthModal);
  if (btnCloseAuth) btnCloseAuth.addEventListener("click", closeAuthModal);
  
  if (tabLogin) tabLogin.addEventListener("click", () => setAuthMode("login"));
  if (tabRegister) tabRegister.addEventListener("click", () => setAuthMode("register"));
  if (authForm) authForm.addEventListener("submit", (e) => handleAuthSubmit(e, onAuthSuccess));

  if (btnLogout) btnLogout.addEventListener("click", () => handleLogout(onLogoutSuccess));

  updateAuthUI();
  checkAuthStatus();
}

export function updateAuthUI() {
  const btnLogin = document.getElementById("btn-nav-login");
  const btnNavLib = document.getElementById("btn-nav-library");
  const btnNavProf = document.getElementById("btn-nav-profile");
  const btnNavStats = document.getElementById("btn-nav-stats");
  const btnNavAdmin = document.getElementById("btn-nav-admin");
  const profileName = document.getElementById("profile-user-name");
  const profileSub = document.getElementById("profile-user-sub");
  const btnLogout = document.getElementById("btn-logout");

  const landingTagline = document.getElementById("landing-tagline");
  const landingPublicContent = document.getElementById("landing-public-content");
  const authenticatedHomeContent = document.getElementById("authenticated-home-content");
  const libraryToolbar = document.getElementById("library-toolbar");
  const libraryGrid = document.getElementById("library-grid");

  const role = state.currentUser ? (state.currentUser.role || state.currentUser.role_name) : null;
  const isAdmin = role === "admin";

  if (state.currentUser && state.authToken) {
    if (btnNavLib) btnNavLib.classList.remove("hidden");
    if (btnNavProf) btnNavProf.classList.remove("hidden");
    if (btnNavStats) btnNavStats.classList.remove("hidden");
    if (btnNavAdmin) {
      if (isAdmin) btnNavAdmin.classList.remove("hidden");
      else btnNavAdmin.classList.add("hidden");
    }
    if (btnLogin) btnLogin.classList.add("hidden");

    if (landingTagline) landingTagline.classList.add("hidden");
    if (landingPublicContent) landingPublicContent.classList.add("hidden");
    if (authenticatedHomeContent) authenticatedHomeContent.classList.remove("hidden");
    if (libraryToolbar) libraryToolbar.classList.remove("hidden");
    if (libraryGrid) libraryGrid.classList.remove("hidden");

    if (profileName) profileName.textContent = state.currentUser.first_name || state.currentUser.username;
    if (profileSub) profileSub.textContent = `Cuenta: @${state.currentUser.username} ${isAdmin ? '(⚡ Admin)' : ''}`;
    if (btnLogout) btnLogout.classList.remove("hidden");
  } else {
    if (btnNavLib) btnNavLib.classList.add("hidden");
    if (btnNavProf) btnNavProf.classList.add("hidden");
    if (btnNavStats) btnNavStats.classList.add("hidden");
    if (btnNavAdmin) btnNavAdmin.classList.add("hidden");
    if (btnLogin) btnLogin.classList.remove("hidden");

    if (landingTagline) landingTagline.classList.remove("hidden");
    if (landingPublicContent) landingPublicContent.classList.remove("hidden");
    if (authenticatedHomeContent) authenticatedHomeContent.classList.add("hidden");
    if (libraryToolbar) libraryToolbar.classList.add("hidden");
    if (libraryGrid) libraryGrid.classList.add("hidden");

    if (profileName) profileName.textContent = "Invitado";
    if (profileSub) profileSub.textContent = "Modo local / No registrado";
    if (btnLogout) btnLogout.classList.add("hidden");
  }
}

export async function checkAuthStatus() {
  if (!state.authToken) return;
  try {
    const res = await authFetch(`${API_BASE}/api/auth/me`);
    const data = await res.json();
    if (data.authenticated && data.user) {
      state.currentUser = data.user;
      localStorage.setItem("alj_user", JSON.stringify(state.currentUser));
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

export function openAuthModal() {
  if (state.currentUser && state.authToken) {
    toggleSettingsModal();
    return;
  }
  setAuthMode("login");
  const modalAuth = document.getElementById("modal-auth");
  if (modalAuth) modalAuth.classList.add("open");
}

export function closeAuthModal() {
  const modalAuth = document.getElementById("modal-auth");
  if (modalAuth) modalAuth.classList.remove("open");
  const errEl = document.getElementById("auth-error-msg");
  if (errEl) errEl.classList.add("hidden");
}

// Single toggle flag to enable/disable public user registration
export const ENABLE_PUBLIC_REGISTRATION = false;

export function setAuthMode(mode) {
  state.authMode = mode;
  const tabLogin = document.getElementById("tab-auth-login");
  const tabRegister = document.getElementById("tab-auth-register");
  const modalTitle = document.getElementById("auth-modal-title");
  const submitBtn = document.getElementById("btn-auth-submit");
  const errEl = document.getElementById("auth-error-msg");
  const usernameInput = document.getElementById("auth-username");
  const passwordInput = document.getElementById("auth-password");

  if (errEl) {
    errEl.classList.add("hidden");
    errEl.classList.remove("auth-notice");
  }

  if (mode === "register") {
    if (tabLogin) tabLogin.classList.remove("active");
    if (tabRegister) tabRegister.classList.add("active");
    if (modalTitle) modalTitle.textContent = "Crear nueva cuenta";

    if (!ENABLE_PUBLIC_REGISTRATION) {
      if (errEl) {
        errEl.textContent = "🔒 Temporalmente deshabilitado. Solo altas con invitación.";
        errEl.classList.remove("hidden");
        errEl.classList.add("auth-notice");
      }
      if (usernameInput) usernameInput.disabled = true;
      if (passwordInput) passwordInput.disabled = true;
      if (submitBtn) {
        submitBtn.textContent = "Altas por invitación";
        submitBtn.disabled = true;
      }
    } else {
      if (usernameInput) usernameInput.disabled = false;
      if (passwordInput) passwordInput.disabled = false;
      if (submitBtn) {
        submitBtn.textContent = "Registrarse y Entrar";
        submitBtn.disabled = false;
      }
    }
  } else {
    if (tabLogin) tabLogin.classList.add("active");
    if (tabRegister) tabRegister.classList.remove("active");
    if (modalTitle) modalTitle.textContent = "Iniciar Sesión";
    if (usernameInput) usernameInput.disabled = false;
    if (passwordInput) passwordInput.disabled = false;
    if (submitBtn) {
      submitBtn.textContent = "Iniciar Sesión";
      submitBtn.disabled = false;
    }
  }
}

export async function handleAuthSubmit(e, onSuccess) {
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

  const endpoint = state.authMode === "register" ? "/api/auth/register" : "/api/auth/login";

  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });
    
    let data;
    const contentType = res.headers.get("content-type");
    if (contentType && contentType.includes("application/json")) {
      data = await res.json();
    } else {
      throw new Error(`Error de conexión con el servidor (${res.status}).`);
    }

    if (!res.ok || data.status !== "success") {
      throw new Error(data.detail || "Usuario o contraseña incorrectos.");
    }

    state.authToken = data.user.token;
    state.currentUser = { 
      user_id: data.user.user_id, 
      username: data.user.username, 
      first_name: data.user.first_name,
      role: data.user.role || data.user.role_name
    };

    localStorage.setItem("alj_token", state.authToken);
    localStorage.setItem("alj_user", JSON.stringify(state.currentUser));

    updateAuthUI();
    closeAuthModal();
    if (onSuccess) onSuccess();
    checkAuthStatus();
  } catch (err) {
    if (errEl) {
      errEl.textContent = err.message || "Error al iniciar sesión";
      errEl.classList.remove("hidden");
    }
  } finally {
    if (submitBtn && !(state.authMode === "register" && !ENABLE_PUBLIC_REGISTRATION)) {
      submitBtn.disabled = false;
    }
  }
}

export async function handleLogout(onLogout) {
  if (state.authToken) {
    try {
      await authFetch(`${API_BASE}/api/auth/logout`, { method: "POST" });
    } catch (e) {}
  }
  state.authToken = null;
  state.currentUser = null;
  localStorage.removeItem("alj_token");
  localStorage.removeItem("alj_user");
  updateAuthUI();
  const modalSettings = document.getElementById("modal-settings");
  if (modalSettings) modalSettings.classList.remove("open");
  if (onLogout) onLogout();
}
