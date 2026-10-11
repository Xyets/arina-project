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
            const selectedType = form.querySelector("#seg_type")?.value || "";
            const segmentName = form.querySelector("#seg_name")?.value.trim() || "";

            if (!selectedType) {
                showToast("Сначала выбери тип сегмента");
                return;
            }

            if (selectedType !== "retry" && !segmentName) {
                showToast("Введи название сегмента");
                return;
            }

            if (
                selectedType === "vibration" &&
                (
                    !form.querySelector("#seg_strength")?.value ||
                    !form.querySelector("#seg_duration")?.value
                )
            ) {
                showToast("Укажи силу и время вибрации");
                return;
            }

            if (
                selectedType === "action" &&
                !form.querySelector("#seg_action")?.value.trim()
            ) {
                showToast("Опиши действие");
                return;
            }
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

            if (payload.action_type === "wheel") {
                const editor = document.getElementById("wheelChanceList");
                const segments = editor
                    ? Array.from(editor.querySelectorAll(".wheel-chance-row")).map(row => ({
                        index: Number(row.dataset.index),
                        chance: Number(row.querySelector("input[type=range]")?.value || 0)
                    }))
                    : [];
                const total = segments.reduce((sum, seg) => sum + seg.chance, 0);
                if (!segments.length) {
                    showToast("Сначала добавь хотя бы один сегмент");
                    return;
                }
                if (total !== 100) {
                    showToast(`Сумма вероятностей должна быть 100%. Сейчас: ${total}%`);
                    return;
                }
                sendRuleCommand(socket, {
                    type: "edit_wheel_settings",
                    profile_key: CURRENT_PROFILE,
                    id: payload.id,
                    min: payload.min,
                    max: payload.max,
                    segments
                });
            } else {
                sendRuleCommand(socket, payload);
            }

            showToast("Настройки сохранены");
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
                showToast("Введи название сегмента");
                return;
            }

            if (
                selectedType === "vibration" &&
                (
                    !form.querySelector("#seg_strength")?.value ||
                    !form.querySelector("#seg_duration")?.value
                )
            ) {
                showToast("Укажи силу и время вибрации");
                return;
            }

            if (
                selectedType === "action" &&
                !form.querySelector("#seg_action")?.value.trim()
            ) {
                showToast("Опиши действие");
                return;
            }
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
        const wheelBlock = document.getElementById("wheelSettingsBlock");
        const wheelList = document.getElementById("wheelChanceList");
        const saveButton = document.querySelector("#ruleEditForm .modal-save-btn");
        if (wheelBlock) {
            const isWheel = card.dataset.type === "wheel";
            wheelBlock.classList.toggle("hidden", !isWheel);
            if (isWheel) {
                let segments = [];
                try { segments = JSON.parse(card.dataset.segments || "[]"); } catch (e) { segments = []; }
                renderWheelChanceEditor(segments);
                if (saveButton) saveButton.textContent = "💾 Сохранить настройки колеса";
            } else if (saveButton) {
                saveButton.textContent = "💾 Сохранить";
                saveButton.disabled = false;
            }
        }
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

        if (form) form.reset();

        document.getElementById("segment_rule_id").value = ruleId;

        const typeSelect = document.getElementById("seg_type");
        if (typeSelect) {
            typeSelect.value = "";
            const customDisplay = document.getElementById("segmentTypeDisplay");
            const customOptions = document.getElementById("segmentTypeOptions");

            if (customDisplay) {
                customDisplay.textContent = "Выберите тип сегмента";
            }

            if (customOptions) {
                customOptions.style.display = "none";
            }
        }

        const chanceInput = document.getElementById("seg_chance");
        if (chanceInput) {
            chanceInput.value = "0";
        }

        updateSegmentFields(typeSelect);
        modal.classList.add("show");
    };

    const segmentTypeSelect = document.getElementById("segmentTypeSelect");
    const segmentTypeDisplay = document.getElementById("segmentTypeDisplay");
    const segmentTypeOptions = document.getElementById("segmentTypeOptions");
    const segmentTypeInput = document.getElementById("seg_type");

    if (
        segmentTypeSelect &&
        segmentTypeDisplay &&
        segmentTypeOptions &&
        segmentTypeInput &&
        !segmentTypeSelect.dataset.initialized
    ) {
        segmentTypeSelect.dataset.initialized = "true";

        const closeSegmentTypeOptions = () => {
            segmentTypeOptions.style.display = "none";
            segmentTypeDisplay.setAttribute("aria-expanded", "false");
        };

        segmentTypeDisplay.addEventListener("click", (event) => {
            event.stopPropagation();

            const isOpen = segmentTypeOptions.style.display === "flex";

            segmentTypeOptions.style.display = isOpen ? "none" : "flex";
            segmentTypeDisplay.setAttribute("aria-expanded", String(!isOpen));
        });

        segmentTypeDisplay.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                segmentTypeDisplay.click();
            }

            if (event.key === "Escape") {
                closeSegmentTypeOptions();
            }
        });

        segmentTypeOptions.querySelectorAll(".option").forEach((option) => {
            option.addEventListener("click", (event) => {
                event.stopPropagation();

                const value = option.dataset.value;
                segmentTypeInput.value = value;
                segmentTypeDisplay.textContent = option.textContent.trim();

                closeSegmentTypeOptions();

                // Показываем поля, соответствующие выбранному типу.
                updateSegmentFields(segmentTypeInput);
            });
        });

        document.addEventListener("click", (event) => {
            if (!segmentTypeSelect.contains(event.target)) {
                closeSegmentTypeOptions();
            }
        });

        // Начальное состояние
        segmentTypeOptions.style.display = "none";
    }

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
   RULES — Wheel chance editor
