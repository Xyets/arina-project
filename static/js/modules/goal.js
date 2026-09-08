// goal.js — модуль круглой цели Apple Ring

let goal = {
    title: "",
    current: 0,
    target: 0
};

// Показывать/скрывать цель в зависимости от режима
export function updateGoalVisibility(CURRENT_MODE) {
    const circle = document.getElementById("goalCircle");
    if (!circle) return;

    circle.style.display = CURRENT_MODE === "public" ? "flex" : "none";
}

// Обновление круглой цели
export function updateGoalCircle(newGoal = null, CURRENT_MODE) {
    if (newGoal) goal = newGoal;
    if (CURRENT_MODE !== "public") return;

    const ring = document.querySelector(".goal-progress-ring");
    const cur = document.getElementById("goalCurrent");
    const tgt = document.getElementById("goalTarget");
    const title = document.getElementById("goalCircleTitle");

    if (!ring || !cur || !tgt || !title) return;

    const percent = goal.target > 0 ? (goal.current / goal.target) : 0;
    const circumference = 264; // r = 42
    const offset = circumference - (circumference * percent);

    ring.style.strokeDashoffset = offset;
    cur.textContent = goal.current;
    tgt.textContent = goal.target;
    title.textContent = goal.title || "Цель";
}

// Модалка цели
export function initGoalModal(showToast, loadGoalFromServer) {
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

// Загрузка цели с сервера
export async function loadGoalFromServer(updateGoalCircle, CURRENT_MODE) {
    if (CURRENT_MODE !== "public") return;

    try {
        const res = await fetch("/goal_data");
        const data = await res.json();

        updateGoalCircle(data, CURRENT_MODE);
    } catch (e) {
        console.error("Ошибка загрузки цели:", e);
    }
}
