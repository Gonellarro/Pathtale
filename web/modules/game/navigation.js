import { state } from "../state.js";

export function resetNavigationHistory() {
  state.navigationHistory = [];
}

export function recordVisitedNode(nodeId) {
  if (!state.isNavigatingBack && (state.navigationHistory.length === 0 || state.navigationHistory.at(-1) !== nodeId)) {
    state.navigationHistory.push(nodeId);
  }
  updateBackHistoryUI();
}

export async function goBackHistory(jumpToSection) {
  if (state.navigationHistory.length <= 1) return;
  state.navigationHistory.pop();
  const previousNodeId = state.navigationHistory.at(-1);
  if (!previousNodeId) return;
  state.isNavigatingBack = true;
  try {
    await jumpToSection(previousNodeId);
  } finally {
    state.isNavigatingBack = false;
  }
}

export function updateBackHistoryUI() {
  const button = document.getElementById("btn-game-history-back");
  if (button) button.disabled = state.navigationHistory.length <= 1;
}
