/* Public façade for the game feature's API, navigation and rendering modules. */

import { jumpToSection, startGame, submitChoice } from "./api.js";
import { goBackHistory as navigateBack, updateBackHistoryUI } from "./navigation.js";

export { jumpToSection, startGame, submitChoice, updateBackHistoryUI };
export { renderChoices, renderGameState } from "./renderer.js";
export function goBackHistory() {
  return navigateBack(jumpToSection);
}
