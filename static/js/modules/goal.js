import { CURRENT_MODE, goal } from "./core.js";
import { showToast } from "./toast.js";

export function updateGoalVisibility() {
    const circle = document.getElementById("goalCircle");
    if (!circle) return;

    circle.style.display = CURRENT_MODE === "public" ? "flex" : "none";
}

export function updateGoalCircle(newGoal = null) {
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

export function initGoalModal() {
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
            showToast("Цель обновлена");
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

export async function loadGoalFromServer() {
    if (CURRENT_MODE !== "public") return;

    try {
        const res = await fetch("/goal_data");
        const data = await res.json();
        updateGoalCircle(data);
    } catch (e) {
        console.error("Ошибка загрузки цели:", e);
    }
}
