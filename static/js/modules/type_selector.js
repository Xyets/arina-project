// type_selector.js — кастомный селект типа действия

export function initTypeSelector(updateNewRuleFields) {
    const typeSelect = document.getElementById("typeSelect");
    const typeDisplay = document.getElementById("typeDisplay");
    const typeOptions = document.getElementById("typeOptions");

    if (!typeSelect || !typeDisplay || !typeOptions) return;

    // Открытие/закрытие списка
    typeDisplay.onclick = () => {
        typeOptions.style.display =
            typeOptions.style.display === "flex" ? "none" : "flex";
    };

    // Выбор опции
    typeOptions.querySelectorAll(".option").forEach(opt => {
        opt.onclick = () => {
            const value = opt.dataset.value;
            typeDisplay.textContent = opt.textContent;
            typeOptions.style.display = "none";

            document.getElementById("new_action_type").value = value;

            if (updateNewRuleFields) {
                updateNewRuleFields();
            }
        };
    });

    // Глобальный обработчик закрытия
    function typeSelectorGlobalHandler(e) {
        if (!typeSelect.contains(e.target)) {
            typeOptions.style.display = "none";
        }
    }

    document.removeEventListener("click", typeSelectorGlobalHandler);
    document.addEventListener("click", typeSelectorGlobalHandler);
}
