import { CURRENT_PROFILE } from "./core.js";
import { socket } from "./websocket.js";
import { reloadInnerContent } from "./spa.js";
import { showToast } from "./toast.js";
import { updateGoalVisibility } from "./goal.js";

/* ============================================================
   🧹 Очистка логов
============================================================ */
export function initLogButtons() {
    const clearLogsBtn = document.getElementById("clearLogsBtn");
    if (!clearLogsBtn) return;

    clearLogsBtn.onclick = () => {
        window.lastLogCount = 0;
        document.getElementById("logbox").innerHTML = "";

        fetch("/clear_logs", { method: "POST" })
            .then(() => showToast("Логи очищены ✅"))
            .catch(() => showToast("❌ Ошибка при очистке логов"));
    };
}

/* ============================================================
   📜 RULES — команды через WebSocket
============================================================ */
export function sendRuleCommand(payload) {
    socket.send(JSON.stringify(payload));
}

export function deleteRule(id) {
    sendRuleCommand({
        type: "delete_rule",
        profile_key: CURRENT_PROFILE,
        id
    });

    showToast("Правило удалено");

    reloadInnerContent(() => {
        updateGoalVisibility();
        if (document.querySelector(".rules-page")) {
            initRuleForms();
            initRuleModals();
        }
    });
}

export function deleteSegment(ruleId, segIndex) {
    sendRuleCommand({
        type: "delete_segment",
        profile_key: CURRENT_PROFILE,
        rule_id: ruleId,
        seg_index: segIndex
    });

    showToast("Сегмент удалён");

    reloadInnerContent(() => {
        updateGoalVisibility();
        if (document.querySelector(".rules-page")) {
            initRuleForms();
            initRuleModals();
        }
    });
}

