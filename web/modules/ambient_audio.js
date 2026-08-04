/**
 * Ambient music runtime. Kept separate from the narration player so each
 * concern can evolve independently.
 */

let activeAudio = null;
let pendingRuntime = null;
let currentSceneKey = null;
let enabled = false;
let ambientVolume = Number(localStorage.getItem("alj_ambient_volume"));
if (!Number.isFinite(ambientVolume)) ambientVolume = 0.30;

function ensureAudio() {
  if (!activeAudio) {
    activeAudio = new Audio();
    activeAudio.loop = true;
    activeAudio.preload = "auto";
    activeAudio.volume = ambientVolume;
  }
  return activeAudio;
}

function sceneTrack(runtime) {
  const directive = runtime?.node_directive || {};
  const sceneId = directive.scene;
  const scene = sceneId ? runtime?.music_scenes?.[sceneId] : null;
  const track = scene?.tracks?.[0];
  if (!sceneId || !track?.file) return null;
  return {
    key: `${sceneId}:${track.asset_id}`,
    url: track.file,
    crossfadeMs: Number(scene.crossfade_ms) || 5000,
  };
}

export function syncAmbientRuntime(runtime) {
  pendingRuntime = runtime || null;
  const next = sceneTrack(pendingRuntime);
  if (!next) {
    currentSceneKey = null;
    if (activeAudio) {
      activeAudio.pause();
      activeAudio.removeAttribute("src");
      activeAudio.load();
    }
    return;
  }
  if (currentSceneKey === next.key) return;
  currentSceneKey = next.key;
  if (enabled) startTrack(next);
}

function startTrack(track) {
  const player = ensureAudio();
  if (player.src.endsWith(track.url)) return;
  const wasPlaying = !player.paused;
  const targetVolume = ambientVolume;
  const fadeMs = Math.max(0, Math.min(track.crossfadeMs, 15000));
  const swap = () => {
    player.pause();
    player.src = `${track.url}?v=ambient`;
    player.volume = wasPlaying ? 0 : targetVolume;
    if (wasPlaying) {
      player.play().catch(() => {});
      const startedAt = performance.now();
      const fadeIn = (now) => {
        const progress = fadeMs ? Math.min(1, (now - startedAt) / fadeMs) : 1;
        player.volume = targetVolume * progress;
        if (progress < 1) requestAnimationFrame(fadeIn);
      };
      requestAnimationFrame(fadeIn);
    }
  };
  if (!wasPlaying || !fadeMs) {
    swap();
    return;
  }
  const startedAt = performance.now();
  const fadeOut = (now) => {
    const progress = Math.min(1, (now - startedAt) / fadeMs);
    player.volume = targetVolume * (1 - progress);
    if (progress < 1) requestAnimationFrame(fadeOut);
    else swap();
  };
  requestAnimationFrame(fadeOut);
}

export function resumeAmbientAudio() {
  enabled = true;
  const track = sceneTrack(pendingRuntime);
  if (!track) return;
  startTrack(track);
  ensureAudio().play().catch(() => {});
}

export function pauseAmbientAudio() {
  enabled = false;
  if (activeAudio) activeAudio.pause();
}

export function setAmbientVolume(volume) {
  ambientVolume = Math.max(0, Math.min(1, Number(volume) || 0));
  localStorage.setItem("alj_ambient_volume", String(ambientVolume));
  if (activeAudio) activeAudio.volume = ambientVolume;
}
