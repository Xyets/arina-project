export function initModelSelector() {
    console.log("MODEL: initModelSelector()");   
    const select = document.getElementById("modelSelect");
    const options = document.getElementById("modelOptions");

    if (!select || !options) {
        console.warn("MODEL: selector elements NOT FOUND");   // ← ВСТАВИТЬ СЮДА
        return;
    }


    // Открытие списка только при клике на display
    const display = select.querySelector(".select-display");
    if (!display) return;

    display.onclick = (e) => {
        console.log("MODEL: display clicked");   // ← ВСТАВИТЬ СЮДА
        e.stopPropagation();
        options.style.display =
            options.style.display === "flex" ? "none" : "flex";
    };

    // Клик по опциям — НЕ должен вызывать select.onclick
    const items = options.querySelectorAll(".option");
    items.forEach(item => {
        item.onclick = (e) => {
            e.stopPropagation();
            const value = item.dataset.value;
            console.log("MODEL: option selected =", value);   // ← ВСТАВИТЬ СЮДА
            navigateSPA(`/stats_beta?model=${value}`);
        };
    });

    // Закрытие при клике вне
    document.addEventListener("click", () => {
        console.log("MODEL: outside click → closing options");   // ← ВСТАВИТЬ СЮДА
        options.style.display = "none";
    }, { once: true });
}
