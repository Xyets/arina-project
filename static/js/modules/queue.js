// ============================================================
// 🔁 Очередь вибраций — стеклянный стиль
// ============================================================

import { CURRENT_USER, CURRENT_MODE, CURRENT_PROFILE } from "./core.js";
import { socket } from "./websocket.js";
import { showToast } from "./toast.js";

// Глобальная очередь вибраций (единая для всех модулей)
export let vibrationQueue = [];

/* ============================================================
   📦 Обновление UI очереди
============================================================ */
export function updateQueueUI() {
    const box = document.getElementById("queuebox");
    if (!box) return;

    if (vibrationQueue.length === 0) {
        box.innerHTML = `<div class="empty">Очередь пуста</div>`;
        return;
    }

    box.innerHTML = vibrationQueue
        .map((v, i) => `
            <div class="queue-item">
                <strong>#${i + 1}</strong> • сила ${v.strength}, ${v.duration}s
            </div>
        `)
        .join("");
}

/* ============================================================
   🧹 Кнопка очистки очереди
============================================================ */
export function initQueueButtons() {
    const clearQueueBtn = document.getElementById("clearQueueBtn");
    if (!clearQueueBtn) return;

    clearQueueBtn.onclick = () => {
        const profile_key = CURRENT_PROFILE || `${CURRENT_USER}_${CURRENT_MODE}`;

        socket.send(JSON.stringify({
            type: "clear_queue",
            profile_key
        }));

        vibrationQueue.length = 0;
        updateQueueUI();
        showToast("Очередь очищена ✅");
    };
}

/* ============================================================
   ⏱ Таймер вибрации
============================================================ */
export function startVibrationTimer(duration, strength) {

    // Сбрасываем блокировку при SPA-переходах
    if (!window._vibrationTimerActive) {
        window._vibrationTimerActive = false;
    }

    if (window._vibrationTimerActive) {
        console.warn("Таймер уже активен — второй не запускаем");
        return;
    }
    window._vibrationTimerActive = true;

    const container = document.getElementById("vibrationOverlay");
    if (!container) return;

    const box = document.createElement("div");
    box.className = "vibration-timer";

    box.innerHTML = `
        <div class="vibration-title">💖 Вибрация • Сила ${strength}</div>
        <div class="vibration-time">Осталось: <span class="time">${Math.ceil(duration)}</span> сек</div>
        <div class="vibration-progress"><div class="vibration-progress-fill"></div></div>
        <button class="vibration-stop-btn">Остановить</button>
    `;

    container.appendChild(box);

    let remaining = duration;
    const timeSpan = box.querySelector(".time");
    const progressFill = box.querySelector(".vibration-progress-fill");

    const interval = setInterval(() => {
        remaining -= 1;

        if (remaining <= 0) {
            clearInterval(interval);
            box.remove();
            window._vibrationTimerActive = false;
        } else {
            timeSpan.textContent = Math.ceil(remaining);
            progressFill.style.width = `${(remaining / duration) * 100}%`;
        }
    }, 1000);

    box.querySelector(".vibration-stop-btn").onclick = () => {
        sendStop();
        clearInterval(interval);
        box.remove();
        window._vibrationTimerActive = false;
    };
}

/* ============================================================
   ⛔ Остановка вибрации
============================================================ */
export function sendStop() {
    const profile_key = CURRENT_PROFILE || `${CURRENT_USER}_${CURRENT_MODE}`;

    socket.send(JSON.stringify({
        type: "stop",
        user: CURRENT_USER,
        profile_key
    }));
}
