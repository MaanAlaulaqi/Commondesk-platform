import type L from "leaflet";
import { maplibreGL } from "@maplibre/maplibre-gl-leaflet";
import { setWorkerUrl, type StyleSpecification } from "maplibre-gl";
import workerURL from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import ar400 from "@fontsource/noto-sans-arabic/files/noto-sans-arabic-arabic-400-normal.woff2?url";
import ar700 from "@fontsource/noto-sans-arabic/files/noto-sans-arabic-arabic-700-normal.woff2?url";
import hi400 from "@fontsource/noto-sans-devanagari/files/noto-sans-devanagari-devanagari-400-normal.woff2?url";
import hi700 from "@fontsource/noto-sans-devanagari/files/noto-sans-devanagari-devanagari-700-normal.woff2?url";
import th400 from "@fontsource/noto-sans-thai/files/noto-sans-thai-thai-400-normal.woff2?url";
import th700 from "@fontsource/noto-sans-thai/files/noto-sans-thai-thai-700-normal.woff2?url";
import "maplibre-gl/dist/maplibre-gl.css";
import { labelFields, languageName, nameExpression } from "./basemapLabels";

// Explicit asset URL keeps Vite from rewriting the worker relative to a bundled chunk.
setWorkerUrl(workerURL);

const styleURL = "https://vector.openstreetmap.org/styles/shortbread/colorful.json";
const attribution =
  '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

export async function addLocalizedBasemap(
  map: L.Map,
  raster: L.TileLayer,
  currentLanguage: () => string,
  signal: AbortSignal,
) {
  const response = await fetch(styleURL, { signal });
  if (!response.ok) return;
  const style: StyleSpecification = await response.json();
  // Shortbread supplies Latin glyphs. Font files let the browser shape joined
  // Arabic/Urdu letters, Devanagari clusters and Thai marks as complete labels.
  const scriptFaces = (arabic: string, devanagari: string, thai: string) => [
    { url: arabic, "unicode-range": ["U+0600-06FF", "U+0750-077F", "U+08A0-08FF"] },
    { url: devanagari, "unicode-range": ["U+0900-097F"] },
    { url: thai, "unicode-range": ["U+0E00-0E7F"] },
  ];
  style["font-faces"] = {
    ...style["font-faces"],
    noto_sans_regular: scriptFaces(ar400, hi400, th400),
    noto_sans_bold: scriptFaces(ar700, hi700, th700),
  };
  const names = labelFields(style);
  if (!names.length || signal.aborted) return;
  const layer = maplibreGL({
    style,
    attributionControl: false,
    interactive: false,
  });
  // The adapter assumes GL construction succeeded when removing the layer.
  // If construction throws, still let Leaflet detach the half-created layer.
  const onRemove = layer.onRemove.bind(layer);
  layer.onRemove = (owner) => {
    if (layer.getMaplibreMap()) return onRemove(owner);
    layer.getContainer()?.remove();
    return layer;
  };
  let gl: ReturnType<typeof layer.getMaplibreMap> | undefined;
  function cleanup() {
    if (map.hasLayer(layer)) map.removeLayer(layer);
    if (shown) map.attributionControl.removeAttribution(attribution);
  }
  let shown = false;
  signal.addEventListener("abort", cleanup, { once: true });
  try {
    layer.addTo(map);
    gl = layer.getMaplibreMap();
    const container = layer.getContainer();
    container.classList.add("base-tiles");
    container.style.opacity = "0";
    const setLanguage = () => {
      const field = languageName(currentLanguage());
      for (const id of names) {
        gl?.setLayoutProperty(id, "text-field", nameExpression(currentLanguage()));
      }
      container.dataset.labelField = field;
    };
    gl.once("style.load", setLanguage);
    gl.once("idle", () => {
      if (signal.aborted || !map.hasLayer(layer) || !gl?.areTilesLoaded()) return;
      map.attributionControl.addAttribution(attribution);
      container.style.opacity = "1";
      map.removeLayer(raster);
      shown = true;
    });
    gl.on("webglcontextlost", () => {
      if (signal.aborted) return;
      if (!map.hasLayer(raster)) raster.addTo(map);
      cleanup();
      shown = false;
    });
    return () => { if (gl?.getLayer(names[0]) && map.hasLayer(layer)) setLanguage(); };
  } catch {
    cleanup();
  }
}
