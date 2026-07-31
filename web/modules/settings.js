/**
 * Settings & Preference Management Module for PathTale
 */

import { state, authFetch, API_BASE } from "./state.js";

export function setTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
}

export function setFontSize(fontClass) {
  const body = document.body;
  body.classList.remove("font-sm", "font-md", "font-lg", "font-xl");
  body.classList.add(fontClass);
}

export async function loadSettings() {
  const localTheme = localStorage.getItem("alj_theme") || "pathtale";
  const localFont = localStorage.getItem("alj_font_size") || "font-md";
  const localAutoplay = localStorage.getItem("alj_autoplay") === "true";
  const localVoice = localStorage.getItem("alj_voice") !== "false";
  const localSpeed = parseFloat(localStorage.getItem("alj_speed") || "1.0");

  state.appSettings = {
    theme: localTheme,
    fontSize: localFont,
    autoplay: localAutoplay,
    voiceEnabled: localVoice,
    audioSpeed: localSpeed
  };

  applySettingsToUI();

  if (state.authToken) {
    const uid = (state.currentUser && state.currentUser.user_id) ? state.currentUser.user_id : 1;
    try {
      const res = await authFetch(`${API_BASE}/api/users/${uid}/settings`);
      const data = await res.json();
      if (data && data.settings && Object.keys(data.settings).length > 0) {
        state.appSettings = { ...state.appSettings, ...data.settings };
        applySettingsToUI();
      }
    } catch (err) {
      console.log("Using local settings (offline/server sync skipped)");
    }
  }
}

export function applySettingsToUI() {
  setTheme(state.appSettings.theme);
  setFontSize(state.appSettings.fontSize);

  const themeEl = document.getElementById("setting-theme");
  const fontEl = document.getElementById("setting-font-size");
  const autoEl = document.getElementById("setting-autoplay");
  const voiceEl = document.getElementById("setting-voice-enabled");

  if (themeEl) themeEl.value = state.appSettings.theme;
  if (fontEl) fontEl.value = state.appSettings.fontSize;
  if (autoEl) autoEl.checked = !!state.appSettings.autoplay;
  if (voiceEl) voiceEl.checked = state.appSettings.voiceEnabled !== false;

  const speed = parseFloat(state.appSettings.audioSpeed || "1.0");
  const audioPlayer = document.getElementById("html-audio-player");
  const speedBtn = document.getElementById("btn-audio-speed");

  if (audioPlayer) {
    audioPlayer.playbackRate = speed;
  }
  if (speedBtn) {
    speedBtn.textContent = `${speed.toFixed(1)}x`;
  }

  // Voice recording button & box visibility toggle
  const voiceBox = document.querySelector(".voice-input-box");
  const voiceBtn = document.getElementById("btn-voice-record");
  if (state.appSettings.voiceEnabled === false) {
    if (voiceBox) voiceBox.classList.add("hidden");
    if (voiceBtn) voiceBtn.classList.add("hidden");
  } else {
    if (voiceBox) voiceBox.classList.remove("hidden");
    if (voiceBtn) voiceBtn.classList.remove("hidden");
  }
}

export function updateSetting(key, value) {
  state.appSettings[key] = value;

  if (key === "theme") localStorage.setItem("alj_theme", value);
  if (key === "fontSize") localStorage.setItem("alj_font_size", value);
  if (key === "autoplay") localStorage.setItem("alj_autoplay", value);
  if (key === "voiceEnabled") localStorage.setItem("alj_voice", value);
  if (key === "audioSpeed") localStorage.setItem("alj_speed", value);

  applySettingsToUI();

  if (state.authToken) {
    const uid = (state.currentUser && state.currentUser.user_id) ? state.currentUser.user_id : 1;
    authFetch(`${API_BASE}/api/users/${uid}/settings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ settings: state.appSettings })
    }).catch(() => {});
  }
}

export function toggleSettingsModal() {
  const modalSettings = document.getElementById("modal-settings");
  if (modalSettings) {
    modalSettings.classList.toggle("open");
  }
}
