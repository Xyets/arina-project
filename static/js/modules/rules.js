// static/js/modules/rules.js

/* ============================================================
   RULES — WebSocket helpers
============================================================ */

export function sendRuleCommand(socket, payload) {
    socket.send(JSON.stringify(payload));
}

/* ============================================================
   RULES — Delete rule / segment (без reloadInnerContent!)
============================================================ */

export function createDeleteRule(socket, CURRENT_PROFILE, showToast) {
    return function(id) {
        sendRuleCommand(socket, {
            type: "delete_rule",
            profile_key: CURRENT_PROFILE,
            id
        });

        showToast("Правило удалено");
        // SPA сама обновит страницу через WebSocket rules_update
    };
}

export function createDeleteSegment(socket, CURRENT_PROFILE, showToast) {
    return function(ruleId, segIndex) {
        sendRuleCommand(socket, {
            type: "delete_segment",
            profile_key: CURRENT_PROFILE,
            rule_id: ruleId,
            seg_index: segIndex
        });

        showToast("Сегмент удалён");
        // SPA сама обновит страницу через WebSocket rules_update
    };
}

/* ============================================================
   RULES — Page init
============================================================ */

export function initRulesPage(socket, showToast) {
    if (!document.querySelector(".rules-page")) return;

    // Заполнение прогресс‑баров сегментов
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
}

/* ============================================================
   RULES — Forms (Add / Edit / Segment)
============================================================ */

export function initRuleForms(CURRENT_PROFILE, socket, showToast) {
    if (!document.querySelector(".rules-page")) return;

    /*
     * Не привязываем submit непосредственно к form.
     *
     * После rules_update HTML формы заменяется.
     * Поэтому обычный addEventListener на старой форме терялся.
     *
     * Здесь используется один делегированный обработчик на document.
     * Он продолжает работать даже после полной замены формы.
     */

    if (window._flowtipRulesSubmitHandler) {
        document.removeEventListener(
            "submit",
            window._flowtipRulesSubmitHandler
        );
    }

    window._flowtipRulesSubmitHandler = function (e) {

        /* ========================================================
           ➕ Добавление правила
        ======================================================== */

        if (e.target && e.target.id === "addRuleForm") {
            e.preventDefault();
            e.stopPropagation();

            const form = e.target;
            console.log(
                "FLOWTIP DEBUG — выбранный тип:",
                form.querySelector("#new_action_type")?.value
            );
            const payload = {
                type: "add_rule",
                profile_key: CURRENT_PROFILE,

                min: Number(
                    form.querySelector("#new_min")?.value || 0
                ),

                max: Number(
                    form.querySelector("#new_max")?.value || 0
                ),

                strength: Number(
                    form.querySelector("#new_strength")?.value || 0
                ),

                duration: Number(
                    form.querySelector("#new_duration")?.value || 0
                ),

                action_type:
                    form.querySelector("#new_action_type")?.value || "",

                name:
                    form.querySelector("#new_name")?.value || "",

                action:
                    form.querySelector("#new_action")?.value || ""
            };

            sendRuleCommand(socket, payload);

            showToast("Правило добавлено");

            return;
        }


        /* ========================================================
           ✏️ Редактирование правила
        ======================================================== */

        if (e.target && e.target.id === "ruleEditForm") {
            e.preventDefault();
            e.stopPropagation();

            const form = e.target;

            const payload = {
                type: "edit_rule",
                profile_key: CURRENT_PROFILE,

                id:
                    form.querySelector("#edit_rule_id")?.value || "",

                min: Number(
                    form.querySelector("#edit_min")?.value || 0
                ),

                max: Number(
                    form.querySelector("#edit_max")?.value || 0
                ),

                strength: Number(
                    form.querySelector("#edit_strength")?.value || 0
                ),

                duration: Number(
                    form.querySelector("#edit_duration")?.value || 0
                ),

                action_type:
                    form.querySelector("#edit_type")?.value || "",

                name:
                    form.querySelector("#edit_name")?.value || "",

                action:
                    form.querySelector("#edit_action")?.value || ""
            };

            sendRuleCommand(socket, payload);

            showToast("Правило обновлено");

            return;
        }


        /* ========================================================
           🎡 Добавление сегмента
        ======================================================== */

        if (e.target && e.target.id === "segmentAddForm") {
            e.preventDefault();
            e.stopPropagation();

            const form = e.target;

            const payload = {
                type: "add_segment",
                profile_key: CURRENT_PROFILE,

                rule_id:
                    form.querySelector("#segment_rule_id")?.value || "",

                name:
                    form.querySelector("#seg_name")?.value || "",

                chance: Number(
                    form.querySelector("#seg_chance")?.value || 0
                ),

                seg_type:
                    form.querySelector("#seg_type")?.value || "",

                strength: Number(
                    form.querySelector("#seg_strength")?.value || 0
                ),

                duration: Number(
                    form.querySelector("#seg_duration")?.value || 0
                ),

                action:
                    form.querySelector("#seg_action")?.value || ""
            };

            sendRuleCommand(socket, payload);

            showToast("Сегмент добавлен");

            return;
        }
    };

    document.addEventListener(
        "submit",
        window._flowtipRulesSubmitHandler
    );
}