/* ============================================================
   🎛 Логика страницы правил
============================================================ */
export function initRulesPage() {

    if (!document.querySelector(".rules-page")) return;

    // Анимация шансов сегментов
    document.querySelectorAll(".segment-chance-fill").forEach(el => {
        if (el.dataset.chance) {
            el.style.width = el.dataset.chance + "%";
        }
    });

    // Тест вибрации
    const testVibrationBtn = document.getElementById("testVibrationBtn");
    if (testVibrationBtn) {
        testVibrationBtn.onclick = () => {
            fetch("/test_vibration", { method: "POST" })
                .then(r => r.json())
                .then(data => showToast(data.message || "Вибрация отправлена"))
                .catch(() => showToast("Ошибка при проверке"));
        };
    }

    // Тест правила
    document.querySelectorAll(".testRuleBtn").forEach(btn => {
        btn.onclick = () => {
            const index = btn.dataset.index;

            fetch(`/test_rule/${index}`, { method: "POST" })
                .then(r => r.json())
                .then(data => {
                    showToast(data.message || `Правило ${index} проверено`);

                    if (data.wheel_result && socket.readyState === WebSocket.OPEN) {
                        socket.send(JSON.stringify({
                            type: "wheel_result",
                            profile: data.wheel_result.profile,
                            segment: data.wheel_result.segment
                        }));
                    }
                })
                .catch(() => showToast("Ошибка при проверке"));
        };
    });

    /* ---------------- Модалки ---------------- */

    window.openRuleModal = (id) => {
        const modal = document.getElementById("ruleModal");
        modal.classList.add("show");

        const card = document.querySelector(`[data-rule-id="${id}"]`);

        window._originalRuleData = {
            min: card.dataset.min,
            max: card.dataset.max,
            strength: card.dataset.strength,
            duration: card.dataset.duration,
            action: card.dataset.action || "",
            type: card.dataset.type
        };

        document.getElementById("edit_rule_id").value = id;
        document.getElementById("edit_min").value = card.dataset.min;
        document.getElementById("edit_max").value = card.dataset.max;
        document.getElementById("edit_strength").value = card.dataset.strength;
        document.getElementById("edit_duration").value = card.dataset.duration;
        document.getElementById("edit_action").value =
            card.dataset.type === "custom" ? (card.dataset.action || "") : "";
        document.getElementById("edit_type").value = card.dataset.type;

        updateRuleEditFields();
    };

    window.closeRuleModal = () => {
        const modal = document.getElementById("ruleModal");
        modal.classList.remove("show");

        if (window._originalRuleData) {
            document.getElementById("edit_min").value = window._originalRuleData.min;
            document.getElementById("edit_max").value = window._originalRuleData.max;
            document.getElementById("edit_strength").value = window._originalRuleData.strength;
            document.getElementById("edit_duration").value = window._originalRuleData.duration;
            document.getElementById("edit_action").value = window._originalRuleData.action;
            document.getElementById("edit_type").value = window._originalRuleData.type;

            updateRuleEditFields();
        }
    };

    window.openSegmentModal = (ruleId) => {
        const modal = document.getElementById("segmentModal");
        modal.classList.add("show");
        document.getElementById("segment_rule_id").value = ruleId;
    };

    window.closeSegmentModal = () => {
        document.getElementById("segmentModal").classList.remove("show");
    };

    /* ---------------- Обновление полей ---------------- */

    window.updateRuleEditFields = () => {
        const type = document.getElementById("edit_type").value;

        const strength = document.getElementById("edit_strength_block");
        const duration = document.getElementById("edit_duration_block");
        const action = document.getElementById("edit_action_block");
        const typeBlock = document.getElementById("edit_type_display").parentElement;

        strength.classList.add("hidden");
        duration.classList.add("hidden");
        action.classList.add("hidden");
        typeBlock.classList.add("hidden");

        if (type === "vibration") {
            strength.classList.remove("hidden");
            duration.classList.remove("hidden");
        }

        if (type === "custom") {
            action.classList.remove("hidden");
        }
    };

    window.updateNewRuleFields = () => {
        const type = document.getElementById("new_action_type").value;

        const cellMin = document.getElementById("cell_min");
        const cellMax = document.getElementById("cell_max");
        const cellStrength = document.getElementById("cell_strength");
        const cellDuration = document.getElementById("cell_duration");
        const cellAction = document.getElementById("cell_action");

        cellMin.style.display = "none";
        cellMax.style.display = "none";
        cellStrength.style.display = "none";
        cellDuration.style.display = "none";
        cellAction.style.display = "none";

        if (!type) return;

        if (type === "vibration") {
            cellMin.style.display = "flex";
            cellMax.style.display = "flex";
            cellStrength.style.display = "flex";
            cellDuration.style.display = "flex";
        }

        if (type === "custom") {
            cellMin.style.display = "flex";
            cellMax.style.display = "flex";
            cellAction.style.display = "flex";
        }

        if (type === "wheel") {
            cellMin.style.display = "flex";
            cellMax.style.display = "flex";
        }
    };
}
/* ============================================================
   🎛 Формы правил (WebSocket)
============================================================ */
export function initRuleForms() {
    if (!document.querySelector(".rules-page")) return;

    const addForm = document.getElementById("addRuleForm");
    const editForm = document.getElementById("ruleEditForm");
    const segForm = document.getElementById("segmentAddForm");

    if (addForm) addForm.replaceWith(addForm.cloneNode(true));
    if (editForm) editForm.replaceWith(editForm.cloneNode(true));
    if (segForm) segForm.replaceWith(segForm.cloneNode(true));

    const addFormNew = document.getElementById("addRuleForm");
    const editFormNew = document.getElementById("ruleEditForm");
    const segFormNew = document.getElementById("segmentAddForm");

    /* ➕ Добавление правила */
    if (addFormNew) {
        addFormNew.addEventListener("submit", (e) => {
            e.preventDefault();

            const payload = {
                type: "add_rule",
                profile_key: CURRENT_PROFILE,
                min: Number(document.getElementById("new_min").value),
                max: Number(document.getElementById("new_max").value),
                strength: Number(document.getElementById("new_strength").value || 0),
                duration: Number(document.getElementById("new_duration").value || 0),
                action_type: document.getElementById("new_action_type").value,
                action: document.getElementById("new_action").value || ""
            };

            sendRuleCommand(payload);
            showToast("Правило добавлено");

            reloadInnerContent(() => {
                if (document.querySelector(".rules-page")) {
                    initRulesPage();
                    initRuleForms();
                    initRuleModals();
                }
            });
        });
    }

    /* ✏️ Редактирование правила */
    if (editFormNew) {
        editFormNew.addEventListener("submit", (e) => {
            e.preventDefault();

            const payload = {
                type: "edit_rule",
                profile_key: CURRENT_PROFILE,
                id: document.getElementById("edit_rule_id").value,
                min: Number(document.getElementById("edit_min").value),
                max: Number(document.getElementById("edit_max").value),
                strength: Number(document.getElementById("edit_strength").value || 0),
                duration: Number(document.getElementById("edit_duration").value || 0),
                action_type: document.getElementById("edit_type").value,
                action: document.getElementById("edit_action").value || ""
            };

            sendRuleCommand(payload);
            showToast("Правило обновлено");

            reloadInnerContent(() => {
                if (document.querySelector(".rules-page")) {
                    initRulesPage();
                    initRuleForms();
                    initRuleModals();
                }
            });
        });
    }

    /* 🎡 Добавление сегмента */
    if (segFormNew) {
        segFormNew.addEventListener("submit", (e) => {
            e.preventDefault();

            const payload = {
                type: "add_segment",
                profile_key: CURRENT_PROFILE,
                rule_id: document.getElementById("segment_rule_id").value,
                name: document.getElementById("seg_name").value,
                chance: Number(document.getElementById("seg_chance").value),
                seg_type: document.getElementById("seg_type").value,
                strength: Number(document.getElementById("seg_strength").value || 0),
                duration: Number(document.getElementById("seg_duration").value || 0),
                action: document.getElementById("seg_action").value || ""
            };

            sendRuleCommand(payload);
            showToast("Сегмент добавлен");

            reloadInnerContent(() => {
                if (document.querySelector(".rules-page")) {
                    initRulesPage();
                    initRuleForms();
                    initRuleModals();
                }
            });
        });
    }
}

