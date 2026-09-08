// ============================================================
// 🌐 CORE — глобальные переменные FlowTip
// ============================================================

// Глобальный объект, который МОЖНО менять
window.FlowTipCore = {
    CURRENT_PAGE_URL: "/beta",
    CURRENT_USER: "",
    CURRENT_MODE: "public",
    CURRENT_PROFILE: "",
    goal: {
        title: "",
        current: 0,
        target: 0
    }
};

// Инициализация из DOM
const app = document.getElementById("app");
if (app) {
    FlowTipCore.CURRENT_USER = app.dataset.user || "";
    FlowTipCore.CURRENT_MODE = app.dataset.mode || "public";
    FlowTipCore.CURRENT_PROFILE = app.dataset.profile || "";
}

export const Core = FlowTipCore;
