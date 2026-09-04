let CURRENT_PAGE_URL = "/beta";

/* ============================================================
   📌 0. Инициализация данных из HTML
============================================================ */
const app = document.getElementById("app");
const CURRENT_USER = app?.dataset.user || "";
let CURRENT_MODE = app?.dataset.mode || "public";
let CURRENT_PROFILE = app?.dataset.profile || "";

// глобальная цель
let goal = {
    title: "",
    current: 0,
    target: 0
};

/* ============================================================
   📡 1. WebSocket подключение
============================================================ */
let socket = null;
let wsReconnectAttempts = 0;
const WS_MAX_RECONNECT = 10;

function connectWS() {
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

    if (data.rules_update) {
        reloadInnerContent(() => {
            if (document.querySelector(".rules-page")) {
                initRulesPage();
                initRuleForms();
                initRuleModals();
            }
        });
        return;
    }
}

/* ============================================================
   📦 3. Инициализация обработчиков
============================================================ */
function initHandlers() {
    initSidebarCollapse();
    initModeSwitch();
    initLogButtons();
    initQueueButtons();
    initGoalModal();
}

window.addEventListener("load", () => {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
        connectWS();
    }
    initHandlers();
    initSidebarNavigation();
    loadQR();
    loadGoalFromServer();   // ← исправлено
});


/* ============================================================
   📦 SPA навигация
============================================================ */
function initSidebarNavigation() {
    const links = document.querySelectorAll(".sidebar-menu .sidebar-item");

    links.forEach(link => {
        link.addEventListener("click", (e) => {
            e.preventDefault();
            const url = link.getAttribute("href");
            navigateSPA(url);
        });
    });
}

function navigateSPA(url) {
    CURRENT_PAGE_URL = url;

    const container = document.querySelector(".content-inner");
    if (!container) {
        window.location.href = url;
        return;
    }

    container.style.opacity = "0";

    fetch(url + "?mode=" + CURRENT_MODE)
        .then(r => r.text())
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, "text/html");
            const newContent = doc.querySelector(".content-inner").innerHTML;

            container.innerHTML = newContent;

            setTimeout(() => {
                container.style.opacity = "1";

                if (document.querySelector(".rules-page")) {
                    initRulesPage();
                    initRuleForms();
                    initRuleModals();

                    setTimeout(() => {
                        initRulesPage();
                    }, 0);
                }

                loadLogs();
                updateQueueUI();
                loadQR();
                updateGoalUI();
            }, 50);
        });
}

/* ============================================================
   📦 Sidebar collapse
============================================================ */
function initSidebarCollapse() {
    const sidebar = document.getElementById("sidebar");
    const sidebarLogo = document.getElementById("sidebarLogo");

    if (sidebar && sidebarLogo) {
        sidebarLogo.onclick = () => sidebar.classList.toggle("collapsed");
    }
}

/* ============================================================
   🔄 Переключатель режима
============================================================ */
function initModeSwitch() {
    const modeSwitch = document.getElementById("modeSwitch");
    if (!modeSwitch) return;

    modeSwitch.onchange = () => {
        const newMode = modeSwitch.checked ? "private" : "public";

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
            if (data.status === "ok") {
                CURRENT_MODE = newMode;
                CURRENT_PROFILE = `${CURRENT_USER}_${CURRENT_MODE}`;

                socket.send(JSON.stringify({
                    type: "hello",
                    role: "panel",
                    profile_key: CURRENT_PROFILE
                }));

                reloadInnerContent(() => {
                    if (document.querySelector(".rules-page")) {
                        initRulesPage();
                        initRuleForms();
                        initRuleModals();
                    }
                });

                showToast(`Режим переключен: ${newMode}`);
            }
        });
    };
}

