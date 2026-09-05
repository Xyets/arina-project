import { showToast } from "./toast.js";

let savedQR = localStorage.getItem("qr_code");

// ============================================================
// 📱 Загрузка QR
// ============================================================

export function loadQR() {
    const img = document.getElementById("qrImage");
    if (!img) return;

    if (savedQR) {
        img.src = savedQR;
        return;
    }

    fetch("/qr_generate")
        .then(r => r.json())
        .then(data => {
            savedQR = data.qr;
            localStorage.setItem("qr_code", savedQR);
            img.src = savedQR;
        });
}

// ============================================================
// 📱 Обновление QR
// ============================================================

export function refreshQR() {
    const img = document.getElementById("qrImage");
    if (!img) return;

    fetch("/qr_generate?refresh=1")
        .then(r => r.json())
        .then(data => {
            savedQR = data.qr;
            localStorage.setItem("qr_code", savedQR);
            img.src = savedQR;
            showToast("QR‑код обновлён");
        });
}
