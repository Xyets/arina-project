// websocket.js — модуль WebSocket для FlowTip

import {
    createDeleteRule,
    createDeleteSegment
} from "./rules.js";

export let socket = null;
let wsReconnectAttempts = 0;
const WS_MAX_RECONNECT = 10;

export function initWebSocket(CURRENT_USER, CURRENT_MODE, CURRENT_PROFILE, reloadInnerContent, showToast) {

    // Делаем переменные глобальными для sendStop()
    window.CURRENT_USER = CURRENT_USER;
    window.CURRENT_MODE = CURRENT_MODE;
    window.CURRENT_PROFILE = CURRENT_PROFILE;

    function connectWS() {
        if (socket && socket.readyState === WebSocket.OPEN) return;

        const wsUrl = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`;
        socket = new WebSocket(wsUrl);

        socket.onopen = () => {
            wsReconnectAttempts = 0;

            const profile_key = window.CURRENT_PROFILE || `${window.CURRENT_USER}_${window.CURRENT_MODE}`;

            socket.send(JSON.stringify({
                type: "hello",
                role: "panel",
                profile_key
            }));

            if (socket._pingInterval) clearInterval(socket._pingInterval);
            socket._pingInterval = setInterval(() => {
                if (socket.readyState === WebSocket.OPEN) {
                    socket.send(JSON.stringify({ type: "ping" }));
                }
            }, 30000);
        };

        // глобальные функции для HTML onclick
        window.deleteRule = createDeleteRule(socket, window.CURRENT_PROFILE, reloadInnerContent, showToast);
        window.deleteSegment = createDeleteSegment(socket, window.CURRENT_PROFILE, reloadInnerContent, showToast);

        socket.onclose = () => {
            if (socket._pingInterval) clearInterval(socket._pingInterval);

            if (wsReconnectAttempts < WS_MAX_RECONNECT) {
                wsReconnectAttempts++;
                setTimeout(connectWS, 2000);
            }
        };

        socket.onmessage = (event) => {
            let data;
            try { data = JSON.parse(event.data); }
            catch { return; }

            handleWSMessage(data);
        };
    }

    function handleWSMessage(data) {

        if (data.type === "refresh_logs") {
            if (typeof window.loadLogs === "function") window.loadLogs();
            return;
        }

        if (data.status === "hello_ok") {
            return;
        }

        if (data.vibration) {
            startVibrationTimer(data.vibration.duration, data.vibration.strength);
            return;
        }

        if (data.queue_update) {
            // ВАЖНО: сохраняем ссылку на массив
            vibrationQueue.length = 0;
            (data.queue || []).forEach(v => {
                vibrationQueue.push({
                    strength: v[0],
                    duration: v[1]
                });
            });
            updateQueueUI();
            return;
        }

        if (data.entry) {
            if (typeof window.showEntryPopup === "function") {
                window.showEntryPopup(`
                    👤 <strong>${data.entry.name}</strong><br>
                    🔢 Визитов: ${data.entry.visits}<br>
                    💗 Чаевых всего: ${data.entry.total_tips}<br>
                    📝 Заметки: ${data.entry.notes || "нет"}
                `);
            }
            return;
        }

        if (data.goal_update) {
            if (typeof window.updateGoalCircle === "function") {
                window.updateGoalCircle(data.goal);
            }
            return;
        }

        if (data.rules_update) {
            reloadInnerContent(() => {
                if (document.querySelector(".rules-page")) {
                    window.initRuleForms?.(window.CURRENT_PROFILE, socket, reloadInnerContent, showToast);
                    window.initRuleModals?.();
                }
            });
            return;
        }

        if (data.vip_update) {
            if (typeof window.loadVipList === "function") {
                window.loadVipList();
            }
            return;
        }
    }

    connectWS();
}


// =========================
// ВИБРАЦИИ
// =========================

export let vibrationQueue = [];

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

export function startVibrationTimer(duration, strength) {
    if (window._vibrationTimerActive) return;
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

export function sendStop() {
    const profile_key = window.CURRENT_PROFILE || `${window.CURRENT_USER}_${window.CURRENT_MODE}`;

    socket.send(JSON.stringify({
        type: "stop",
        user: window.CURRENT_USER,
        profile_key
    }));
}