/* ============================================================
   🔄 Мгновенное обновление внутреннего контента
============================================================ */
function reloadInnerContent(callback) {
    const container = document.querySelector(".content-inner");
    if (!container) return;

    container.style.opacity = "0";

    fetch(CURRENT_PAGE_URL + "?mode=" + CURRENT_MODE)
        .then(r => r.text())
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, "text/html");

            const newContent = doc.querySelector(".content-inner").innerHTML;
            container.innerHTML = newContent;

            setTimeout(() => {
                container.style.opacity = "1";

                if (callback) {
                    callback();
                } else {
                    initHandlers();

                    if (document.querySelector(".rules-page")) {
                        initRulesPage();
                        initRuleForms();
                        initRuleModals();
                    }
                }

                loadLogs();
                updateQueueUI();
                loadQR();
                loadGoalFromServer(); 

            }, 50);
        });
}

/* ============================================================
   📜 Цветные логи
============================================================ */

function classifyLog(log) {
    log = log.toLowerCase();

    if (log.includes("вибрация")) return "vibration";
    if (log.includes("колесо")) return "wheel";
    if (log.includes("действие")) return "action";
    if (log.includes("вошёл") || log.includes("вошел")) return "entry";
    if (log.includes("вышел")) return "exit";
    return "system";
}

let lastLogCount = 0;
let logInterval = setInterval(loadLogs, 2000);

async function loadLogs() {
    const box = document.getElementById("logbox");
    if (!box) return;

    const res = await fetch("/logs_data");
    const data = await res.json();

    const logs = data.logs || [];
    const newLogs = logs.slice(lastLogCount);
    lastLogCount = logs.length;

    newLogs.forEach(log => {
        const div = document.createElement("div");
        const type = classifyLog(log);
        div.className = `event-item ${type}`;
        div.textContent = log;

        box.appendChild(div);
        box.scrollTop = box.scrollHeight;
    });
}

/* ============================================================
   🔁 Очередь вибраций — стеклянный стиль
============================================================ */
let vibrationQueue = [];

