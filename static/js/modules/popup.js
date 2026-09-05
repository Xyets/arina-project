// ============================================================
// 🔔 Popup — вход пользователя
// ============================================================

export function showEntryPopup(message) {
    const popup = document.getElementById("entryPopup");
    popup.innerHTML = `<div>${message}</div><button id="popupOkBtn">ОК</button>`;
    popup.classList.add("show");

    let hideTimer = setTimeout(hideEntryPopup, 8000);

    popup.onmouseenter = () => clearTimeout(hideTimer);
    popup.onmouseleave = () => hideTimer = setTimeout(hideEntryPopup, 8000);

    document.getElementById("popupOkBtn").onclick = hideEntryPopup;
}

export function hideEntryPopup() {
    const popup = document.getElementById("entryPopup");
    popup.classList.remove("show");
}
