(() => {
  const passwordToggle = document.querySelector("[data-password-toggle]");
  if (passwordToggle) {
    passwordToggle.addEventListener("click", () => {
      const input = passwordToggle.parentElement.querySelector("input");
      const reveal = input.type === "password";
      input.type = reveal ? "text" : "password";
      passwordToggle.textContent = reveal ? "Hide" : "Show";
      passwordToggle.setAttribute("aria-label", reveal ? "Hide password" : "Show password");
    });
  }

  const menuButton = document.querySelector("[data-menu-toggle]");
  const sidebar = document.querySelector("#portal-sidebar");
  const scrim = document.querySelector("[data-menu-scrim]");
  const accountToggle = document.querySelector("[data-account-toggle]");
  const accountMenu = document.querySelector("[data-account-menu]");

  const sidebarToggle = document.querySelector("[data-sidebar-toggle]");
  const navigation = document.querySelector("#sidebar-navigation");
  const mobile = window.matchMedia("(max-width: 760px)");
  const storageKey = "floodsense.sidebar.collapsed";
  let collapsed = false;
  let focusOnOpen = false;
  const focusExpandedSidebar = () => {
    if (!focusOnOpen || sidebarToggle?.getAttribute("aria-expanded") !== "true") return;
    sidebarToggle.focus({preventScroll: true});
    if (document.activeElement === sidebarToggle) focusOnOpen = false;
  };
  try { collapsed = localStorage.getItem(storageKey) === "true"; } catch { /* Storage is optional. */ }

  // All buttons and Ctrl+B use this state transition, including the mobile drawer.
  const setSidebar = (expanded, {persist = true, focus = false} = {}) => {
    if (!sidebar || !sidebarToggle || !navigation) return;
    const isMobile = mobile.matches;
    if (accountMenu) accountMenu.hidden = true;
    if (accountToggle) accountToggle.setAttribute("aria-expanded", "false");
    if (isMobile && !expanded && sidebar.contains(document.activeElement)) {
      menuButton.focus();
    }
    document.body.classList.toggle("sidebar-collapsed", !isMobile && !expanded);
    sidebar.classList.toggle("sidebar--open", isMobile && expanded);
    document.body.classList.toggle("menu-open", isMobile && expanded);
    navigation.hidden = false;
    sidebar.inert = isMobile && !expanded;
    menuButton.setAttribute("aria-expanded", String(isMobile && expanded));
    sidebarToggle.setAttribute("aria-expanded", String(expanded));
    const label = isMobile ? "Close navigation" : expanded ? "Collapse Sidebar" : "Expand Sidebar";
    sidebarToggle.setAttribute("aria-label", label);
    sidebarToggle.removeAttribute("title");
    sidebarToggle.setAttribute("data-sidebar-tooltip", expanded ? "Close sidebar" : "Open sidebar");
    if (!isMobile && persist) {
      collapsed = !expanded;
      try { localStorage.setItem(storageKey, String(collapsed)); } catch { /* Keep in-memory state. */ }
    }
    focusOnOpen = focus && expanded;
    if (focusOnOpen) requestAnimationFrame(focusExpandedSidebar);
    document.dispatchEvent(new Event("portal:layoutchange"));
  };
  const toggleSidebar = () => setSidebar(
    mobile.matches ? !sidebar.classList.contains("sidebar--open") : document.body.classList.contains("sidebar-collapsed"),
    {focus: true},
  );
  const closeMenu = () => {
    if (mobile.matches && sidebar?.classList.contains("sidebar--open")) {
      setSidebar(false);
      menuButton.focus();
    }
  };
  if (menuButton && sidebar && sidebarToggle) {
    sidebarToggle.hidden = false;
    setSidebar(mobile.matches ? false : !collapsed, {persist: false});
    menuButton.addEventListener("click", toggleSidebar);
    sidebarToggle.addEventListener("click", toggleSidebar);
    mobile.addEventListener("change", () => setSidebar(mobile.matches ? false : !collapsed, {persist: false}));
    sidebar.addEventListener("transitionend", event => {
      if (event.target !== sidebar) return;
      focusExpandedSidebar();
      document.dispatchEvent(new Event("portal:layoutchange"));
    });
    document.addEventListener("keydown", event => {
      const editor = event.composedPath().some(node => node instanceof Element && (
        node.matches("input, textarea, select, [role='textbox'], [role='searchbox'], [role='combobox'], [role='spinbutton'], .cm-editor, .monaco-editor") || node.isContentEditable
      ));
      if (event.ctrlKey && event.key.toLowerCase() === "b" && !event.repeat && !event.altKey && !event.shiftKey && !event.metaKey && !event.isComposing && !editor) {
        event.preventDefault();
        toggleSidebar();
      }
      if (event.key === "Tab" && mobile.matches && sidebar.classList.contains("sidebar--open")) {
        const items = [...sidebar.querySelectorAll("a[href], button:not([disabled])")].filter(item => item.getClientRects().length);
        const first = items[0], last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    });
  }
  if (scrim) scrim.addEventListener("click", closeMenu);

  // Fixed tooltips sit outside the narrow rail without clipping its scroll area.
  navigation?.querySelectorAll(".nav-link").forEach(link => {
    const positionTooltip = () => {
      const rect = link.getBoundingClientRect();
      const top = Math.max(20, Math.min(window.innerHeight - 20, rect.top + rect.height / 2));
      link.style.setProperty("--nav-tooltip-top", `${top}px`);
    };
    link.addEventListener("pointerenter", positionTooltip);
    link.addEventListener("focus", positionTooltip);
  });

  const closeAccountMenu = () => {
    if (!accountToggle || !accountMenu) return;
    accountMenu.hidden = true;
    accountToggle.setAttribute("aria-expanded", "false");
  };

  if (accountToggle && accountMenu) {
    accountToggle.addEventListener("click", (event) => {
      event.stopPropagation();
      const open = accountMenu.hidden;
      accountMenu.hidden = !open;
      accountToggle.setAttribute("aria-expanded", String(open));
      if (open) accountMenu.querySelector("[role='menuitem']")?.focus();
    });
    accountMenu.addEventListener("keydown", event => {
      const items = [...accountMenu.querySelectorAll("[role='menuitem']")];
      const index = items.indexOf(document.activeElement);
      if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
        event.preventDefault();
        const next = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1
          : (index + (event.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
        items[next].focus();
      }
    });
    accountMenu.parentElement.addEventListener("focusout", event => {
      if (!event.currentTarget.contains(event.relatedTarget)) closeAccountMenu();
    });
    accountMenu.addEventListener("click", (event) => event.stopPropagation());
    document.addEventListener("click", closeAccountMenu);
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      if (accountMenu && !accountMenu.hidden) {
        closeAccountMenu();
        accountToggle.focus();
      } else closeMenu();
    }
  });
})();
