/**
 * Game Module for PathTale
 * Main entrypoint re-exporting view navigation, game engine, voice recognition, and history.
 */

export { showLandingView, showHomeView, showFullLibraryView, showAdminView, showGameView } from "./game/views.js";
export { startGame, submitChoice, jumpToSection, goBackHistory, updateBackHistoryUI, renderGameState, renderChoices } from "./game/engine.js";
export { initVoiceControls, triggerAutoVoiceListening, toggleVoiceRecording, updateVoiceUI, uploadAndTranscribeAudio } from "./game/voice.js";
export { toggleHistoryDrawer, renderHistoryDrawer } from "./game/history.js";
