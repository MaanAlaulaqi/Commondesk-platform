import type { StyleSpecification } from "maplibre-gl";

const supported = new Set(["en", "ar", "th", "hi", "ur"]);
export const languageName = (locale: string) =>
  "name_" + (supported.has(locale) ? locale : "en");

export const labelFields = (style: StyleSpecification) =>
  style.layers.flatMap((layer) => {
    if (layer.type !== "symbol") return [];
    const field = layer.layout?.["text-field"];
    return field === "{name}" ||
      (Array.isArray(field) && field.length === 2 && field[0] === "get" && field[1] === "name")
      ? [layer.id]
      : [];
  });

export function nameExpression(locale: string): [
  "coalesce", ["get", string], ["get", "name"], string,
] {
  return ["coalesce", ["get", languageName(locale)], ["get", "name"], ""];
}
