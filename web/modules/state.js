/**
 * State Module for PathTale Interactive Gamebooks
 * Shared state variables and helper utility functions.
 */

export const API_BASE = "";

export const state = {
  authToken: localStorage.getItem("alj_token") || null,
  currentUser: JSON.parse(localStorage.getItem("alj_user") || "null"),
  authMode: "login",
  landingAuthMode: "login",

  currentBookId: null,
  currentGameState: null,
  currentAudioType: "narrative",
  currentSupplements: [],

  mediaRecorder: null,
  audioChunks: [],
  isRecording: false,

  libraryViewMode: localStorage.getItem("alj_library_view") || "grid",
  allLibraryBooks: [],

  navigationHistory: [],
  isNavigatingBack: false,

  appSettings: {
    theme: "pathtale",
    fontSize: "font-md",
    autoplay: false,
    voiceEnabled: true,
    audioSpeed: 1.0
  }
};

export function authFetch(url, options = {}) {
  const headers = options.headers || {};
  if (state.authToken) {
    headers["Authorization"] = `Bearer ${state.authToken}`;
  }
  return fetch(url, { ...options, headers });
}

export function escapeHtml(str) {
  if (!str) return "";
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

export function formatTime(seconds) {
  if (isNaN(seconds)) return "0:00";
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
}

export function formatTimeAgo(isoString) {
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
