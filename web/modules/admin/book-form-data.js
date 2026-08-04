export function readBookConfigForm() {
  const selectedOption = document.getElementById("pre-import-voice-select")?.selectedOptions?.[0];
  const coverInput = document.getElementById("pre-import-cover-file");
  const regenCheck = document.getElementById("pre-import-regenerate-check");
  const generateAudiosCheck = document.getElementById("pre-import-generate-audios-check");
  return {
    editBookId: document.getElementById("pre-import-edit-book-id").value,
    tempFileId: document.getElementById("pre-import-temp-id").value,
    title: document.getElementById("pre-import-title").value.trim(),
    author: document.getElementById("pre-import-author").value.trim(),
    language: document.getElementById("pre-import-language").value,
    startNode: document.getElementById("pre-import-start-node").value.trim(),
    tierId: parseInt(document.getElementById("pre-import-tier").value || "1"),
    regenCheck: Boolean(regenCheck?.checked),
    generateAudios: Boolean(generateAudiosCheck?.checked),
    coverFile: coverInput?.files?.[0] || null,
    narratorId: selectedOption ? parseInt(selectedOption.getAttribute("data-narrator-id") || "1") : 1,
  };
}
