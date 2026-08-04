export function setPreImportFields(values) {
  const fields = {
    "pre-import-temp-id": values.tempFileId || "",
    "pre-import-edit-book-id": values.editBookId || "",
    "pre-import-title": values.title || "",
    "pre-import-author": values.author || "",
    "pre-import-language": values.language || "es",
    "pre-import-start-node": values.startNode || "sec_001",
    "pre-import-tier": values.tierId || "1",
  };
  Object.entries(fields).forEach(([id, value]) => {
    const element = document.getElementById(id);
    if (element) element.value = value;
  });
  const coverInput = document.getElementById("pre-import-cover-file");
  if (coverInput) coverInput.value = "";
}

export function bindPreImportModal(onSubmit) {
  const modal = document.getElementById("modal-pre-import");
  if (!modal) return;
  const close = () => modal.classList.remove("open");
  const closeButton = document.getElementById("btn-close-modal-pre-import");
  const cancelButton = document.getElementById("btn-cancel-pre-import");
  const form = document.getElementById("form-pre-import");
  if (closeButton) closeButton.onclick = close;
  if (cancelButton) cancelButton.onclick = close;
  if (form) form.onsubmit = async (event) => {
    event.preventDefault();
    await onSubmit();
    close();
  };
}
