import { connectWS } from "./modules/websocket.js";
import { initSidebarCollapse, initModeSwitch } from "./modules/sidebar.js";
import { initSidebarNavigation } from "./modules/spa.js";
import { initLogButtons } from "./modules/logs.js";
import { initQueueButtons } from "./modules/queue.js";
import { initGoalModal, loadGoalFromServer } from "./modules/goal.js";
import { loadQR } from "./modules/qr.js";
import { initTypeSelector } from "./modules/utils.js";

window.addEventListener("load", () => {
    connectWS();
    initSidebarCollapse();
    initModeSwitch();
    initLogButtons();
    initQueueButtons();
    initGoalModal();
    initSidebarNavigation();
    loadQR();
    loadGoalFromServer();
    initTypeSelector();
});
