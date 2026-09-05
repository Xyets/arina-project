// ============================================================
// 📦 Sidebar collapse & mode switch
// ============================================================

import { CURRENT_USER, CURRENT_MODE, CURRENT_PROFILE } from "./core.js";
import { socket } from "./websocket.js";
import { reloadInnerContent } from "./spa.js";
import { loadGoalFromServer, updateGoalVisibility } from "./goal.js";
import { showToast } from "./toast.js";

export function initSidebarCollapse() {
    const sidebar = document.getElementById("sidebar");
    const sidebarLogo = document.getElementById("sidebarLogo");

    if (sidebar && sidebarLogo) {
        sidebarLogo.onclick = () => sidebar.classList.toggle("collapsed");
    }
}

export function initModeSwitch() {
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

                // обновляем глобальные переменные
                CURRENT_MODE = newMode;
                CURRENT_PROFILE = `${CURRENT_USER}_${CURRENT_MODE}`;

                updateGoalVisibility();
                loadGoalFromServer();

                socket.send(JSON.stringify({
                    type: "hello",
                    role: "panel",
                    profile_key: CURRENT_PROFILE
                }));

                reloadInnerContent(() => {
                    updateGoalVisibility();
                });

                showToast(`Режим переключен: ${newMode}`);
            }
        });
    };
}
