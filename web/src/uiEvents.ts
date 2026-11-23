// One opaque ID per loaded tab. Never persisted or derived from browser or report data.
const correlationId = globalThis.crypto?.randomUUID?.();
const uiLanguages = new Set(["en", "ar", "th", "hi", "ur"]);
function uiLanguage(value = document.documentElement.lang) {
  return uiLanguages.has(value) ? value : "en";
}
const actions = new Set([
  "explore_open",
  "report_open",
  "search_open",
  "insights_open",
  "case_open",
  "search_submit",
  "filter_apply",
  "help_open",
  "interface_language",
  "theme_change",
  "source_select",
  "answer_submit",
  "report_prepare",
  "report_submit",
  "status_update",
  "service_select",
  "map_interact",
  "report_language_select",
  "answer_language_select",
  "page_previous",
  "page_next",
  "list_view",
  "map_view",
  "clear_selection",
  "photo_remove",
  "location_apply",
  "location_current",
  "location_clear",
  "report_edit",
  "related_search",
  "translation_retry",
  "control_retry",
]);
const controls =
  "button,a[href],input,select,textarea,[role=button],[role=link],[role=tab],[contenteditable=true]";
const api =
  (import.meta.env.VITE_API_ORIGIN || "")
    .replace(/\/$/, "")
    .replace(/\/api$/, "") + "/api";
export const apiBase = api;

export function correlatedRequest(
  path: string,
  init?: RequestInit,
  language = uiLanguage(),
) {
  // Only fetch the configured CommonDesk API. Block redirects to avoid forwarding its ID.
  const headers = new Headers(init?.headers);
  if (correlationId) headers.set("X-Correlation-ID", correlationId);
  headers.set("X-UI-Language", uiLanguage(language));
  return fetch(api + path, { ...init, headers, redirect: "error" });
}

function actionFor(el: Element) {
  const hint = el.getAttribute("data-ui-action");
  if (hint && actions.has(hint)) return hint;
  if (el.closest(".leaflet-container")) return "map_interact";
  if (el.matches("button,input[type=submit],input[type=button],[role=button]"))
    return "control_button";
  if (el.matches("a,[role=link]")) return "control_link";
  if (el.matches("select")) return "control_select";
  if (el.matches("input[type=checkbox],input[type=radio]"))
    return "control_checkbox";
  if (el.matches("input[type=file]")) return "control_file";
  if (el.matches("input,textarea,[contenteditable=true]"))
    return "control_field";
  return "control_other";
}

export function listenForClicks(root: HTMLElement) {
  function record(el: Element, language = uiLanguage()) {
    if (!correlationId) return;
    const action = actionFor(el);
    console.info("ui.click", { action, correlationId, uiLanguage: language });
    void correlatedRequest(
      "/ui-events",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
        credentials: "omit",
        referrerPolicy: "no-referrer",
        keepalive: true,
      },
      language,
    ).catch(() => {});
  }
  function click(event: Event) {
    const el =
      event.target instanceof Element && event.target.closest(controls);
    if (
      el &&
      root.contains(el) &&
      el.getAttribute("data-ui-action") !== "interface_language"
    )
      record(el);
  }
  // Buttons and links already dispatch click on keyboard activation. Native selects
  // can change via arrow keys without a click. Do not observe text entry or raw keys.
  let keyboard = false;
  const onKey = () => {
    keyboard = true;
  };
  const onPointer = () => {
    keyboard = false;
  };
  function selectChange(event: Event) {
    if (!(event.target instanceof HTMLSelectElement)) return;
    if (event.target.getAttribute("data-ui-action") === "interface_language") {
      record(event.target, uiLanguage(event.target.value));
    } else if (keyboard) record(event.target);
  }
  root.addEventListener("click", click, true);
  root.addEventListener("keydown", onKey, true);
  root.addEventListener("pointerdown", onPointer, true);
  root.addEventListener("change", selectChange, true);
  return () => {
    root.removeEventListener("click", click, true);
    root.removeEventListener("keydown", onKey, true);
    root.removeEventListener("pointerdown", onPointer, true);
    root.removeEventListener("change", selectChange, true);
  };
}
