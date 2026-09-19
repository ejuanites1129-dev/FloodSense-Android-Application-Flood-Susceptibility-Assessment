(() => {
  const preview = document.querySelector("[data-guidance-preview]");
  if (!preview) return;

  const field = (id) => document.getElementById(id);
  const setText = (selector, value, fallback) => {
    const target = preview.querySelector(selector);
    if (target) target.textContent = value.trim() || fallback;
  };
  const selectedText = (select) =>
    select && select.selectedIndex >= 0
      ? select.options[select.selectedIndex].text
      : "";

  const update = () => {
    setText("[data-preview-title]", field("id_title")?.value || "", "Guidance title");
    setText(
      "[data-preview-instruction]",
      field("id_instruction")?.value || "",
      "Preparedness instruction will appear here."
    );
    setText(
      "[data-preview-category]",
      selectedText(field("id_category")),
      "Category"
    );
    setText(
      "[data-preview-source]",
      selectedText(field("id_source")),
      "Select a source"
    );
    setText(
      "[data-preview-attribution]",
      field("id_attribution")?.value || "",
      "No additional attribution recorded."
    );
  };

  ["id_title", "id_instruction", "id_category", "id_source", "id_attribution"].forEach(
    (id) => {
      const input = field(id);
      if (input) {
        input.addEventListener("input", update);
        input.addEventListener("change", update);
      }
    }
  );
  update();
})();
