// static/js/modules/reactions.js

/* ============================================================
   ИНИЦИАЛИЗАЦИЯ СТРАНИЦЫ РЕАКЦИЙ
============================================================ */
export function initReactionsPage(showToast) {
    initTestButtons(showToast);
    initEditButtons();
    initCloseModal();
}

/* ============================================================
   ТЕСТ РЕАКЦИИ
============================================================ */
function initTestButtons(showToast) {
    document.querySelectorAll(".testReactionBtn").forEach(btn => {
        btn.onclick = () => {
            const ruleId = btn.dataset.ruleId;

            fetch("/test_reaction", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "same-origin",
                body: JSON.stringify({
                    rule_id: ruleId,
                    profile_key: window.CURRENT_PROFILE
                })
            })
            .then(r => r.json())
            .then(data => {
                if (data.status === "ok") {
                    showToast("Тест отправлен в OBS");
                } else {
                    showToast("Ошибка: " + data.message);
                }
            })
            .catch(() => showToast("Ошибка запроса"));
        };
    });
}

/* ============================================================
   ОТКРЫТИЕ МОДАЛКИ РЕДАКТИРОВАНИЯ
============================================================ */
function initEditButtons() {
    document.querySelectorAll(".editReactionBtn").forEach(btn => {
        btn.onclick = () => {
            const ruleId = btn.dataset.ruleId;

            // Находим карточку
            const card = btn.closest(".reaction-card-beta");
            if (!card) return;

            // Достаём данные
            const min = card.querySelector(".rule-range").textContent.match(/(\d+)\s*–\s*(\d+)/);
            const duration = card.querySelector(".rule-info").textContent.match(/(\d+)/);

            const minVal = min ? min[1] : "";
            const maxVal = min ? min[2] : "";
            const durationVal = duration ? duration[1] : "";

            // Заполняем форму
            document.getElementById("edit_reaction_id").value = ruleId;
            document.getElementById("edit_min_points").value = minVal;
            document.getElementById("edit_max_points").value = maxVal;
            document.getElementById("edit_duration").value = durationVal;

            // Открываем модалку
            openReactionEditModal();
        };
    });
}

/* ============================================================
   МОДАЛКА — ОТКРЫТЬ / ЗАКРЫТЬ
============================================================ */
function openReactionEditModal() {
    const modal = document.getElementById("reactionEditModal");
    if (modal) modal.classList.add("show");
}

function closeReactionEditModal() {
    const modal = document.getElementById("reactionEditModal");
    if (modal) modal.classList.remove("show");
}

function initCloseModal() {
    const modal = document.getElementById("reactionEditModal");
    if (!modal) return;

    modal.addEventListener("click", e => {
        if (e.target === modal) {
            closeReactionEditModal();
        }
    });
}
