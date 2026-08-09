import { API_BASE, authFetch, state } from "./state.js";

let narrationContext = null;

function save(player, { keepalive = false } = {}) {
  if (!player || !narrationContext || player.ended || !state.authToken) return Promise.resolve();
  const position = Number(player.currentTime);
  const userId = state.currentUser?.user_id;
  if (!userId || !Number.isFinite(position) || position < 0) return Promise.resolve();
  return authFetch(`${API_BASE}/api/games/${userId}/${encodeURIComponent(narrationContext.bookId)}/playback-position`, {
    method: "PUT", keepalive, headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ node_id: narrationContext.nodeId, position_seconds: position, captured_at_ms: Date.now() }),
  }).catch(() => {});
}

export function loadNarrativeBookmark(player, gameState) {
  if (!player || !gameState?.audio_url) return;
  const context = { bookId: gameState.book_id, nodeId: gameState.node_id };
  const bookmark = Number(gameState.playback_position_seconds) || 0;
  player.src = `${gameState.audio_url}?v=${Date.now()}`;
  player.addEventListener("loadedmetadata", () => {
    narrationContext = context;
    if (bookmark > 0 && player.duration && bookmark < player.duration) player.currentTime = bookmark;
    if (state.appSettings.autoplay && !state.supplementsOpen) player.play().catch(() => {});
  }, { once: true });
}

export function persistCurrentNarrationBookmark(player, { keepalive = false } = {}) {
  return state.currentAudioType === "narrative" && !player?.paused ? save(player, { keepalive }) : Promise.resolve();
}

export function persistPausedNarrationBookmark(player) {
  return save(player);
}

export function clearNarrationBookmarkContext() {
  narrationContext = null;
}
