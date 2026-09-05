import { CURRENT_USER, CURRENT_MODE, CURRENT_PROFILE } from "./core.js";
import { loadLogs } from "./logs.js";
import { startVibrationTimer, updateQueueUI } from "./queue.js";
import { showEntryPopup } from "./popup.js";
import { updateGoalCircle } from "./goal.js";
import { reloadInnerContent } from "./spa.js";
import { initRuleForms, initRuleModals } from "./rules.js";
import { vibrationQueue } from "./queue.js";

export let socket = null;
let wsReconnectAttempts = 0;
const WS_MAX_RECONNECT = 10;

/* ============================================================
   📡 WebSocket connect
============================================================ */
export function connectWS() {
    if (socket && socket.readyState === WebSocket.OPEN) return;

    const wsUrl = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`;
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
        console.log("WS connected");
        wsReconnectAttempts = 0;

        const profile_key = CURRENT_PROFILE || `${CURRENT_USER}_${CURRENT_MODE}`;

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

    socket.onclose = () => {
        console.log("WS closed");

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

/* ============================================================
   📡 WebSocket message handler
============================================================ */
export function handleWSMessage(data) {
    console.log("WS:", data);

    /* Логи */
    if (data.type === "refresh_logs") {
        loadLogs();
        return;
    }

    /* После hello → запрос очереди */
    if (data.status === "hello_ok") {
        socket.send(JSON.stringify({
            type: "get_queue",
            profile_key: `${CURRENT_USER}_${CURRENT_MODE}`
        }));
        return;
    }

    /* Вибрация */
    if (data.vibration) {
        startVibrationTimer(data.vibration.duration, data.vibration.strength);
        return;
    }

    /* Обновление очереди */
    if (data.queue_update) {
        vibrationQueue.splice(0, vibrationQueue.length, 
            ...data.queue.map(v => ({ strength: v[0], duration: v[1] }))
        );
        updateQueueUI();
        return;
    }


    /* Popup входа */
    if (data.entry) {
        showEntryPopup(`
            👤 <strong>${data.entry.name}</strong><br>
            🔢 Визитов: ${data.entry.visits}<br>
            💗 Чаевых всего: ${data.entry.total_tips}<br>
            📝 Заметки: ${data.entry.notes || "нет"}
        `);
        return;
    }

    /* Обновление цели */
    if (data.goal_update) {
        updateGoalCircle(data.goal);
        return;
    }

    /* Обновление правил */
    if (data.rules_update) {
        reloadInnerContent(() => {
            if (document.querySelector(".rules-page")) {
                initRuleForms();
                initRuleModals();
            }
        });
        return;
    }
}