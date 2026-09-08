// queue.js — модуль управления очередью вибраций FlowTip

import { socket, vibrationQueue, updateQueueUI } from "/static/js/modules/websocket.js";
import { showToast } from "/static/js/modules/core.js";

/**
 * Инициализация кнопки очистки очереди
 * clearQueueBtn появляется только на страницах, где есть очередь
 */
export function initQueueButtons(CURRENT_USER, CURRENT_MODE, CURRENT_PROFILE) {
    const clearQueueBtn = document.getElementById("clearQueueBtn");
    if (!clearQueueBtn) return;

    clearQueueBtn.onclick = () => {
        const profile_key = CURRENT_PROFILE || `${CURRENT_USER}_${CURRENT_MODE}`;

        // отправляем команду на сервер
        socket.send(JSON.stringify({
            type: "clear_queue",
            profile_key
        }));

        // очищаем локальную очередь
        vibrationQueue.length = 0;

        // обновляем UI
        updateQueueUI();

        // уведомление
        showToast("Очередь очищена ✅");
    };
}
