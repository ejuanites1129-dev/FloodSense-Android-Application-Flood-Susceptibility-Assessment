"use strict";
(() => {
  const dataNode = document.getElementById("dss-preview-structure");
  const host = document.getElementById("dss-resident-preview");
  if (!dataNode || !host) return;
  const graph = JSON.parse(dataNode.textContent);
  const flow = graph.flow;
  const history = [];
  let current = (graph.questions || []).find(q => q.is_start);
  let outcome = null;
  function text(tag, value, parent = host) {
    const node = document.createElement(tag);
    node.textContent = value || "";
    parent.append(node);
    return node;
  }
  function button(label, action, parent = host) {
    const node = text("button", label, parent);
    node.type = "button";
    node.className = "button button--secondary";
    node.addEventListener("click", action);
    return node;
  }
  function source(record, parent = host) {
    if (!record) return;
    const container = document.createElement("div");
    container.className = "dss-preview-source";
    parent.append(container);
    text("p", `Source: ${record.name || "Not recorded"} · ${record.organization || ""}`, container);
    if (record.version) text("p", `Source version: ${record.version}`, container);
    if (record.reviewed_on) text("p", `Reviewed: ${record.reviewed_on}`, container);
    if (record.date) text("p", `Reference date: ${record.date}`, container);
    if (record.data_status) text("p", `Data status: ${record.data_status}`, container);
    if (record.limitations) text("p", record.limitations, container);
    if (record.citation_url && /^https:\/\//i.test(record.citation_url)) {
      const link = text("a", "Source reference", container);
      link.href = record.citation_url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
    }
  }
  function renderBlocks() {
    const blocks = (graph.content_blocks || []).filter(b => b.audience !== "STAFF_ONLY" && (!b.outcome_code || b.outcome_code === outcome?.code));
    for (const type of ["SCENARIO_EXPLANATION", "HOUSEHOLD_ACTION", "OFFICIAL_CHANNEL", "MONITORING_REFERENCE", "AUTHORITY_ACTIVITY", "RISK_REFERENCE"]) {
      const selected = blocks.filter(b => b.content_type === type);
      if (!selected.length) continue;
      const headings = {SCENARIO_EXPLANATION: "What this scenario may mean", HOUSEHOLD_ACTION: "What your household can prepare", OFFICIAL_CHANNEL: "Official information channels", MONITORING_REFERENCE: "What local responders monitor", AUTHORITY_ACTIVITY: "What local authorities may coordinate", RISK_REFERENCE: "Educational reference"};
      const section = type === "MONITORING_REFERENCE" ? document.createElement("details") : document.createElement("section");
      host.append(section);
      text(type === "MONITORING_REFERENCE" ? "summary" : "h3", headings[type], section);
      if (type === "MONITORING_REFERENCE") text("p", "FloodSense does not monitor these sources live.", section);
      for (const phase of ["BEFORE", "ALWAYS", "DURING", "AFTER"]) {
        const items = selected.filter(b => b.phase === phase);
        if (!items.length) continue;
        text("h4", `${phase.charAt(0)}${phase.slice(1).toLowerCase()}${["DURING", "AFTER"].includes(phase) ? " — educational reference" : ""}`, section);
        const list = document.createElement("ol");
        section.append(list);
        for (const block of items) {
          const item = document.createElement("li"); list.append(item);
          text("strong", block.title, item); text("p", block.body, item);
          if (block.limitations) text("p", `Limitations: ${block.limitations}`, item);
          if (block.attribution) text("p", block.attribution, item);
          source(block.source, item);
          if (block.public_url && /^https:\/\//i.test(block.public_url)) {
            const link = text("a", "Verified official channel", item);
            link.href = block.public_url; link.target = "_blank"; link.rel = "noopener noreferrer";
          }
        }
      }
    }
  }
  function render() {
    host.replaceChildren();
    text("h2", flow.title);
    text("p", `${flow.data_status} · ${flow.version} · staff-only preview`);
    text("p", flow.warning);
    if (outcome) {
      text("h3", outcome.title); text("p", outcome.instruction); text("p", outcome.warning); source(outcome.source);
      for (const item of outcome.guidance || []) {
        text("h4", item.title); text("p", item.instruction);
        if (item.attribution) text("p", item.attribution);
        source(item.source);
      }
    } else if (current) {
      text("h3", "Household support check"); text("h4", current.prompt); text("p", current.explanatory_text);
      for (const option of current.options || []) button(option.label, () => {
        history.push({current, outcome, option});
        outcome = (graph.outcomes || []).find(o => o.code === option.outcome_code) || null;
        current = (graph.questions || []).find(q => q.code === option.next_question_code) || null;
        render();
      });
      for (const option of current.options || []) {
        if (option.supporting_text) text("p", `${option.label}: ${option.supporting_text}`);
      }
    } else text("p", "No start question is available. Complete and validate this draft.");
    if (history.length) {
      text("h3", "Your household support check");
      for (const answer of history) {
        text("p", `${answer.current.prompt}: ${answer.option.label}`);
        if (answer.option.supporting_text) text("p", answer.option.supporting_text);
      }
    }
    renderBlocks();
    text("h3", "Sources and limitations"); source(flow.source);
    if (flow.source_locator) text("p", flow.source_locator);
    if (flow.attribution) text("p", flow.attribution);
    if (flow.effective_date) text("p", `Effective: ${flow.effective_date}`);
    if (flow.reviewed_on) text("p", `Reviewed: ${flow.reviewed_on}`);
    if (flow.expires_on) text("p", `Expiry: ${flow.expires_on}`);
    text("p", flow.limitations || "No additional limitations recorded.");
    const controls = document.createElement("div"); controls.className = "dss-preview-controls"; host.append(controls);
    const back = button("Back", () => {const previous = history.pop(); if (previous) {current = previous.current; outcome = previous.outcome; render();}}, controls); back.disabled = !history.length;
    button("Restart", () => {history.length = 0; outcome = null; current = (graph.questions || []).find(q => q.is_start) || null; render();}, controls);
  }
  render();
})();
