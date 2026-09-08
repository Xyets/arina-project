import { Core } from "./core.js";
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
            user: Core.CURRENT_USER,
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

                Core.CURRENT_MODE = newMode;   // ✔ теперь можно менять
                Core.CURRENT_PROFILE = `${Core.CURRENT_USER}_${Core.CURRENT_MODE}`;

                updateGoalVisibility();
                loadGoalFromServer();

                socket.send(JSON.stringify({
                    type: "hello",
                    role: "panel",
                    profile_key: Core.CURRENT_PROFILE
                }));

                reloadInnerContent(() => {
                    updateGoalVisibility();
                });

                showToast(`Режим переключен: ${newMode}`);
            }
        });
    };
}
