// ============================================================
// 🎛 Кастомный селект типа
// ============================================================
import { updateNewRuleFields } from "./rules.js";
export function initTypeSelector() {
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

            // вызываем глобальную функцию из rules.js
            updateNewRuleFields();

        };
    });

    function typeSelectorGlobalHandler(e) {
        if (!typeSelect.contains(e.target)) {
            typeOptions.style.display = "none";
        }
    }

    document.removeEventListener("click", typeSelectorGlobalHandler);
    document.addEventListener("click", typeSelectorGlobalHandler);
}
