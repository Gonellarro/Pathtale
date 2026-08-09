import { API_BASE, authFetch, state } from "../state.js";
import { openAuthModal } from "../auth.js";
import { loadBookSupplements } from "./supplements.js";
import { renderGameState } from "./renderer.js";
import { resetNavigationHistory } from "./navigation.js";
import { showGameView } from "./views.js";
import { persistCurrentNarrationBookmark } from "../audio.js";

function getUserId() {
  return state.currentUser?.user_id || 1;
}

async function requestGame(url, options) {
  const response = await authFetch(url, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const error = new Error(payload.detail || String(response.status));
    error.status = response.status;
    throw error;
  }
  return response.json();
}

export async function startGame(bookId, forceNew = false) {
  if (!state.authToken || !state.currentUser) {
    openAuthModal();
    return;
  }
  const changingBook = state.currentBookId && state.currentBookId !== bookId;
  if (changingBook) await persistCurrentNarrationBookmark();
  if (changingBook || forceNew) resetNavigationHistory();
  state.currentBookId = bookId;
  showGameView();
  try {
    const uid = getUserId();
    const data = forceNew
      ? await requestGame(`${API_BASE}/api/games`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ book_id: bookId }) })
      : await requestGame(`${API_BASE}/api/games/${uid}/${encodeURIComponent(bookId)}`);
    if (data?.node_id) {
      state.currentGameState = data;
      await loadBookSupplements(bookId, forceNew);
      renderGameState(data);
    }
  } catch (error) {
    if (!forceNew && error.status === 404) return startGame(bookId, true);
    console.error("Error starting game:", error);
    alert("Error al cargar la partida. Revisa la consola o los logs del servidor.");
  }
}

export async function submitChoice(choiceId, targetNode, textQuery = null) {
  if (!state.currentBookId) return;
  try {
    const data = await requestGame(`${API_BASE}/api/games/${getUserId()}/${encodeURIComponent(state.currentBookId)}/choice`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ choice_id: choiceId, target_node: targetNode, text_query: textQuery }),
    });
    if (data?.node_id) {
      state.currentGameState = data;
      renderGameState(data);
    }
  } catch (error) {
    console.error("Error submitting choice:", error);
  }
}

export async function jumpToSection(target) {
  if (!state.currentBookId || !target) return;
  try {
    const data = await requestGame(`${API_BASE}/api/games/${getUserId()}/${encodeURIComponent(state.currentBookId)}/jump`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ target }),
    });
    if (data?.node_id) {
      state.currentGameState = data;
      renderGameState(data);
    }
  } catch (error) {
    alert(`No se pudo ir a la sección ${target}: ${error.message || "Sección no encontrada"}`);
  }
}
