document.addEventListener("submit", (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement)) return;
  const confirmMsg = form.getAttribute("data-confirm");
  const submitter = event.submitter;
  const buttonMsg = submitter && submitter.getAttribute("data-confirm");
  const message = buttonMsg || confirmMsg;
  if (message && !window.confirm(message)) {
    event.preventDefault();
  }
});

document.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  if (target.classList.contains("remove-row")) {
    const row = target.closest("li");
    if (row) row.remove();
  }
  if (target.classList.contains("move-up") || target.classList.contains("move-down")) {
    const row = target.closest("li");
    const list = row && row.parentElement;
    if (!row || !list) return;
    if (target.classList.contains("move-up") && row.previousElementSibling) {
      list.insertBefore(row, row.previousElementSibling);
    }
    if (target.classList.contains("move-down") && row.nextElementSibling) {
      list.insertBefore(row.nextElementSibling, row);
    }
  }
});

document.querySelectorAll("[data-filter]").forEach((input) => {
  input.addEventListener("input", () => {
    const sel = input.getAttribute("data-filter");
    const root = sel && document.querySelector(sel);
    if (!root) return;
    const q = input.value.toLowerCase();
    root.querySelectorAll("[data-filter-text]").forEach((node) => {
      const hay = (node.getAttribute("data-filter-text") || "").toLowerCase();
      node.style.display = hay.includes(q) ? "" : "none";
    });
  });
});

function enableDrag(list) {
  let dragging = null;
  list.querySelectorAll(":scope > li[draggable]").forEach((item) => {
    item.addEventListener("dragstart", () => {
      dragging = item;
      item.classList.add("dragging");
    });
    item.addEventListener("dragend", () => {
      item.classList.remove("dragging");
      dragging = null;
    });
    item.addEventListener("dragover", (event) => {
      event.preventDefault();
      if (!dragging || dragging === item) return;
      const rect = item.getBoundingClientRect();
      const before = event.clientY < rect.top + rect.height / 2;
      list.insertBefore(dragging, before ? item : item.nextSibling);
    });
  });
}

document.querySelectorAll("[data-sortable]").forEach(enableDrag);
