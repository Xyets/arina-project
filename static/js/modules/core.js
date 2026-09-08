export let CURRENT_PAGE_URL = "/beta";

export const app = document.getElementById("app");
export const CURRENT_USER = app?.dataset.user || "";
export let CURRENT_MODE = app?.dataset.mode || "public";
export let CURRENT_PROFILE = app?.dataset.profile || "";

export let goal = {
    title: "",
    current: 0,
    target: 0
};
