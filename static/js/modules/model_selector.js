// Model-to-model statistics navigation has been disabled.
// The server now enforces that each model can view only its own statistics.
export function initModelSelector() {
    const select = document.getElementById("modelSelect");
    if (select) select.remove();
}
