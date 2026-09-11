// static/js/modules/reactions.js

/* ============================================================
   ИНИЦИАЛИЗАЦИЯ СТРАНИЦЫ РЕАКЦИЙ (SPA)
============================================================ */
export function initReactionsPage(showToast) {
    initTestButtons(showToast);
    initAddReaction(showToast);
    initEditButtons();
    initDeleteButtons(showToast);
    initEditModalSave(showToast);
    initCloseModal();
}

/* ============================================================
   🔔 ТЕСТ РЕАКЦИИ
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
   ➕ ДОБАВЛЕНИЕ РЕАКЦИИ
============================================================ */
function initAddReaction(showToast) {
    const btn = document.getElementById("reactionAddBtn");
    if (!btn) return;

    btn.onclick = async () => {
        const min = document.getElementById("reactionAddMin").value;
        const max = document.getElementById("reactionAddMax").value;
        const duration = document.getElementById("reactionAddDuration").value;
        const file = document.getElementById("reactionAddImage").files[0];

        const formData = new FormData();
        formData.append("add_reaction_rule", "1");
        formData.append("min_points", min);
        formData.append("max_points", max);
        formData.append("duration", duration);
        if (file) formData.append("image", file);

        const res = await fetch("/reactions_beta", {
            method: "POST",
            body: formData
        });

        if (res.ok) {
            showToast("Реакция добавлена");
            reloadInnerContent();
        } else {
            showToast("Ошибка добавления");
        }
    };
}

/* ============================================================
   ✏️ ОТКРЫТИЕ МОДАЛКИ РЕДАКТИРОВАНИЯ
============================================================ */
function initEditButtons() {
    document.querySelectorAll(".editReactionBtn").forEach(btn => {
        btn.onclick = () => {
            const ruleId = btn.dataset.ruleId;
            const card = btn.closest(".reaction-card-beta");
            if (!card) return;

            const min = card.querySelector(".rule-range").textContent.match(/(\d+)\s*–\s*(\d+)/);
            const duration = card.querySelector(".rule-info").textContent.match(/(\d+)/);

            document.getElementById("reactionEditId").value = ruleId;
            document.getElementById("reactionEditMin").value = min ? min[1] : "";
            document.getElementById("reactionEditMax").value = min ? min[2] : "";
            document.getElementById("reactionEditDuration").value = duration ? duration[1] : "";

            openReactionEditModal();
        };
    });
}

/* ============================================================
   💾 СОХРАНЕНИЕ РЕАКЦИИ (EDIT)
============================================================ */
function initEditModalSave(showToast) {
    const btn = document.getElementById("reactionEditSaveBtn");
    if (!btn) return;

    btn.onclick = async () => {
        const id = document.getElementById("reactionEditId").value;
        const min = document.getElementById("reactionEditMin").value;
        const max = document.getElementById("reactionEditMax").value;
        const duration = document.getElementById("reactionEditDuration").value;
        const file = document.getElementById("reactionEditImage").files[0];

        const formData = new FormData();
        formData.append("edit_reaction_rule", id);
        formData.append("min_points", min);
        formData.append("max_points", max);
        formData.append("duration", duration);
        if (file) formData.append("image", file);

        const res = await fetch("/reactions_beta", {
            method: "POST",
            body: formData
        });

        if (res.ok) {
            showToast("Сохранено");
            closeReactionEditModal();
            reloadInnerContent();
        } else {
            showToast("Ошибка сохранения");
        }
    };
}

/* ============================================================
   ❌ УДАЛЕНИЕ РЕАКЦИИ
============================================================ */
function initDeleteButtons(showToast) {
    document.querySelectorAll(".deleteReactionBtn").forEach(btn => {
        btn.onclick = async () => {
            const id = btn.dataset.ruleId;

            const formData = new FormData();
            formData.append("delete_reaction_rule", id);

            const res = await fetch("/reactions_beta", {
                method: "POST",
                body: formData
            });

            if (res.ok) {
                showToast("Удалено");
                reloadInnerContent();
            } else {
                showToast("Ошибка удаления");
            }
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
