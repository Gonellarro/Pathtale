/**
 * Admin Module for PathTale Dashboard
 * Main entrypoint integrating submodules: users, books, narrators, and audit logs.
 */

import { state } from "./state.js";
import { loadAdminUsers, loadAdminRoles, openAdminUserModal } from "./admin/users.js";
import { openAdminBookTierModal } from "./admin/book-tier-modal.js";
import { loadAdminBooks, initAdminUploadZone, openPreImportModal, openEditExistingBookModal, openPostUploadModal, currentAdminBooks } from "./admin/books.js";
import { loadAdminNarrators } from "./admin/narrators.js";
import { loadAdminLogs } from "./admin/audit.js";

export async function loadAdminDashboard() {
  const role = state.currentUser ? (state.currentUser.role || state.currentUser.role_name) : null;
  if (!state.currentUser || role !== "admin") {
    console.warn("loadAdminDashboard: Current user is not admin", state.currentUser);
    return;
  }

  initAdminTabs();
  initAdminUploadZone();
  await Promise.all([
    loadAdminUsers(),
    loadAdminBooks(),
    loadAdminNarrators(),
    loadAdminLogs()
  ]);
}

function initAdminTabs() {
  const tabs = document.querySelectorAll(".admin-tab");
  tabs.forEach(tab => {
    tab.onclick = () => {
      tabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");

      const targetTab = tab.getAttribute("data-tab");
      document.querySelectorAll(".admin-panel").forEach(p => p.classList.add("hidden"));

      const activePanel = document.getElementById(`admin-panel-${targetTab}`);
      if (activePanel) {
        activePanel.classList.remove("hidden");
        activePanel.classList.add("active");
      }
    };
  });
}

// Re-export public functions for backward compatibility
export {
  loadAdminUsers,
  loadAdminRoles,
  openAdminUserModal,
  openAdminBookTierModal,
  loadAdminBooks,
  initAdminUploadZone,
  openPreImportModal,
  openEditExistingBookModal,
  openPostUploadModal,
  loadAdminNarrators,
  loadAdminLogs,
  currentAdminBooks
};
