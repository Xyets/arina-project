
 // qr.js — QR-код отдельный для каждой модели.
 // Приватный и публичный режимы одной модели используют общий QR.

function qrCacheKey(uid) {
    return `qr_code_${uid}`;
}

// Запрос QR-кода с сервера
async function requestQR(refresh = false) {
    const url = refresh
        ? "/qr_generate?refresh=1"
        : "/qr_generate";

    const response = await fetch(url, {
        cache: "no-store"
    });

    const data = await response.json();

    if (
        !response.ok ||
        data.status !== "ok" ||
        !data.qr ||
        !data.uid
    ) {
        throw new Error(
            data.message || "Не удалось получить QR-код Lovense"
        );
    }

    // Сохраняем QR отдельно для UID каждой модели.
    localStorage.setItem(qrCacheKey(data.uid), data.qr);

    return data;
}

// Загрузка QR-кода при открытии страницы
export async function loadQR() {
    const img = document.getElementById("qrImage");

    if (!img) return;

    try {
        const data = await requestQR(false);

        img.src = data.qr;
        img.dataset.modelUid = data.uid;
    } catch (error) {
        console.error("Ошибка загрузки QR-кода:", error);
        img.removeAttribute("src");
    }
}

// Обновление QR-кода по нажатию кнопки
export async function refreshQR(showToast) {
    const img = document.getElementById("qrImage");

    if (!img) return;

    try {
        const data = await requestQR(true);

        img.src = data.qr;
        img.dataset.modelUid = data.uid;

        if (typeof showToast === "function") {
            showToast("QR-код обновлён");
        }
    } catch (error) {
        console.error("Ошибка обновления QR-кода:", error);

        if (typeof showToast === "function") {
            showToast("Не удалось обновить QR-код");
        }
    }
}
