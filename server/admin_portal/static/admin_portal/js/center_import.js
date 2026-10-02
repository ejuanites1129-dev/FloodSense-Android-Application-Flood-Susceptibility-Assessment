"use strict";
(() => {
  const page = document.querySelector(".center-import");
  if (!page) return;

  const source = page.querySelector("#id_source");
  const emptyOption = [...source.options].find(option => !option.value);
  if (emptyOption) emptyOption.textContent = "Select a source";
  page.querySelector("#id_shared_limitations").placeholder = "Add batch limitations, if applicable";

  // Keep the real Django file input and native chooser; enhance its presentation only.
  const upload = page.querySelector("#id_upload");
  const control = upload.closest(".center-import__file-control");
  const filename = page.querySelector("[data-upload-filename]");
  control.classList.add("center-import__file-control--enhanced");
  control.querySelector(".center-import__browse").hidden = false;
  const showFilename = () => {
    filename.textContent = upload.files[0]?.name || "";
    filename.hidden = !filename.textContent;
  };
  upload.addEventListener("change", showFilename);
  showFilename();

  for (const name of ["source", "upload"]) {
    const input = page.querySelector(`#id_${name}`);
    const descriptions = new Set((input.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean));
    descriptions.add(`id_${name}_helptext`);
    input.setAttribute("aria-describedby", [...descriptions].join(" "));
  }
})();
