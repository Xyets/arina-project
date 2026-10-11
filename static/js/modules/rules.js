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
            const selectedType = form.querySelector("#seg_type")?.value || "";
            const segmentName = form.querySelector("#seg_name")?.value.trim() || "";
            if (!selectedType) {
                showToast("Сначала выбери тип сегмента");
                return;
            }
            if (selectedType !== "retry" && !segmentName) {
                showToast("Введи название приза");
                return;
            }
            if (selectedType === "vibration" &&
                (!Number(form.querySelector("#seg_strength")?.value) ||
                 !Number(form.querySelector("#seg_duration")?.value))) {
                showToast("Укажи силу и время вибрации");
                return;
            }
            if (selectedType === "action" &&
                !(form.querySelector("#seg_action")?.value || "").trim()) {
                showToast("Добавь описание действия для лога");
                return;
            }

            const payload = {
                type: "add_segment",
                profile_key: CURRENT_PROFILE,

                rule_id:
                    form.querySelector("#segment_rule_id")?.value || "",

                name:
                    form.querySelector("#seg_name")?.value.trim() || "",

                emoji:
                    form.querySelector("#seg_emoji")?.value.trim() || "✨",

                chance: 0,

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
            closeSegmentModal();
            return;
        }

        /* ========================================================
           ✏️ Редактирование сегмента
        ======================================================== */
        if (e.target && e.target.id === "segmentEditForm") {
            e.preventDefault();
            e.stopPropagation();

            const form = e.target;
            const type = form.querySelector("#edit_seg_type")?.value || "";
            if (!(form.querySelector("#edit_seg_name")?.value || "").trim()) {
                showToast("Введи название приза");
                return;
            }
            if (!(form.querySelector("#edit_seg_emoji")?.value || "").trim()) {
                showToast("Введи эмодзи");
                return;
            }
            if (type === "vibration" &&
                (!Number(form.querySelector("#edit_seg_strength")?.value) ||
                 !Number(form.querySelector("#edit_seg_duration")?.value))) {
                showToast("Укажи силу и время вибрации");
                return;
            }
            if (type === "action" &&
                !(form.querySelector("#edit_seg_action")?.value || "").trim()) {
                showToast("Добавь описание действия для лога");
                return;
            }
            const payload = {
                type: "edit_segment",
                profile_key: CURRENT_PROFILE,
                rule_id: form.querySelector("#edit_segment_rule_id")?.value || "",
                seg_index: Number(form.querySelector("#edit_segment_index")?.value || -1),
                name: form.querySelector("#edit_seg_name")?.value.trim() || "",
                emoji: form.querySelector("#edit_seg_emoji")?.value.trim() || "✨",
                seg_type: type,
                strength: type === "vibration" ? Number(form.querySelector("#edit_seg_strength")?.value || 0) : 0,
                duration: type === "vibration" ? Number(form.querySelector("#edit_seg_duration")?.value || 0) : 0,
                action: type === "action" ? (form.querySelector("#edit_seg_action")?.value.trim() || "") : ""
            };

            sendRuleCommand(socket, payload);
            closeSegmentEditModal();
            showToast("Сегмент обновлён");
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
        const form = document.getElementById("segmentAddForm");
        form.reset();
        document.getElementById("seg_name").disabled = false;
        document.getElementById("seg_emoji").disabled = false;
        document.getElementById("segment_rule_id").value = ruleId;
        document.getElementById("seg_type").value = "";
        document.getElementById("seg_emoji").value = "";
        document.getElementById("segEmojiPreview").textContent = "✨";
        updateSegmentFields(document.getElementById("seg_type"));
        modal.classList.add("show");
    };

    window.closeSegmentModal = () => {
        document.getElementById("segmentModal").classList.remove("show");
    };

    window.openSegmentEditModal = (ruleId, segIndex) => {
        const card = document.querySelector(
            `#wheel-${CSS.escape(ruleId)} .segment-card:nth-of-type(${Number(segIndex) + 2})`
        );
        // Cards may be nested alongside headings/buttons; fall back to indexed card list.
        const cards = Array.from(document.querySelectorAll(`#wheel-${CSS.escape(ruleId)} .segment-card`));
        const segmentCard = cards[Number(segIndex)];
        if (!segmentCard || segmentCard.classList.contains("segment-card-fixed")) return;

        const form = document.getElementById("segmentEditForm");
        form.reset();
        document.getElementById("edit_segment_rule_id").value = ruleId;
        document.getElementById("edit_segment_index").value = segIndex;
        document.getElementById("edit_seg_name").value = segmentCard.dataset.segName || "";
        document.getElementById("edit_seg_emoji").value = segmentCard.dataset.segEmoji || "✨";
        document.getElementById("editSegEmojiPreview").textContent = segmentCard.dataset.segEmoji || "✨";
        document.getElementById("edit_seg_type").value = segmentCard.dataset.segType || "vibration";
        document.getElementById("edit_seg_strength").value = segmentCard.dataset.segStrength || "";
        document.getElementById("edit_seg_duration").value = segmentCard.dataset.segDuration || "";
        document.getElementById("edit_seg_action").value = segmentCard.dataset.segAction || "";
        updateSegmentFields(document.getElementById("edit_seg_type"));
        document.getElementById("segmentEditModal").classList.add("show");
    };

    window.closeSegmentEditModal = () => {
        document.getElementById("segmentEditModal").classList.remove("show");
    };

    // Custom emoji input and quick-pick buttons.
    document.querySelectorAll(".emoji-quick-picks").forEach(group => {
        group.addEventListener("click", event => {
            const button = event.target.closest("button[data-emoji]");
            if (!button) return;
            const modal = button.closest(".modal");
            const input = modal?.querySelector('input[name="seg_emoji"]');
            const preview = modal?.querySelector(".emoji-live-preview");
            if (input) input.value = button.dataset.emoji;
            if (preview) preview.textContent = button.dataset.emoji;
        });
    });

    [["seg_emoji", "segEmojiPreview"], ["edit_seg_emoji", "editSegEmojiPreview"]].forEach(([inputId, previewId]) => {
        const input = document.getElementById(inputId);
        const preview = document.getElementById(previewId);
        if (input && preview) input.addEventListener("input", () => {
            preview.textContent = input.value || "✨";
        });
    });

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
    if (!selectEl) return;
    const form = selectEl.closest("form");
    if (!form) return;

    const vib = form.querySelector(".seg-vibration-fields");
    const act = form.querySelector(".seg-action-fields");
    const retry = form.querySelector(".seg-retry-fields");

    [vib, act, retry].forEach(block => block?.classList.add("hidden"));

    if (selectEl.value === "vibration") vib?.classList.remove("hidden");
    if (selectEl.value === "action") act?.classList.remove("hidden");
    if (selectEl.value === "retry") {
        retry?.classList.remove("hidden");
        const name = form.querySelector("#seg_name");
        const emoji = form.querySelector("#seg_emoji");
        if (name) { name.value = "もう一回"; name.disabled = true; }
        if (emoji) { emoji.value = "🔁"; emoji.disabled = true; }
        const preview = form.querySelector(".emoji-live-preview");
        if (preview) preview.textContent = "🔁";
    } else {
        const name = form.querySelector("#seg_name");
        const emoji = form.querySelector("#seg_emoji");
        if (name) name.disabled = false;
        if (emoji) emoji.disabled = false;
    }
}

// Used by the existing inline onchange handlers in the template.
window.updateSegmentFields = updateSegmentFields;
