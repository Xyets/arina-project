/* ============================================================
   📌 0. Инициализация данных из HTML
============================================================ */
const app = document.getElementById("app");
const CURRENT_USER = app?.dataset.user || "";
let CURRENT_MODE = app?.dataset.mode || "public";
let CURRENT_PROFILE = app?.dataset.profile || "";

/* ============================================================
   📡 1. WebSocket подключение
============================================================ */
let socket = null;

function connectWS() {
    if (socket && socket.readyState === WebSocket.OPEN) return;

    const wsUrl = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`;
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
        console.log("WS connected");

        const profile_key = `${CURRENT_USER}_${CURRENT_MODE}`;

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

        setTimeout(() => {
            if (!socket || socket.readyState === WebSocket.CLOSED) {
                connectWS();
            }
        }, 2000);
    };

    socket.onmessage = (event) => {
        let data;
        try { data = JSON.parse(event.data); }
        catch { return; }

        handleWSMessage(data);
    };
}

connectWS();

/* ============================================================
   📡 2. Обработка входящих WS сообщений
============================================================ */
function handleWSMessage(data) {
    console.log("WS:", data);

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
        vibrationQueue = (data.queue || []).map(v => ({
            strength: v[0],
            duration: v[1]
        }));
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
        updateGoalUI(data.goal);
        return;
    }
}

window.addEventListener("load", () => {

    const modeSwitch = document.getElementById("modeSwitch");
    if (!modeSwitch) {
        console.log("⚠️ modeSwitch не найден");
        return;
    }

    console.log("🔧 modeSwitch найден, назначаю обработчик");

    modeSwitch.addEventListener("change", () => {
        const newMode = modeSwitch.checked ? "private" : "public";

        console.log("🔄 Переключение режима:", newMode);

        socket.send(JSON.stringify({
            type: "set_mode",
            user: CURRENT_USER,
            mode: newMode
        }));

        fetch("/set_mode", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mode: newMode })
        })
        .then(r => r.json())
        .then(data => {
            console.log("📩 Ответ от /set_mode:", data);

            if (data.status === "ok") {
                CURRENT_MODE = newMode;
                reloadInnerContent();
                showToast(`Режим переключен: ${newMode}`);
            }
        });
    });
    /* ============================================================
       📦 Sidebar collapse — ВСТАВИТЬ СЮДА
    ============================================================ */

    const sidebar = document.getElementById("sidebar");
    const sidebarLogo = document.getElementById("sidebarLogo");

    if (sidebar && sidebarLogo) {
        sidebarLogo.addEventListener("click", () => {
            sidebar.classList.toggle("collapsed");
        });
    }
});


/* ============================================================
   🔄 Мгновенное обновление внутреннего контента без мигания
============================================================ */
function reloadInnerContent() {
    const container = document.querySelector(".content-inner");
    if (!container) return;

    // плавное исчезновение
    container.style.opacity = "0";

    fetch(window.location.pathname)
        .then(r => r.text())
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, "text/html");

            const newContent = doc.querySelector(".content-inner").innerHTML;

            // заменяем контент
            container.innerHTML = newContent;

            // плавное появление
            setTimeout(() => {
                container.style.opacity = "1";
            }, 50);

            // перезапуск логики
            connectWS();
            loadLogs();
            updateQueueUI();
        });
}


/* ============================================================
   📜 3. Логи
============================================================ */
let lastLogCount = 0;

async function loadLogs() {
    const res = await fetch("/logs_data");
    const data = await res.json();
    const box = document.getElementById("logbox");

    if (!box) return;

    const logs = data.logs || [];
    const newLogs = logs.slice(lastLogCount);
    lastLogCount = logs.length;

    newLogs.forEach(log => {
        const div = document.createElement("div");
        div.className = "event-item";
        div.textContent = log;
        box.appendChild(div);
        box.scrollTop = box.scrollHeight;
    });
}

setInterval(loadLogs, 2000);

/* ============================================================
   🔁 4. Очередь вибраций
============================================================ */
let vibrationQueue = [];
let vibrationTimerRunning = false;

function updateQueueUI() {
    const box = document.getElementById("queuebox");
    if (!box) return;

    if (vibrationQueue.length === 0) {
        box.innerHTML = `<div class="empty">Очередь пуста</div>`;
        return;
    }

    box.innerHTML = vibrationQueue
        .map((v, i) => `<div>#${i + 1} → сила: ${v.strength}, время: ${v.duration}s</div>`)
        .join("");
}

