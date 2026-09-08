import { socket } from "./websocket.js";
import { CURRENT_USER, CURRENT_MODE, setMode, setProfile } from "./core.js";
import { showToast } from "./toast.js";
import { updateGoalVisibility, loadGoalFromServer } from "./goal.js";
import { reloadInnerContent } from "./spa.js";
import { initRuleForms, initRuleModals } from "./rules.js";

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

        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({
                type: "set_mode",
                user: CURRENT_USER,
                mode: newMode
            }));
        }

        fetch("/set_mode", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mode: newMode })
        })
        .then(r => r.json())
        .then(data => {
            if (data.status === "ok") {
                setMode(newMode);
                updateGoalVisibility();
                const newProfile = `${CURRENT_USER}_${newMode}`;
                setProfile(newProfile);

                loadGoalFromServer();

                if (socket && socket.readyState === WebSocket.OPEN) {
                    socket.send(JSON.stringify({
                        type: "hello",
                        role: "panel",
                        profile_key: newProfile
                    }));
                }

                reloadInnerContent(() => {
                    updateGoalVisibility();
                    if (document.querySelector(".rules-page")) {
                        initRuleForms();
                        initRuleModals();
                    }
                });

                showToast(`Режим переключен: ${newMode}`);
            }
        });
    };
}