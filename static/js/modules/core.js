// core.js — базовые функции интерфейса FlowTip

/* ============================================================
   🔔 Popup
============================================================ */
export function showEntryPopup(message) {
    const popup = document.getElementById("entryPopup");
    popup.innerHTML = `<div>${message}</div><button onclick="hideEntryPopup()">ОК</button>`;
    popup.classList.add("show");

    let hideTimer = setTimeout(hideEntryPopup, 8000);

    popup.onmouseenter = () => clearTimeout(hideTimer);
    popup.onmouseleave = () => hideTimer = setTimeout(hideEntryPopup, 8000);
}

export function hideEntryPopup() {
    const popup = document.getElementById("entryPopup");
    popup.classList.remove("show");
}

/* ============================================================
   🔔 Toast
============================================================ */
export function showToast(msg) {
    const toast = document.getElementById("toast");
    toast.textContent = msg;
    toast.classList.add("show");
    setTimeout(() => toast.classList.remove("show"), 3000);
}

/* ============================================================
   🎯 Goal visibility
============================================================ */
export function updateGoalVisibility(CURRENT_MODE) {
    const circle = document.getElementById("goalCircle");
    if (!circle) return;

    circle.style.display = CURRENT_MODE === "public" ? "flex" : "none";
}

/* ============================================================
   🎯 Apple Ring
============================================================ */
export let goal = { title: "", current: 0, target: 0 };

export function updateGoalCircle(newGoal = null, CURRENT_MODE) {
    if (newGoal) goal = newGoal;
    if (CURRENT_MODE !== "public") return;

    const ring = document.querySelector(".goal-progress-ring");
    const cur = document.getElementById("goalCurrent");
    const tgt = document.getElementById("goalTarget");
    const title = document.getElementById("goalCircleTitle");

    if (!ring || !cur || !tgt || !title) return;

    const percent = goal.target > 0 ? (goal.current / goal.target) : 0;
    const circumference = 264;
    const offset = circumference - (circumference * percent);

    ring.style.strokeDashoffset = offset;
    cur.textContent = goal.current;
    tgt.textContent = goal.target;
    title.textContent = goal.title || "Цель";
}

/* ============================================================
   🎯 Goal Modal
============================================================ */
export function initGoalModal(loadGoalFromServer, showToast) {
    const modal = document.getElementById("goalModal");
    if (!modal) return;

    const form = document.getElementById("goalForm");

    form.onsubmit = async (e) => {
        e.preventDefault();

        const formData = new FormData(form);
        const res = await fetch("/goal_new", { method: "POST", body: formData });
        const data = await res.json();

        if (data.status === "ok") {
            closeGoalModal();
            showToast("Цель обновлена 🎯");
            loadGoalFromServer();
        } else {
            showToast(data.message || "Ошибка сохранения цели");
        }
    };
}

export function openGoalModal() {
    document.getElementById("goalModal").classList.add("show");
}

export function closeGoalModal() {
    document.getElementById("goalModal").classList.remove("show");
}

export async function loadGoalFromServer(CURRENT_MODE) {
    if (CURRENT_MODE !== "public") return;

    try {
        const res = await fetch("/goal_data");
        const data = await res.json();
        updateGoalCircle(data, CURRENT_MODE);
    } catch (e) {
        console.error("Ошибка загрузки цели:", e);
    }
}

/* ============================================================
   📱 QR-код
============================================================ */
export let savedQR = localStorage.getItem("qr_code");

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

export function refreshQR(showToast) {
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
   🧹 Логи
============================================================ */
export let lastLogCount = 0;

export async function loadLogs() {
    const box = document.getElementById("logbox");
    if (!box) return;

    const res = await fetch("/logs_data");
    const data = await res.json();

    const logs = data.logs || [];
    const newLogs = logs.slice(lastLogCount);
    lastLogCount = logs.length;

    newLogs.forEach(log => {
        const div = document.createElement("div");
        div.className = `event-item ${classifyLog(log)}`;
        div.textContent = log;

        box.appendChild(div);
        box.scrollTop = box.scrollHeight;
    });
}

export function classifyLog(log) {
    log = log.toLowerCase();

    if (log.includes("вибрация")) return "vibration";
    if (log.includes("колесо")) return "wheel";
    if (log.includes("действие")) return "action";
    if (log.includes("вошёл") || log.includes("вошел")) return "entry";
    if (log.includes("вышел")) return "exit";
    return "system";
}

export function initLogButtons(showToast) {
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
   🎛 Type Selector
============================================================ */
export function initTypeSelector(updateNewRuleFields) {
    const typeSelect = document.getElementById("typeSelect");
    const typeDisplay = document.getElementById("typeDisplay");
    const typeOptions = document.getElementById("typeOptions");

    if (!typeSelect || !typeDisplay || !typeOptions) return;

    typeDisplay.onclick = () => {
        typeOptions.style.display =
            typeOptions.style.display === "flex" ? "none" : "flex";
    };

    typeOptions.querySelectorAll(".option").forEach(opt => {
        opt.onclick = () => {
            const value = opt.dataset.value;
            typeDisplay.textContent = opt.textContent;
            typeOptions.style.display = "none";

            document.getElementById("new_action_type").value = value;
            updateNewRuleFields();
        };
    });

    document.addEventListener("click", (e) => {
        if (!typeSelect.contains(e.target)) {
            typeOptions.style.display = "none";
        }
    });
}

/* ============================================================
   🔍 ENTER Search
============================================================ */
export function initSearchEnter(doSearch) {
    const searchInput = document.querySelector('input[name="q"]');
    if (!searchInput) return;

    searchInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            doSearch();
        }
    });
}
