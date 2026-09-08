// ui.js — Popup + Toast

// 🔔 Popup
export function showEntryPopup(message) {
    const popup = document.getElementById("entryPopup");
    if (!popup) return;

    popup.innerHTML = `<div>${message}</div><button onclick="hideEntryPopup()">ОК</button>`;
    popup.classList.add("show");

    let hideTimer = setTimeout(hideEntryPopup, 8000);

    popup.onmouseenter = () => clearTimeout(hideTimer);
    popup.onmouseleave = () => hideTimer = setTimeout(hideEntryPopup, 8000);
}

export function hideEntryPopup() {
    const popup = document.getElementById("entryPopup");
    if (!popup) return;

    popup.classList.remove("show");
}

// 🔔 Toast
export function showToast(msg) {
    const toast = document.getElementById("toast");
    if (!toast) return;

    toast.textContent = msg;
    toast.classList.add("show");

    setTimeout(() => toast.classList.remove("show"), 3000);
}
