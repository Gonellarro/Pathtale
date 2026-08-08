/**
 * Audio Player Controls Module for PathTale (Piper TTS & Options Player)
 */

import { state, authFetch, API_BASE, formatTime } from "./state.js";
import { updateSetting } from "./settings.js";
import { resumeAmbientAudio, pauseAmbientAudio } from "./ambient_audio.js";

const audioPlayer = document.getElementById("html-audio-player");
const PLAY_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4.5 19 12 7 19.5Z"></path></svg>';
const PAUSE_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14M16 5v14"></path></svg>';

let narrationContext = null;
let persistOnNextPause = false;

function saveNarrationBookmark({ keepalive = false } = {}) {
  if (!audioPlayer || !narrationContext || audioPlayer.ended || !state.authToken) return;

  const positionSeconds = Number(audioPlayer.currentTime);
  if (!Number.isFinite(positionSeconds) || positionSeconds < 0) return;

  const uid = state.currentUser?.user_id;
  if (!uid) return;

  return authFetch(
    `${API_BASE}/api/games/${uid}/${encodeURIComponent(narrationContext.bookId)}/playback-position`,
    {
      method: "PUT",
      keepalive,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        node_id: narrationContext.nodeId,
        position_seconds: positionSeconds,
        captured_at_ms: Date.now(),
      }),
    },
  ).catch(() => {
    // Playback must remain responsive if the bookmark cannot be synchronized.
  });
}

export function persistCurrentNarrationBookmark({ keepalive = false } = {}) {
  if (state.currentAudioType === "narrative" && audioPlayer && !audioPlayer.paused) {
    return saveNarrationBookmark({ keepalive });
  }
  return Promise.resolve();
}

export function persistNarrationBookmarkOnExit() {
  persistCurrentNarrationBookmark({ keepalive: true });
}

export function loadNarrativeAudio(gameState) {
  if (!audioPlayer || !gameState?.audio_url) return;

  const nextNarrationContext = { bookId: gameState.book_id, nodeId: gameState.node_id };
  state.currentAudioType = "narrative";
  const bookmark = Number(gameState.playback_position_seconds) || 0;

  audioPlayer.src = `${gameState.audio_url}?v=${Date.now()}`;
  const restoreBookmark = () => {
    // Associate the bookmark once the newly selected narration has metadata.
    narrationContext = nextNarrationContext;
    if (bookmark > 0 && audioPlayer.duration && bookmark < audioPlayer.duration) {
      audioPlayer.currentTime = bookmark;
    }
    if (state.appSettings.autoplay) {
      audioPlayer.play().catch(() => {});
    }
  };

  audioPlayer.addEventListener("loadedmetadata", restoreBookmark, { once: true });
}

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
    persistOnNextPause = state.currentAudioType === "narrative";
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
  resumeAmbientAudio();
  const label = document.getElementById("audio-label");
  const icon = document.getElementById("audio-icon");
  const btn = document.getElementById("btn-audio-play");
  if (icon) icon.innerHTML = PAUSE_ICON;
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
  if (persistOnNextPause && state.currentAudioType === "narrative") {
    saveNarrationBookmark();
  }
  persistOnNextPause = false;
  pauseAmbientAudio();
  const label = document.getElementById("audio-label");
  const icon = document.getElementById("audio-icon");
  const btn = document.getElementById("btn-audio-play");
  if (icon) icon.innerHTML = PLAY_ICON;
  if (label) label.textContent = "Escuchar Narración";
  if (btn) btn.classList.remove("playing");
}

export function onAudioEnded() {
  // A completed narration is not a useful resume point.
  if (state.currentAudioType === "narrative") narrationContext = null;
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
