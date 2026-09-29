(() => {
  const LIST_SELECTOR = ".ai-conversation-list";
  const TRIGGER_CLASS = "ai-conversation-menu-trigger";
  const MENU_CLASS = "ai-conversation-menu";
  const SIDEBAR_WIDTH_KEY = "dental-ai-sidebar-width";
  const nativeTextareaValueSetter = Object.getOwnPropertyDescriptor(
    HTMLTextAreaElement.prototype,
    "value",
  )?.set;
  const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
    HTMLInputElement.prototype,
    "value",
  )?.set;

  function closeMenu() {
    document.querySelector(`.${MENU_CLASS}`)?.remove();
  }

  function setConversationTitle(value) {
    const field = document.querySelector(
      ".ai-conversation-title textarea, .ai-conversation-title input",
    );
    if (!field) return false;
    if (nativeTextareaValueSetter && field instanceof HTMLTextAreaElement) {
      nativeTextareaValueSetter.call(field, value);
    } else if (nativeInputValueSetter && field instanceof HTMLInputElement) {
      nativeInputValueSetter.call(field, value);
    } else {
      field.value = value;
    }
    field.dispatchEvent(new Event("input", { bubbles: true }));
    field.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }

  function clickHiddenAction(selector) {
    const component = document.querySelector(selector);
    const button = component?.matches("button")
      ? component
      : component?.querySelector("button");
    button?.click();
  }

  function currentTitle(label) {
    const text = label.querySelector(":scope > span")?.textContent?.trim() || "";
    return text.split(/\s+·\s+/u)[0].trim();
  }

  function positionMenu(menu, trigger) {
    const rect = trigger.getBoundingClientRect();
    const menuWidth = 188;
    const left = Math.max(12, Math.min(rect.right - menuWidth, innerWidth - menuWidth - 12));
    menu.style.left = `${left}px`;
    menu.style.top = `${rect.bottom + 6}px`;
  }

  function showRenameEditor(menu, label) {
    const editor = document.createElement("div");
    editor.className = "ai-conversation-menu-editor";
    const input = document.createElement("input");
    input.type = "text";
    input.maxLength = 80;
    input.value = currentTitle(label);
    input.setAttribute("aria-label", "新的对话名称");
    const actions = document.createElement("div");
    actions.className = "ai-conversation-menu-editor-actions";
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.textContent = "取消";
    const save = document.createElement("button");
    save.type = "button";
    save.textContent = "保存";
    save.className = "is-primary";
    actions.append(cancel, save);
    editor.append(input, actions);
    menu.replaceChildren(editor);
    input.focus();
    input.select();
    cancel.addEventListener("click", closeMenu);
    const commit = () => {
      const value = input.value.trim();
      if (!value || !setConversationTitle(value)) return;
      clickHiddenAction(".ai-conversation-rename-action");
      closeMenu();
    };
    save.addEventListener("click", commit);
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") commit();
      if (event.key === "Escape") closeMenu();
    });
  }

  function openMenu(trigger, label) {
    closeMenu();
    const radio = label.querySelector('input[type="radio"]');
    if (radio && !radio.checked) radio.click();
    const menu = document.createElement("div");
    menu.className = MENU_CLASS;
    menu.setAttribute("role", "menu");
    const rename = document.createElement("button");
    rename.type = "button";
    rename.textContent = "重命名";
    rename.setAttribute("role", "menuitem");
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "删除";
    remove.className = "is-danger";
    remove.setAttribute("role", "menuitem");
    menu.append(rename, remove);
    document.body.append(menu);
    positionMenu(menu, trigger);
    rename.addEventListener("click", () => showRenameEditor(menu, label));
    remove.addEventListener("click", () => {
      if (remove.dataset.confirmed !== "true") {
        remove.dataset.confirmed = "true";
        remove.textContent = "再次点击确认删除";
        return;
      }
      clickHiddenAction(".ai-conversation-delete-action");
      closeMenu();
    });
  }

  function decorateConversationItems(root = document) {
    root.querySelectorAll(`${LIST_SELECTOR} label`).forEach((label) => {
      if (label.querySelector(`.${TRIGGER_CLASS}`)) return;
      const trigger = document.createElement("button");
      trigger.type = "button";
      trigger.className = TRIGGER_CLASS;
      trigger.textContent = "⋯";
      trigger.title = "管理对话";
      trigger.setAttribute("aria-label", "管理对话");
      trigger.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        openMenu(trigger, label);
      });
      label.append(trigger);
    });
  }

  function sidebarBounds(layout) {
    const minimum = 240;
    const maximum = Math.max(minimum, Math.min(480, layout.clientWidth - 520));
    return { minimum, maximum };
  }

  function setSidebarWidth(layout, resizer, requestedWidth, persist = false) {
    const { minimum, maximum } = sidebarBounds(layout);
    const width = Math.round(Math.min(maximum, Math.max(minimum, requestedWidth)));
    layout.style.setProperty("--ai-sidebar-width", `${width}px`);
    resizer.setAttribute("aria-valuemin", String(minimum));
    resizer.setAttribute("aria-valuemax", String(maximum));
    resizer.setAttribute("aria-valuenow", String(width));
    if (persist) {
      try {
        localStorage.setItem(SIDEBAR_WIDTH_KEY, String(width));
      } catch (_) {
        // The layout remains draggable when browser storage is unavailable.
      }
    }
  }

  function storedSidebarWidth() {
    try {
      const value = Number(localStorage.getItem(SIDEBAR_WIDTH_KEY));
      return Number.isFinite(value) ? value : 300;
    } catch (_) {
      return 300;
    }
  }

  function initializeSidebarResizer(root = document) {
    root.querySelectorAll(".ai-sidebar-resizer").forEach((resizer) => {
      if (resizer.dataset.ready === "true") return;
      const layout = resizer.closest(".ai-chat-layout");
      if (!layout) return;
      resizer.dataset.ready = "true";
      setSidebarWidth(layout, resizer, storedSidebarWidth());

      resizer.addEventListener("pointerdown", (event) => {
        if (event.button !== 0) return;
        event.preventDefault();
        const layoutRect = layout.getBoundingClientRect();
        let latestWidth = Number(resizer.getAttribute("aria-valuenow")) || 300;
        resizer.classList.add("is-dragging");
        document.body.classList.add("ai-sidebar-resizing");

        const move = (moveEvent) => {
          latestWidth = moveEvent.clientX - layoutRect.left;
          setSidebarWidth(layout, resizer, latestWidth);
        };
        const finish = () => {
          setSidebarWidth(layout, resizer, latestWidth, true);
          resizer.classList.remove("is-dragging");
          document.body.classList.remove("ai-sidebar-resizing");
          window.removeEventListener("pointermove", move);
          window.removeEventListener("pointerup", finish);
          window.removeEventListener("pointercancel", finish);
        };
        window.addEventListener("pointermove", move);
        window.addEventListener("pointerup", finish);
        window.addEventListener("pointercancel", finish);
      });

      resizer.addEventListener("keydown", (event) => {
        if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
        event.preventDefault();
        const current = Number(resizer.getAttribute("aria-valuenow")) || 300;
        const offset = event.key === "ArrowLeft" ? -16 : 16;
        setSidebarWidth(layout, resizer, current + offset, true);
      });

      resizer.addEventListener("dblclick", () => {
        setSidebarWidth(layout, resizer, 300, true);
      });

      new ResizeObserver(() => {
        const current = Number(resizer.getAttribute("aria-valuenow")) || 300;
        setSidebarWidth(layout, resizer, current);
      }).observe(layout);
    });
  }

  function initializeWorkspace(root = document) {
    decorateConversationItems(root);
    initializeSidebarResizer(root);
  }

  document.addEventListener("click", (event) => {
    const clickedInsideWorkspaceMenu = event.composedPath().some(
      (node) =>
        node instanceof Element &&
        (node.classList.contains(MENU_CLASS) ||
          node.classList.contains(TRIGGER_CLASS)),
    );
    if (!clickedInsideWorkspaceMenu) closeMenu();
  });
  window.addEventListener("scroll", closeMenu, { passive: true });
  window.addEventListener("resize", closeMenu);

  const observer = new MutationObserver(() => initializeWorkspace());
  observer.observe(document.documentElement, { childList: true, subtree: true });
  initializeWorkspace();
})();
