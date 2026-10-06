"use strict";
(() => {
  // Source search preserves its native selection; barangays use only a dropdown.
  for (const id of ["id_source"]) {
    const select = document.getElementById(id);
    if (!select) continue;
    const input = document.createElement("input");
    input.type = "search"; input.placeholder = "Search available choices";
    input.id = `${id}_search`;
    const label = document.createElement("label");
    label.htmlFor = input.id; label.textContent = "Search sources";
    select.before(label, input);
    input.addEventListener("input", () => {
      const query = input.value.toLocaleLowerCase();
      for (const option of select.options) option.hidden = Boolean(option.value && !option.selected && !option.text.toLocaleLowerCase().includes(query));
    });
  }
  const dialog = document.querySelector("[data-source-dialog]");
  if (!dialog) return;
  const body = dialog.querySelector("[data-source-dialog-body]");
  const status = dialog.querySelector("[data-source-dialog-status]");
  const result = document.querySelector("[data-source-result]");
  const select = document.getElementById("id_source");
  const metadata = JSON.parse(document.getElementById("center-source-metadata")?.textContent || "{}");
  const context = document.querySelector("[data-live-source-context]");
  function showSourceContext() {
    context?.replaceChildren();
    const source = metadata[select.value];
    if (!source || !context) return;
    const staticContext = document.querySelector('[aria-labelledby="source-review-heading"]');
    if (staticContext) staticContext.hidden = true;
    const revision = document.getElementById("id_expected_source_updated_at");
    if (revision) revision.value = source.revision;
    for (const [key, label] of Object.entries({name: "Source", organization: "Organization", custodian: "Custodian", status: "Validation status", public: "Public release", version: "Version", date: "Reference date", limitations: "Limitations"})) {
      const group = document.createElement("div"), term = document.createElement("dt"), value = document.createElement("dd");
      term.textContent = label;
      value.textContent = key === "public" ? (source[key] ? "Permitted" : "Not permitted") : (source[key] || "Not recorded");
      group.append(term, value); context.append(group);
    }
  }
  select.addEventListener("change", showSourceContext);
  showSourceContext();
  let url = "", opener = null;
  document.querySelector("[data-source-close]").addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => opener?.focus());
  async function open(button, target) {
    url = target; opener = button; body.replaceChildren(); status.textContent = "Loading source form…";
    dialog.showModal();
    try {
      const response = await fetch(url, {credentials: "same-origin", headers: {Accept: "application/json"}});
      if (!response.ok) throw new Error("This source cannot be edited with your current permissions or review state. Keep the center draft; use the source detail page for approved records.");
      const data = await response.json();
      // HTML is rendered by Django with escaped field values, never upload-derived markup.
      body.innerHTML = data.html; status.textContent = "Center fields are preserved behind this dialog.";
      body.querySelector("input:not([type=hidden]), select, textarea")?.focus();
    } catch (error) { status.textContent = error.message; }
  }
  document.querySelector("[data-inline-source-new]")?.addEventListener("click", e => open(e.currentTarget, e.currentTarget.dataset.url));
  document.querySelector("[data-inline-source-edit]")?.addEventListener("click", e => {
    if (!select.value) { result.textContent = "Select a source first."; return; }
    open(e.currentTarget, e.currentTarget.dataset.urlPattern.replace("/0/", `/${select.value}/`));
  });
  body.addEventListener("submit", async e => {
    const form = e.target.closest("[data-inline-source-form]");
    if (!form) return;
    e.preventDefault();
    const payload = new FormData(form);
    payload.set("save_action", e.submitter?.value || "save");
    status.textContent = "Validating and saving source metadata…";
    try {
      const response = await fetch(url, {method: "POST", credentials: "same-origin", body: payload});
      const data = await response.json();
      if (!response.ok) {
        if (data.html) { body.innerHTML = data.html; status.textContent = "Nothing saved. Correct the errors; your center fields are unchanged."; }
        else throw new Error("Source save denied or unavailable. Your center fields are unchanged.");
        return;
      }
      if (!Number.isInteger(data.id)) throw new Error("The source form could not be saved; review its errors.");
      let option = [...select.options].find(o => o.value === String(data.id));
      if (!option) { option = document.createElement("option"); option.value = data.id; select.add(option); }
      option.textContent = data.label; option.hidden = false; select.value = data.id;
      metadata[String(data.id)] = data.metadata;
      select.dispatchEvent(new Event("change", {bubbles: true}));
      result.textContent = `${data.label}: ${data.state}; public release ${data.public ? "permitted" : "not permitted"}. Center is not saved or verified by this source action.`;
      dialog.close();
    } catch (error) { status.textContent = "Unable to save source. " + error.message; }
  });
})();