============================================================ */
function renderWheelChanceEditor(segments) {
    const list = document.getElementById("wheelChanceList");
    if (!list) return;
    list.innerHTML = "";

    segments.forEach((segment, index) => {
        const row = document.createElement("div");
        row.className = "wheel-chance-row";
        row.dataset.index = String(index);

        const label = document.createElement("label");
        label.className = "wheel-chance-label";
        label.textContent = segment.name || segment.action || `Сегмент ${index + 1}`;

        const slider = document.createElement("input");
        slider.type = "range";
        slider.min = "0";
        slider.max = "100";
        slider.step = "1";
        slider.value = String(Math.max(0, Math.min(100, Number(segment.chance) || 0)));
        slider.setAttribute("aria-label", `Шанс сегмента ${label.textContent}`);

        const value = document.createElement("output");
        value.className = "wheel-chance-value";
        value.textContent = `${slider.value}%`;

        slider.addEventListener("input", () => {
            value.textContent = `${slider.value}%`;
            updateWheelChanceTotal();
        });

        row.append(label, slider, value);
        list.appendChild(row);
    });
    updateWheelChanceTotal();
}

function updateWheelChanceTotal() {
    const list = document.getElementById("wheelChanceList");
    if (!list) return;
    const sliders = Array.from(list.querySelectorAll('input[type="range"]'));
    const total = sliders.reduce((sum, slider) => sum + Number(slider.value || 0), 0);
    const totalEl = document.getElementById("wheelChanceTotal");
    const errorEl = document.getElementById("wheelChanceError");
    const saveButton = document.querySelector("#ruleEditForm .modal-save-btn");
    if (totalEl) totalEl.textContent = `${total}%`;
    if (totalEl) totalEl.classList.toggle("is-valid", total === 100);
    if (totalEl) totalEl.classList.toggle("is-invalid", total !== 100);
    if (errorEl) errorEl.textContent = sliders.length && total !== 100
        ? `До сохранения осталось ${100 - total > 0 ? `добавить ${100 - total}%` : `уменьшить на ${total - 100}%`}.`
        : (sliders.length ? "Вероятности распределены на 100%." : "Добавь сегменты, чтобы настроить колесо.");
    if (saveButton && document.getElementById("edit_type")?.value === "wheel") {
        saveButton.disabled = sliders.length === 0 || total !== 100;
    }
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

    const modal = selectEl.closest(".modal-content");
    if (!modal) return;

    const vib = modal.querySelector(".seg-vibration-fields");
    const act = modal.querySelector(".seg-action-fields");
    const retry = modal.querySelector(".seg-retry-fields");

    if (vib) vib.classList.add("hidden");
    if (act) act.classList.add("hidden");
    if (retry) retry.classList.add("hidden");

    if (selectEl.value === "vibration" && vib) {
        vib.classList.remove("hidden");
    } else if (selectEl.value === "action" && act) {
        act.classList.remove("hidden");
    } else if (selectEl.value === "retry" && retry) {
        retry.classList.remove("hidden");
    }
}

// Делаем функцию доступной для onchange в HTML.
window.updateSegmentFields = updateSegmentFields;
