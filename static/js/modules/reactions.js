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
    initCopyObsLink(showToast);
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

                }
            });
        };
    });
}


/* ============================================================
   🔗 КОПИРОВАНИЕ OBS-ССЫЛКИ
============================================================ */
function initCopyObsLink(showToast) {
    const btn = document.getElementById("copyObsLink");
    if (!btn) return;

    btn.onclick = () => {
        const code = document.querySelector(".obs-code").textContent.trim();
        navigator.clipboard.writeText(code);
        showToast("Ссылка скопирована");
    };
}

/* ============================================================
   ➕ ДОБАВЛЕНИЕ РЕАКЦИИ
============================================================ */
function initAddReaction(showToast) {
    const btn = document.getElementById("reactionAddBtn");
    if (!btn) return;

    btn.onclick = async () => {
        const formData = new FormData();
        formData.append("add_reaction_rule", "1");
        formData.append("min_points", document.getElementById("reactionAddMin").value);
        formData.append("max_points", document.getElementById("reactionAddMax").value);
        formData.append("duration", document.getElementById("reactionAddDuration").value);

        const file = document.getElementById("reactionAddImage").files[0];
        if (file) formData.append("image", file);

        const res = await fetch("/reactions_beta", { method: "POST", body: formData });

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
            const card = btn.closest(".reaction-card");
            const id = btn.dataset.ruleId;

            const minMax = card.querySelector(".reaction-range").textContent.match(/\d+/g);
            const duration = card.querySelector(".reaction-duration").textContent.match(/\d+/)[0];

            document.getElementById("reactionEditId").value = id;
            document.getElementById("reactionEditMin").value = minMax[0];
            document.getElementById("reactionEditMax").value = minMax[1];
            document.getElementById("reactionEditDuration").value = duration;

            openReactionEditModal();
        };
    });
}

/* ============================================================
   💾 СОХРАНЕНИЕ РЕАКЦИИ
============================================================ */
function initEditModalSave(showToast) {
    const btn = document.getElementById("reactionEditSaveBtn");
    if (!btn) return;

    btn.onclick = async () => {
        const formData = new FormData();
        formData.append("edit_reaction_rule", document.getElementById("reactionEditId").value);
        formData.append("min_points", document.getElementById("reactionEditMin").value);
        formData.append("max_points", document.getElementById("reactionEditMax").value);
        formData.append("duration", document.getElementById("reactionEditDuration").value);

        const file = document.getElementById("reactionEditImage").files[0];
        if (file) formData.append("image", file);

        const res = await fetch("/reactions_beta", { method: "POST", body: formData });

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
            const formData = new FormData();
            formData.append("delete_reaction_rule", btn.dataset.ruleId);

            const res = await fetch("/reactions_beta", { method: "POST", body: formData });

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
    modal.classList.add("show");
}

function closeReactionEditModal() {
    const modal = document.getElementById("reactionEditModal");
    modal.classList.remove("show");
}

function initCloseModal() {
    const modal = document.getElementById("reactionEditModal");
    modal.addEventListener("click", e => {
        if (e.target === modal) closeReactionEditModal();
    });
}
const fileInput = document.getElementById("reactionAddImage");
const fileName = document.getElementById("reactionAddFileName");

if (fileInput) {
    fileInput.onchange = () => {
        fileName.textContent = fileInput.files[0]
            ? fileInput.files[0].name
            : "Файл не выбран";
    };
}
