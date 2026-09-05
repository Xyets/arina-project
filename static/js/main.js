/* ============================================================
   🌐 MAIN — модульная сборка FlowTip
============================================================ */

/* ---------- CORE ---------- */
import { CURRENT_MODE } from "./modules/core.js";

/* ---------- WEBSOCKET ---------- */
import { connectWS, handleWSMessage } from "./modules/websocket.js";

/* ---------- SPA ---------- */
import { initSidebarNavigation, navigateSPA } from "./modules/spa.js";

/* ---------- SIDEBAR ---------- */
import { initSidebarCollapse, initModeSwitch } from "./modules/sidebar.js";

/* ---------- LOGS ---------- */
import { loadLogs } from "./modules/logs.js";

/* ---------- QUEUE ---------- */
import { updateQueueUI, initQueueButtons, startVibrationTimer } from "./modules/queue.js";

/* ---------- POPUP ---------- */
import { showEntryPopup } from "./modules/popup.js";

/* ---------- TOAST ---------- */
import { showToast } from "./modules/toast.js";

/* ---------- GOAL ---------- */
import { updateGoalVisibility, initGoalModal, loadGoalFromServer } from "./modules/goal.js";

/* ---------- QR ---------- */
import { loadQR, refreshQR } from "./modules/qr.js";

/* ---------- RULES ---------- */
import {
    initRulesPage,
    initRuleForms,
    initRuleModals,
    sendRuleCommand,
    deleteRule,
    deleteSegment,
    updateSegmentFields
} from "./modules/rules.js";

/* ---------- UTILS ---------- */
import { initTypeSelector } from "./modules/utils.js";

/* ---------- VIP ---------- */
import { initVipPage, vipWebSocketUpdate } from "./modules/vip.js";


/* ============================================================
   🌟 ГЛОБАЛЬНЫЕ ОБРАБОТЧИКИ WS
============================================================ */
window.handleWSMessage = (data) => {
    handleWSMessage(data);

    // VIP обновления
    vipWebSocketUpdate(data);

    // Вход пользователя → popup
    if (data.entry) {
        showEntryPopup(`
            👤 <strong>${data.entry.name}</strong><br>
            🔢 Визитов: ${data.entry.visits}<br>
            💗 Чаевых всего: ${data.entry.total_tips}<br>
            📝 Заметки: ${data.entry.notes || "нет"}
        `);
    }

    // Вибрация
    if (data.vibration) {
        startVibrationTimer(data.vibration.duration, data.vibration.strength);
    }
};


/* ============================================================
   🌟 ИНИЦИАЛИЗАЦИЯ ПРИ ЗАГРУЗКЕ
============================================================ */
window.addEventListener("load", () => {

    /* WebSocket */
    connectWS();

    /* Sidebar */
    initSidebarCollapse();
    initModeSwitch();
    initSidebarNavigation();

    /* Goal */
    initGoalModal();
    loadGoalFromServer();
    updateGoalVisibility();

    /* Logs */
    loadLogs();

    /* Queue */
    initQueueButtons();
    updateQueueUI();

    /* QR */
    loadQR();

    /* Rules */
    initRuleForms();
    initRuleModals();

    /* Utils */
    initTypeSelector();

    /* VIP */
    initVipPage();
});


/* ============================================================
   🌟 SPA ПЕРЕХОДЫ
============================================================ */
window.navigateSPA = (url) => {
    navigateSPA(url);

    setTimeout(() => {
        // Rules
        if (document.querySelector(".rules-page")) {
            initRulesPage();
            initRuleForms();
            initRuleModals();
        }

        // VIP
        if (document.querySelector(".vip-grid")) {
            initVipPage();
        }

        // Goal
        loadGoalFromServer();
        updateGoalVisibility();

        // Logs
        loadLogs();

        // Queue
        updateQueueUI();

        // QR
        loadQR();

        // Utils
        initTypeSelector();
    }, 50);
};
