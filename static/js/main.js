import { socket, connectWS } from "./modules/websocket.js";
import { initSidebarCollapse, initModeSwitch } from "./modules/sidebar.js";
import { initLogButtons } from "./modules/logs.js";
import { initQueueButtons } from "./modules/queue.js";
import { initGoalModal, loadGoalFromServer } from "./modules/goal.js";
import { initSidebarNavigation } from "./modules/spa.js";
import { loadQR } from "./modules/qr.js";
import { initTypeSelector } from "./modules/utils.js";
import { initVipPage } from "./modules/vip.js";

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
    loadGoalFromServer();
    initTypeSelector();
    initVipPage();
});