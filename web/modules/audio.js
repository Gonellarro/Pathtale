/**
 * Audio Player Controls Module for PathTale (Piper TTS & Options Player)
 */

import { state, formatTime } from "./state.js";
import { updateSetting } from "./settings.js";

const audioPlayer = document.getElementById("html-audio-player");

function showAudioDock() {
  const dock = document.getElementById("global-audio-player");
  if (dock) dock.classList.remove("hidden");
}

export function toggleAudioPlay() {
  if (audioPlayer.paused) {
    if (!audioPlayer.src && state.currentGameState) {
      state.currentAudioType = "narrative";
      audioPlayer.src = `${state.currentGameState.audio_url}?v=${Date.now()}`;
    }
    audioPlayer.play().catch(err => console.log("Audio play error:", err));
  } else {
    audioPlayer.pause();
  }
}

export function playOptionsAudio() {
  if (!state.currentGameState || !state.currentGameState.audio_options_url) return;
  state.currentAudioType = "options";
  audioPlayer.src = `${state.currentGameState.audio_options_url}?v=${Date.now()}`;
  audioPlayer.play().catch(err => console.log("Options play error:", err));
}

export function onAudioPlay() {
  showAudioDock();
  const label = document.getElementById("audio-label");
  const icon = document.getElementById("audio-icon");
  const btn = document.getElementById("btn-audio-play");
  if (icon) icon.textContent = "⏸";
  if (label) {
    label.textContent = (state.currentAudioType === "options") ? "Pausar Opciones" : "Pausar Narración";
  }
  if (btn) btn.classList.add("playing");

  // Re-apply speed on every play event so changing audio src does not reset speed to 1.0
  if (audioPlayer && state.appSettings && state.appSettings.audioSpeed) {
    const savedSpeed = parseFloat(state.appSettings.audioSpeed) || 1.0;
    audioPlayer.playbackRate = savedSpeed;
  }
}

export function onAudioPause() {
  const label = document.getElementById("audio-label");
  const icon = document.getElementById("audio-icon");
  const btn = document.getElementById("btn-audio-play");
  if (icon) icon.textContent = "▶";
  if (label) label.textContent = "Escuchar Narración";
  if (btn) btn.classList.remove("playing");
}

export function onAudioEnded() {
  if (state.currentAudioType === "narrative" && state.currentGameState && state.currentGameState.audio_options_url) {
    state.currentAudioType = "options";
    audioPlayer.src = `${state.currentGameState.audio_options_url}?v=${Date.now()}`;
    audioPlayer.play().catch(() => {
      resetAudioToNarrative();
    });
  } else {
    resetAudioToNarrative();
  }
}

export function resetAudioToNarrative() {
  state.currentAudioType = "narrative";
  if (state.currentGameState && state.currentGameState.audio_url) {
    audioPlayer.src = `${state.currentGameState.audio_url}?v=${Date.now()}`;
  }
  onAudioPause();
  document.dispatchEvent(new CustomEvent("allAudioEnded"));
}

export function updateAudioProgress() {
  if (!audioPlayer.duration) return;
  const current = audioPlayer.currentTime;
  const total = audioPlayer.duration;
  const pct = (current / total) * 100;

  const slider = document.getElementById("audio-slider");
  const timeCur = document.getElementById("audio-time-current");
  const timeTot = document.getElementById("audio-time-total");

  if (slider) slider.value = pct;
  if (timeCur) timeCur.textContent = formatTime(current);
  if (timeTot) timeTot.textContent = formatTime(total);
}

export function onAudioSeek(e) {
  if (!audioPlayer.duration) return;
  const pct = e.target.value;
  audioPlayer.currentTime = (pct / 100) * audioPlayer.duration;
}

export function onAudioVolumeChange(e) {
  if (!audioPlayer) return;
  const volume = Math.max(0, Math.min(1, Number(e.target.value)));
  audioPlayer.volume = volume;
  localStorage.setItem("alj_audio_volume", String(volume));
}

export function toggleAudioSpeed() {
  const btn = document.getElementById("btn-audio-speed");
  const speeds = [1.0, 1.25, 1.5, 2.0];
  const currentSpeed = parseFloat((state.appSettings && state.appSettings.audioSpeed) ? state.appSettings.audioSpeed : "1.0");
  let curIdx = speeds.indexOf(currentSpeed);
  if (curIdx === -1) curIdx = 0;
  let nextIdx = (curIdx + 1) % speeds.length;
  let newSpeed = speeds[nextIdx];

  if (audioPlayer) audioPlayer.playbackRate = newSpeed;
  if (btn) btn.textContent = `${newSpeed.toFixed(1)}x`;
  updateSetting("audioSpeed", newSpeed);
}
