export function showEntryPopup(message) {
    const popup = document.getElementById("entryPopup");
    if (!popup) return;
    popup.innerHTML = `<div>${message}</div><button id="closePopupBtn">ОК</button>`;
    popup.classList.add("show");

    document.getElementById("closePopupBtn")?.addEventListener("click", hideEntryPopup);

    let hideTimer = setTimeout(hideEntryPopup, 8000);
    popup.onmouseenter = () => clearTimeout(hideTimer);
    popup.onmouseleave = () => hideTimer = setTimeout(hideEntryPopup, 8000);
}

export function hideEntryPopup() {
    const popup = document.getElementById("entryPopup");
    if (popup) popup.classList.remove("show");
}

window.hideEntryPopup = hideEntryPopup;