function sendStop() {
    const profile_key = `${CURRENT_USER}_${CURRENT_MODE}`;

    socket.send(JSON.stringify({
        type: "stop",
        user: CURRENT_USER,
        profile_key
    }));

    console.log("⛔ STOP SENT:", profile_key);
}

/* ============================================================
   ⏱ 5. Таймер вибрации — новый красивый стиль
============================================================ */
function startVibrationTimer(duration, strength) {
    if (vibrationTimerRunning) return;
    vibrationTimerRunning = true;

    const container = document.getElementById("vibrationTimersContainer");
    const box = document.createElement("div");
    box.className = "vibration-timer";

    box.innerHTML = `
        <div class="vibration-title">💖 Вибрация • Сила ${strength}</div>

        <div class="vibration-time">
            Осталось: <span class="time">${Math.ceil(duration)}</span> сек
        </div>

        <div class="vibration-progress">
            <div class="vibration-progress-fill"></div>
        </div>

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
            vibrationTimerRunning = false;
        } else {
            timeSpan.textContent = Math.ceil(remaining);
            progressFill.style.width = `${(remaining / duration) * 100}%`;
        }
    }, 1000);

    box.querySelector(".vibration-stop-btn").onclick = () => {
        sendStop();
        clearInterval(interval);
        box.remove();
        vibrationTimerRunning = false;
    };
}

/* ============================================================
   🔔 6. Popup — улучшенный, как в старой версии
============================================================ */
function showEntryPopup(message) {
    const popup = document.getElementById("entryPopup");
    popup.innerHTML = `<div>${message}</div><button onclick="hideEntryPopup()">ОК</button>`;
    popup.classList.add("show");

    let hideTimer = setTimeout(hideEntryPopup, 8000);

    popup.onmouseenter = () => clearTimeout(hideTimer);
    popup.onmouseleave = () => hideTimer = setTimeout(hideEntryPopup, 8000);
}

function hideEntryPopup() {
    const popup = document.getElementById("entryPopup");
    popup.classList.remove("show");
}

/* ============================================================
   🔔 7. Toast
============================================================ */
function showToast(msg) {
    const toast = document.getElementById("toast");
    toast.textContent = msg;
    toast.classList.add("show");
    setTimeout(() => toast.classList.remove("show"), 3000);
}

/* ============================================================
   🎯 8. Цель
============================================================ */
function updateGoalUI(newGoal = null) {
    if (newGoal) goal = newGoal;

    const fillV = document.getElementById("goalFillVertical");
    const cur = document.getElementById("goalCurrent");
    const tgt = document.getElementById("goalTarget");

    if (!fillV || !cur || !tgt) return;

    const percent = goal.target > 0 ? (goal.current / goal.target) * 100 : 0;

    fillV.style.height = Math.min(percent, 100) + "%";
    cur.textContent = goal.current;
    tgt.textContent = goal.target;
}

function openGoalModal() {
    document.getElementById("goalModal").classList.add("show");
}

function closeGoalModal() {
    document.getElementById("goalModal").classList.remove("show");
}

/* ============================================================
   🧹 9. Очистка логов — новая маленькая кнопка
============================================================ */
const clearLogsBtn = document.getElementById("clearLogsBtn");
if (clearLogsBtn) {
    clearLogsBtn.addEventListener("click", () => {
        lastLogCount = 0;
        document.getElementById("logbox").innerHTML = "";

        fetch("/clear_logs", { method: "POST" })
            .then(() => showToast("Логи очищены ✅"))
            .catch(() => showToast("❌ Ошибка при очистке логов"));
    });
}

/* ============================================================
   🧹 10. Очистка очереди вибраций — новая маленькая кнопка
============================================================ */
const clearQueueBtn = document.getElementById("clearQueueBtn");
if (clearQueueBtn) {
    clearQueueBtn.addEventListener("click", () => {
        const profile_key = `${CURRENT_USER}_${CURRENT_MODE}`;

        socket.send(JSON.stringify({
            type: "clear_queue",
            profile_key
        }));

        vibrationQueue = [];
        updateQueueUI();
        showToast("Очередь очищена ✅");
    });
}
