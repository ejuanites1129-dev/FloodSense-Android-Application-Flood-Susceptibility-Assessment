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

  const closeMenu = () => {
    if (!menuButton || !sidebar) return;
    sidebar.classList.remove("sidebar--open");
    document.body.classList.remove("menu-open");
    menuButton.setAttribute("aria-expanded", "false");
  };

  if (menuButton && sidebar) {
    menuButton.addEventListener("click", () => {
      const open = !sidebar.classList.contains("sidebar--open");
      sidebar.classList.toggle("sidebar--open", open);
      document.body.classList.toggle("menu-open", open);
      menuButton.setAttribute("aria-expanded", String(open));
    });
  }
  if (scrim) scrim.addEventListener("click", closeMenu);

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
    });
    accountMenu.addEventListener("click", (event) => event.stopPropagation());
    document.addEventListener("click", closeAccountMenu);
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeMenu();
      closeAccountMenu();
      if (accountToggle) accountToggle.focus();
    }
  });
})();