/* ============================================================
   🎛 Модалки правил
============================================================ */
export function initRuleModals() {
    if (!document.querySelector(".rules-page")) return;

    window.openRuleModal = (id) => {
        const modal = document.getElementById("ruleModal");
        modal.classList.add("show");

        const card = document.querySelector(`[data-rule-id="${id}"]`);

        window._originalRuleData = {
            min: card.dataset.min,
            max: card.dataset.max,
            strength: card.dataset.strength,
            duration: card.dataset.duration,
            action: card.dataset.action || "",
            type: card.dataset.type
        };

        document.getElementById("edit_rule_id").value = id;
        document.getElementById("edit_min").value = card.dataset.min;
        document.getElementById("edit_max").value = card.dataset.max;
        document.getElementById("edit_strength").value = card.dataset.strength;
        document.getElementById("edit_duration").value = card.dataset.duration;
        document.getElementById("edit_action").value =
            card.dataset.type === "custom" ? (card.dataset.action || "") : "";
        document.getElementById("edit_type").value = card.dataset.type;

        updateRuleEditFields();
    };

    window.closeRuleModal = () => {
        const modal = document.getElementById("ruleModal");
        modal.classList.remove("show");

        if (window._originalRuleData) {
            document.getElementById("edit_min").value = window._originalRuleData.min;
            document.getElementById("edit_max").value = window._originalRuleData.max;
            document.getElementById("edit_strength").value = window._originalRuleData.strength;
            document.getElementById("edit_duration").value = window._originalRuleData.duration;
            document.getElementById("edit_action").value = window._originalRuleData.action;
            document.getElementById("edit_type").value = window._originalRuleData.type;

            updateRuleEditFields();
        }
    };

    window.openSegmentModal = (ruleId) => {
        const modal = document.getElementById("segmentModal");
        modal.classList.add("show");
        document.getElementById("segment_rule_id").value = ruleId;
    };

    window.closeSegmentModal = () => {
        document.getElementById("segmentModal").classList.remove("show");
    };

    window.toggleWheel = (ruleId) => {
        const block = document.getElementById(`wheel-${ruleId}`);
        if (!block) return;

        if (block.classList.contains("hidden")) {
            block.classList.remove("hidden");
            block.classList.add("show");
        } else {
            block.classList.remove("show");
            block.classList.add("hidden");
        }
    };
}
/* ============================================================
   🎡 Переключение полей сегмента
============================================================ */
export function updateSegmentFields(selectEl) {
    const modal = selectEl.closest(".modal-content");

    const vib = modal.querySelector(".seg-vibration-fields");
    const act = modal.querySelector(".seg-action-fields");
    const retry = modal.querySelector(".seg-retry-fields");

    vib.classList.add("hidden");
    act.classList.add("hidden");
    retry.classList.add("hidden");

    if (selectEl.value === "vibration") vib.classList.remove("hidden");
    if (selectEl.value === "action") act.classList.remove("hidden");
    if (selectEl.value === "retry") retry.classList.remove("hidden");
}