/* ============================================================
   RULES — Modals
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
            name: card.dataset.name || card.dataset.action || "",
            action: card.dataset.action || "",
            type: card.dataset.type
        };

        document.getElementById("edit_rule_id").value = id;
        document.getElementById("edit_min").value = card.dataset.min;
        document.getElementById("edit_max").value = card.dataset.max;
        document.getElementById("edit_strength").value = card.dataset.strength;
        document.getElementById("edit_duration").value = card.dataset.duration;
        const editName = document.getElementById("edit_name");

        if (editName) {
            editName.value =
                card.dataset.type === "custom"
                    ? (card.dataset.name || card.dataset.action || "")
                    : "";
        }

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
            document.getElementById("edit_duration").value =
                window._originalRuleData.duration;

            const editName = document.getElementById("edit_name");

            if (editName) {
                editName.value = window._originalRuleData.name || "";
            }

            document.getElementById("edit_action").value =
                window._originalRuleData.action;

            document.getElementById("edit_type").value =
                window._originalRuleData.type;

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
   RULES — Edit fields
============================================================ */

export function updateRuleEditFields() {
    const type = document.getElementById("edit_type").value;

    const strength = document.getElementById("edit_strength_block");
    const duration = document.getElementById("edit_duration_block");
    const name = document.getElementById("edit_name_block");
    const action = document.getElementById("edit_action_block");
    const typeBlock = document.getElementById("edit_type_display").parentElement;

    strength.classList.add("hidden");
    duration.classList.add("hidden");

    if (name) {
        name.classList.add("hidden");
    }

    action.classList.add("hidden");
    typeBlock.classList.add("hidden");

    if (type === "vibration") {
        strength.classList.remove("hidden");
        duration.classList.remove("hidden");
    }

    if (type === "custom") {
        if (name) {
            name.classList.remove("hidden");
        }

        action.classList.remove("hidden");
    }
}

/* ============================================================
   RULES — New rule fields
============================================================ */

export function updateNewRuleFields() {
    const type = document.getElementById("new_action_type").value;

    const cellMin = document.getElementById("cell_min");
    const cellMax = document.getElementById("cell_max");
    const cellStrength = document.getElementById("cell_strength");
    const cellDuration = document.getElementById("cell_duration");
    const cellName = document.getElementById("cell_name");
    const cellAction = document.getElementById("cell_action");

    cellMin.style.display = "none";
    cellMax.style.display = "none";
    cellStrength.style.display = "none";
    cellDuration.style.display = "none";

    if (cellName) {
        cellName.style.display = "none";
    }

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

        if (cellName) {
            cellName.style.display = "flex";
        }

        cellAction.style.display = "flex";
    }

    if (type === "wheel") {
        cellMin.style.display = "flex";
        cellMax.style.display = "flex";
    }
}

/* ============================================================
   RULES — Segment fields
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
