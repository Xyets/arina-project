import { CURRENT_USER, CURRENT_MODE, CURRENT_PROFILE } from "./core.js";
import { loadLogs } from "./logs.js";
import { startVibrationTimer, updateQueueUI, vibrationQueue } from "./queue.js";
import { showEntryPopup } from "./popup.js";
import { updateGoalCircle } from "./goal.js";
import { reloadInnerContent } from "./spa.js";
import { initRuleForms, initRuleModals } from "./rules.js";

export let socket = null;
let wsReconnectAttempts = 0;
const WS_MAX_RECONNECT = 10;

export function connectWS() {
    if (socket && socket.readyState === WebSocket.OPEN) return;

    const wsUrl = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`;
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
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

export function handleWSMessage(data) {

    if (data.type === "refresh_logs") {
        loadLogs();
        return;
    }

    if (data.status === "hello_ok") {
        socket.send(JSON.stringify({
            type: "get_queue",
            profile_key: `${CURRENT_USER}_${CURRENT_MODE}`
        }));
        return;
    }

    if (data.vibration) {
        startVibrationTimer(data.vibration.duration, data.vibration.strength);
        return;
    }

    if (data.queue_update) {
        vibrationQueue.length = 0;
        data.queue.forEach(v => vibrationQueue.push({ strength: v[0], duration: v[1] }));
        updateQueueUI();
        return;
    }

    if (data.entry) {
        showEntryPopup(`
            👤 <strong>${data.entry.name}</strong><br>
            🔢 Визитов: ${data.entry.visits}<br>
            💗 Чаевых всего: ${data.entry.total_tips}<br>
            📝 Заметки: ${data.entry.notes || "нет"}
        `);
        return;
    }

    if (data.goal_update) {
        updateGoalCircle(data.goal);
        return;
    }

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