function updateQueueUI() {
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

function initQueueButtons() {
    const clearQueueBtn = document.getElementById("clearQueueBtn");
    if (!clearQueueBtn) return;

    clearQueueBtn.onclick = () => {
        const profile_key = CURRENT_PROFILE || `${CURRENT_USER}_${CURRENT_MODE}`;

        socket.send(JSON.stringify({
            type: "clear_queue",
            profile_key
        }));

        vibrationQueue = [];
        updateQueueUI();
        showToast("Очередь очищена ✅");
    };
}

/* ============================================================
   ⏱ Таймер вибрации
============================================================ */
function startVibrationTimer(duration, strength) {

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

function sendStop() {
    const profile_key = CURRENT_PROFILE || `${CURRENT_USER}_${CURRENT_MODE}`;

    socket.send(JSON.stringify({
        type: "stop",
        user: CURRENT_USER,
        profile_key
    }));
}

/* ============================================================
   🔔 Popup
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
   🔔 Toast
============================================================ */
function showToast(msg) {
    const toast = document.getElementById("toast");
    toast.textContent = msg;
    toast.classList.add("show");
    setTimeout(() => toast.classList.remove("show"), 3000);
}

/* ============================================================
   🎯 Постоянная цель
============================================================ */
function updateGoalUI(newGoal = null) {
    if (newGoal) goal = newGoal;

    const fill = document.querySelector(".goal-fill");
    const cur = document.getElementById("goalCurrent");
    const tgt = document.getElementById("goalTarget");
    const title = document.getElementById("goalTitle");

    if (!fill || !cur || !tgt || !title) return;

    const percent = goal.target > 0 ? (goal.current / goal.target) * 100 : 0;

    fill.style.width = Math.min(percent, 100) + "%";
    cur.textContent = goal.current;
    tgt.textContent = goal.target;
    title.textContent = goal.title || "Цель не установлена";
}



function initGoalModal() {
    const modal = document.getElementById("goalModal");
    if (!modal) return;

    const form = document.getElementById("goalForm");

    form.onsubmit = async (e) => {
        e.preventDefault();

        const formData = new FormData(form);

        const res = await fetch("/goal_new", {
            method: "POST",
            body: formData
        });

        const data = await res.json();

        if (data.status === "ok") {
            closeGoalModal();
            showToast("Цель обновлена 🎯");

            // 🔥 сразу подтягиваем актуальную цель с сервера
            loadGoalFromServer();
        } else {
            showToast(data.message || "Ошибка сохранения цели");
        }
    };
}



function openGoalModal() {
    document.getElementById("goalModal").classList.add("show");
}

function closeGoalModal() {
    document.getElementById("goalModal").classList.remove("show");
}
async function loadGoalFromServer() {
    try {
        const res = await fetch("/goal_data");
        const data = await res.json();

        // data: { title, current, target }
        updateGoalUI(data);
    } catch (e) {
        console.error("Ошибка загрузки цели:", e);
    }
}


/* ============================================================
   📱 QR-код — стабильный
============================================================ */
let savedQR = localStorage.getItem("qr_code");

function loadQR() {
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

function refreshQR() {
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


/* ============================================================
   🧹 10. Очистка логов
============================================================ */
function initLogButtons() {
    const clearLogsBtn = document.getElementById("clearLogsBtn");
    if (!clearLogsBtn) return;

    clearLogsBtn.onclick = () => {
        lastLogCount = 0;
        document.getElementById("logbox").innerHTML = "";

        fetch("/clear_logs", { method: "POST" })
            .then(() => showToast("Логи очищены ✅"))
            .catch(() => showToast("❌ Ошибка при очистке логов"));
    };
}
/* ============================================================
   📜 RULES — SPA через WebSocket
============================================================ */

function sendRuleCommand(payload) {
    socket.send(JSON.stringify(payload));
}

/* Удаление правила */
function deleteRule(id) {
    sendRuleCommand({
        type: "delete_rule",
        profile_key: CURRENT_PROFILE,
        id
    });

    showToast("Правило удалено");

    reloadInnerContent(() => {
        if (document.querySelector(".rules-page")) {
            initRulesPage();
            initRuleForms();
            initRuleModals();
        }
    });


}

/* Удаление сегмента */
function deleteSegment(ruleId, segIndex) {
    sendRuleCommand({
        type: "delete_segment",
        profile_key: CURRENT_PROFILE,
        rule_id: ruleId,
        seg_index: segIndex
    });

    showToast("Сегмент удалён");

    reloadInnerContent(() => {
        if (document.querySelector(".rules-page")) {
            initRulesPage();
            initRuleForms();
            initRuleModals();
        }
    });


}

/* ============================================================
   🎛 11. Логика страницы правил (SPA)
============================================================ */
function initRulesPage() {

    // Если на странице нет блока правил — выходим
    if (!document.querySelector(".rules-page")) {
        return;
    }

    // Анимация шансов сегментов
    document.querySelectorAll(".segment-chance-fill").forEach(el => {
        if (el.dataset.chance) {
            el.style.width = el.dataset.chance + "%";
        }
    });

    // Тест вибрации — БЕЗ таймера!
    const testVibrationBtn = document.getElementById("testVibrationBtn");
    if (testVibrationBtn) {
        testVibrationBtn.onclick = () => {
            fetch("/test_vibration", { method: "POST" })
                .then(r => r.json())
                .then(data => showToast(data.message || "Вибрация отправлена"))
                .catch(() => showToast("Ошибка при проверке"));
        };
    }

    // Тест правила — тоже БЕЗ таймера!
    document.querySelectorAll(".testRuleBtn").forEach(btn => {
        btn.onclick = () => {
            const index = btn.dataset.index;

            fetch(`/test_rule/${index}`, { method: "POST" })
                .then(r => r.json())
                .then(data => {
                    showToast(data.message || `Правило ${index} проверено`);

                    if (data.wheel_result && socket.readyState === WebSocket.OPEN) {
                        socket.send(JSON.stringify({
                            type: "wheel_result",
                            profile: data.wheel_result.profile,
                            segment: data.wheel_result.segment
                        }));
                    }
                })
                .catch(() => showToast("Ошибка при проверке"));
        };
    });

    // Модалки — только назначение функций, без повторных обработчиков
    window.openRuleModal = (id) => {
        const modal = document.getElementById("ruleModal");
        modal.classList.add("show");

        const card = document.querySelector(`[data-rule-id="${id}"]`);

        // сохраняем оригинальные данные
        window._originalRuleData = {
            min: card.dataset.min,
            max: card.dataset.max,
            strength: card.dataset.strength,
            duration: card.dataset.duration,
            action: card.dataset.action || "",
            type: card.dataset.type
        };
        document.getElementById("edit_rule_id").value = id;
        document.getElementById("edit_min").value = card.dataset.min;
        document.getElementById("edit_max").value = card.dataset.max;
        document.getElementById("edit_strength").value = card.dataset.strength;
        document.getElementById("edit_duration").value = card.dataset.duration;

        const type = card.dataset.type;
        document.getElementById("edit_type").value = type;

        document.getElementById("edit_type_display").textContent =
            type === "vibration" ? "Вибрация" :
            type === "custom" ? "Действие" :
            "Колесо фортуны";

        // действие только для custom
        document.getElementById("edit_action").value =
            type === "custom" ? (card.dataset.action || "") : "";

        updateRuleEditFields();
    };




    window.closeRuleModal = () => {
        const modal = document.getElementById("ruleModal");
        modal.classList.remove("show");

        if (window._originalRuleData) {
            document.getElementById("edit_min").value = window._originalRuleData.min;
            document.getElementById("edit_max").value = window._originalRuleData.max;
            document.getElementById("edit_strength").value = window._originalRuleData.strength;
            document.getElementById("edit_duration").value = window._originalRuleData.duration;
            document.getElementById("edit_action").value = window._originalRuleData.action;
            document.getElementById("edit_type").value = window._originalRuleData.type;

            updateRuleEditFields();
        }
    };



    window.openSegmentModal = (ruleId) => {
        const modal = document.getElementById("segmentModal");
        modal.classList.add("show");
        document.getElementById("segment_rule_id").value = ruleId;
    };

    window.closeSegmentModal = () => {
        document.getElementById("segmentModal").classList.remove("show");
    };

    // Обновление полей
    window.updateRuleEditFields = () => {
        const type = document.getElementById("edit_type").value;

        const strength = document.getElementById("edit_strength_block");
        const duration = document.getElementById("edit_duration_block");
        const action = document.getElementById("edit_action_block");
        const typeBlock = document.getElementById("edit_type_display").parentElement;

        // Скрываем всё
        strength.classList.add("hidden");
        duration.classList.add("hidden");
        action.classList.add("hidden");
        typeBlock.classList.add("hidden");

        // ВИБРАЦИЯ → только сила + время
        if (type === "vibration") {
            strength.classList.remove("hidden");
            duration.classList.remove("hidden");
        }

        // ДЕЙСТВИЕ → только действие
        if (type === "custom") {
            action.classList.remove("hidden");
        }

        // КОЛЕСО → ничего кроме мин/макс
        // (мин/макс всегда видны)
    };




    window.updateNewRuleFields = () => {
        const type = document.getElementById("new_action_type").value;

        const cellMin = document.getElementById("cell_min");
        const cellMax = document.getElementById("cell_max");
        const cellStrength = document.getElementById("cell_strength");
        const cellDuration = document.getElementById("cell_duration");
        const cellAction = document.getElementById("cell_action");

        // Скрываем всё
        cellMin.style.display = "none";
        cellMax.style.display = "none";
        cellStrength.style.display = "none";
        cellDuration.style.display = "none";
        cellAction.style.display = "none";

        // Если тип пустой — ничего не показываем
        if (!type) return;

        // Показываем нужное
        if (type === "vibration") {
            cellMin.style.display = "flex";
            cellMax.style.display = "flex";
            cellStrength.style.display = "flex";
            cellDuration.style.display = "flex";
        }

        if (type === "custom") {
            cellMin.style.display = "flex";
            cellMax.style.display = "flex";
            cellAction.style.display = "flex";
        }

        if (type === "wheel") {
            cellMin.style.display = "flex";
            cellMax.style.display = "flex";
        }
    };

    setTimeout(updateNewRuleFields, 0);

    const typeSelect = document.getElementById("typeSelect");
    const typeDisplay = document.getElementById("typeDisplay");
    const typeOptions = document.getElementById("typeOptions");

    if (typeSelect && typeDisplay && typeOptions) {

        typeDisplay.addEventListener("click", () => {
            typeOptions.style.display =
                typeOptions.style.display === "flex" ? "none" : "flex";
        });

        document.querySelectorAll(".option").forEach(opt => {
            opt.addEventListener("click", () => {
                const value = opt.getAttribute("data-value");
                typeDisplay.textContent = opt.textContent;
                typeOptions.style.display = "none";

                document.getElementById("new_action_type").value = value;
                updateNewRuleFields();
            });
        });

        document.addEventListener("click", (e) => {
            if (!typeSelect.contains(e.target)) {
                typeOptions.style.display = "none";
            }
        });
    }

    // Инициализация форм — безопасная
    initRuleForms();
}

/* ============================================================
   🎛 12. Формы правил (WebSocket)
============================================================ */
function initRuleForms() {
    // Если мы не на странице правил — выходим
    if (!document.querySelector(".rules-page")) {
        return;
    }

    // Удаляем старые обработчики
    const addForm = document.getElementById("addRuleForm");
    const editForm = document.getElementById("ruleEditForm");
    const segForm = document.getElementById("segmentAddForm");

    if (addForm) addForm.replaceWith(addForm.cloneNode(true));
    if (editForm) editForm.replaceWith(editForm.cloneNode(true));
    if (segForm) segForm.replaceWith(segForm.cloneNode(true));

    // Ищем формы снова
    const addFormNew = document.getElementById("addRuleForm");
    const editFormNew = document.getElementById("ruleEditForm");
    const segFormNew = document.getElementById("segmentAddForm");

    /* ============================================================
       ➕ Добавление правила
    ============================================================ */
    if (addFormNew) {
        addFormNew.addEventListener("submit", (e) => {
            e.preventDefault();

            const payload = {
                type: "add_rule",
                profile_key: CURRENT_PROFILE,
                min: Number(document.getElementById("new_min").value),
                max: Number(document.getElementById("new_max").value),
                strength: Number(document.getElementById("new_strength").value || 0),
                duration: Number(document.getElementById("new_duration").value || 0),
                action_type: document.getElementById("new_action_type").value,
                action: document.getElementById("new_action").value || ""
            };

            sendRuleCommand(payload);
            showToast("Правило добавлено");

            reloadInnerContent(() => {
                if (document.querySelector(".rules-page")) {
                    initRulesPage();
                    initRuleForms();
                    initRuleModals();
                }
            });
        });
    }

    /* ============================================================
       ✏️ Редактирование правила
    ============================================================ */
    if (editFormNew) {
        editFormNew.addEventListener("submit", (e) => {
            e.preventDefault();

            const payload = {
                type: "edit_rule",
                profile_key: CURRENT_PROFILE,
                id: document.getElementById("edit_rule_id").value,
                min: Number(document.getElementById("edit_min").value),
                max: Number(document.getElementById("edit_max").value),
                strength: Number(document.getElementById("edit_strength").value || 0),
                duration: Number(document.getElementById("edit_duration").value || 0),
                action_type: document.getElementById("edit_type").value,
                action: document.getElementById("edit_action").value || ""
            };

            sendRuleCommand(payload);
            showToast("Правило обновлено");

            reloadInnerContent(() => {
                if (document.querySelector(".rules-page")) {
                    initRulesPage();
                    initRuleForms();
                    initRuleModals();
                }
            });
        });
    }

    /* ============================================================
       🎡 Добавление сегмента
    ============================================================ */
    if (segFormNew) {
        segFormNew.addEventListener("submit", (e) => {
            e.preventDefault();

            const payload = {
                type: "add_segment",
                profile_key: CURRENT_PROFILE,
                rule_id: document.getElementById("segment_rule_id").value,
                name: document.getElementById("seg_name").value,
                chance: Number(document.getElementById("seg_chance").value),
                seg_type: document.getElementById("seg_type").value,
                strength: Number(document.getElementById("seg_strength").value || 0),
                duration: Number(document.getElementById("seg_duration").value || 0),
                action: document.getElementById("seg_action").value || ""
            };

            sendRuleCommand(payload);
            showToast("Сегмент добавлен");

            reloadInnerContent(() => {
                if (document.querySelector(".rules-page")) {
                    initRulesPage();
                    initRuleForms();
                    initRuleModals();
                }
            });
        });
    }
}

function initRuleModals() {
    if (!document.querySelector(".rules-page")) {
        return;
    }
    window.openRuleModal = (id) => {
        const modal = document.getElementById("ruleModal");
        modal.classList.add("show");

        const card = document.querySelector(`[data-rule-id="${id}"]`);

        window._originalRuleData = {
            min: card.dataset.min,
            max: card.dataset.max,
            strength: card.dataset.strength,
            duration: card.dataset.duration,
            action: card.dataset.action || "",
            type: card.dataset.type
        };

        document.getElementById("edit_rule_id").value = id;
        document.getElementById("edit_min").value = card.dataset.min;
        document.getElementById("edit_max").value = card.dataset.max;
        document.getElementById("edit_strength").value = card.dataset.strength;
        document.getElementById("edit_duration").value = card.dataset.duration;
        document.getElementById("edit_action").value =
            card.dataset.type === "custom" ? (card.dataset.action || "") : "";
        document.getElementById("edit_type").value = card.dataset.type;

        updateRuleEditFields();
    };

    window.closeRuleModal = () => {
        const modal = document.getElementById("ruleModal");
        modal.classList.remove("show");

        if (window._originalRuleData) {
            document.getElementById("edit_min").value = window._originalRuleData.min;
            document.getElementById("edit_max").value = window._originalRuleData.max;
            document.getElementById("edit_strength").value = window._originalRuleData.strength;
            document.getElementById("edit_duration").value = window._originalRuleData.duration;
            document.getElementById("edit_action").value = window._originalRuleData.action;
            document.getElementById("edit_type").value = window._originalRuleData.type;

            updateRuleEditFields();
        }
    };

    window.openSegmentModal = (ruleId) => {
        const modal = document.getElementById("segmentModal");
        modal.classList.add("show");
        document.getElementById("segment_rule_id").value = ruleId;
    };

    window.closeSegmentModal = () => {
        document.getElementById("segmentModal").classList.remove("show");
    };

    window.toggleWheel = (ruleId) => {
        const block = document.getElementById(`wheel-${ruleId}`);
        if (!block) return;

        // если скрыто — раскрыть
        if (block.classList.contains("hidden")) {
            block.classList.remove("hidden");
            block.classList.add("show");
        }
        // если раскрыто — скрыть
        else {
            block.classList.remove("show");
            block.classList.add("hidden");
        }
    };

}
/* ============================================================
   🎡 Переключение полей сегмента
============================================================ */
function updateSegmentFields(selectEl) {
    const modal = selectEl.closest(".modal-content");

    const vib = modal.querySelector(".seg-vibration-fields");
    const act = modal.querySelector(".seg-action-fields");
    const retry = modal.querySelector(".seg-retry-fields");

    // Скрываем всё
    vib.classList.add("hidden");
    act.classList.add("hidden");
    retry.classList.add("hidden");

    // Показываем нужное
    if (selectEl.value === "vibration") vib.classList.remove("hidden");
    if (selectEl.value === "action") act.classList.remove("hidden");
    if (selectEl.value === "retry") retry.classList.remove("hidden");
}

