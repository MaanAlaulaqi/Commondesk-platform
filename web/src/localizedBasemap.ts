import type L from "leaflet";
import { maplibreGL } from "@maplibre/maplibre-gl-leaflet";
import { setWorkerUrl, type StyleSpecification } from "maplibre-gl";
import workerURL from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
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
    clearTimeout(deadline);
    if (map.hasLayer(layer)) map.removeLayer(layer);
    if (shown) map.attributionControl.removeAttribution(attribution);
  }
  let shown = false;
  const deadline = window.setTimeout(cleanup, 12000);
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
      clearTimeout(deadline);
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
