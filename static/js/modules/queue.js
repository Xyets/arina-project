// queue.js — модуль очереди вибраций

export function initQueueButtons(socket, vibrationQueue, updateQueueUI, showToast, CURRENT_USER, CURRENT_MODE, CURRENT_PROFILE) {
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
