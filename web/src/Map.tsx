import { useContext, useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet.markercluster";
import "leaflet/dist/leaflet.css";
import { type Case, type Coordinate } from "./client";
import { Locale, useWords } from "./locale";

type Props = {
  items?: Case[];
  selected?: string;
  onSelect?: (id: string) => void;
  onCluster?: (ids: string[]) => void;
  editable?: boolean;
  point?: Coordinate | null;
  onPoint?: (p: Coordinate) => void;
  remember?: boolean;
  label: string;
};
export default function CaseMap(props: Props) {
  const language = useContext(Locale), t = useWords();
  const zoomIn = t("zoomIn"), zoomOut = t("zoomOut"), location = t("location");
  const activeLanguage = useRef(language);
  activeLanguage.current = language;
  const onLanguage = useRef<(() => void) | undefined>(undefined);
  const zoomControl = useRef<L.Control.Zoom | null>(null);
  const host = useRef<HTMLDivElement>(null),
    map = useRef<L.Map | null>(null),
    current = useRef(props),
    markers = useRef(new Map<string, L.Marker>()),
    group = useRef<L.MarkerClusterGroup | null>(null);
  current.current = props;
  useEffect(() => {
    if (!host.current) return;
    let center: L.LatLngExpression = [25.222, 55.297],
      zoom = 12;
    if (props.remember) {
      try {
        const saved = JSON.parse(
          sessionStorage.getItem("commondesk-view") || "null",
        );
        if (saved) {
          center = saved.center;
          zoom = saved.zoom;
        }
      } catch {
        /* New map */
      }
    }
    const m = L.map(host.current, {
      center,
      zoom,
      zoomControl: false,
      preferCanvas: true,
      scrollWheelZoom: true,
    });
    map.current = m;
    zoomControl.current = L.control.zoom({ position: "bottomright" }).addTo(m);
    L.control.scale({ position: "bottomleft", imperial: false }).addTo(m);
    const raster = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution:
        '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      className: "base-tiles",
    }).addTo(m);
    const controller = new AbortController();
    if (import.meta.env.VITE_LOCALIZED_BASEMAP === "1") {
      void import("./localizedBasemap")
        .then(({ addLocalizedBasemap }) => addLocalizedBasemap(
          m, raster, () => activeLanguage.current, controller.signal,
        ))
        .then((update) => { if (!controller.signal.aborted) onLanguage.current = update; })
        .catch(() => { /* Keep the raster basemap if the vector style is unavailable. */ });
    }
    m.attributionControl.setPrefix(false);
    m.on("moveend", () => {
      if (current.current.remember) {
        const c = m.getCenter();
        sessionStorage.setItem(
          "commondesk-view",
          JSON.stringify({ center: [c.lat, c.lng], zoom: m.getZoom() }),
        );
      }
    });
    if (props.editable)
      m.on("click", (e: L.LeafletMouseEvent) =>
        current.current.onPoint?.({
          latitude: +e.latlng.lat.toFixed(6),
          longitude: +e.latlng.wrap().lng.toFixed(6),
          location_source: "map",
        }),
      );
    const ro = new ResizeObserver(() => m.invalidateSize());
    ro.observe(host.current);
    return () => {
      ro.disconnect();
      controller.abort();
      onLanguage.current = undefined;
      zoomControl.current = null;
      m.remove();
      map.current = null;
    };
  }, [props.editable, props.remember]);
  useEffect(() => {
    onLanguage.current?.();
    const container = zoomControl.current?.getContainer();
    for (const [selector, text] of [
      [".leaflet-control-zoom-in", zoomIn],
      [".leaflet-control-zoom-out", zoomOut],
    ]) {
      const control = container?.querySelector(selector);
      control?.setAttribute("title", text);
      control?.setAttribute("aria-label", text);
    }
  }, [language, props.editable, props.remember, zoomIn, zoomOut]);
  useEffect(() => {
    const m = map.current;
    if (!m || props.editable) return;
    const g = L.markerClusterGroup({
      maxClusterRadius: 42,
      showCoverageOnHover: false,
      animate: false,
      zoomToBoundsOnClick: true,
      iconCreateFunction: (c) =>
        L.divIcon({
          className: "cluster-pin",
          html: "<span>" + c.getChildCount() + "</span>",
          iconSize: [37, 37],
        }),
    });
    const lookup = new Map<string, L.Marker>();
    for (const c of props.items || []) {
      if (c.latitude == null || c.longitude == null) continue;
      const marker = L.marker([c.latitude, c.longitude], {
        title: c.id,
        alt: c.id,
        icon: makePin(false),
      });
      marker.on("click", () => current.current.onSelect?.(c.id));
      lookup.set(c.id, marker);
    }
    const ids = new Map([...lookup].map(([id, m]) => [m, id]));
    g.on("clusterclick", (e) =>
      current.current.onCluster?.(
        e.layer
          .getAllChildMarkers()
          .flatMap((marker: L.Marker) => ids.get(marker) || []),
      ),
    );
    g.addLayers([...lookup.values()]);
    g.addTo(m);
    group.current = g;
    markers.current = lookup;
    return () => {
      m.removeLayer(g);
    };
  }, [props.items, props.editable]);
  useEffect(() => {
    if (!props.selected) return;
    const marker = markers.current.get(props.selected);
    if (marker) {
      marker.setIcon(makePin(true));
      group.current?.zoomToShowLayer(marker, () =>
        marker.getElement()?.classList.add("chosen"),
      );
      return () => {
        marker.setIcon(makePin(false));
      };
    }
  }, [props.selected, props.items]);
  useEffect(() => {
    const m = map.current;
    if (!m || !props.editable || !props.point) return;
    const { latitude, longitude } = props.point;
    const marker = L.marker([latitude, longitude], {
      draggable: true,
      icon: makePin(true),
      title: location,
      alt: location,
    }).addTo(m);
    if (!m.getBounds().contains([latitude, longitude]))
      m.panTo([latitude, longitude]);
    marker.on("dragend", () => {
      const p = marker.getLatLng().wrap();
      current.current.onPoint?.({
        latitude: +p.lat.toFixed(6),
        longitude: +p.lng.toFixed(6),
        location_source: "map",
      });
    });
    return () => {
      m.removeLayer(marker);
    };
  }, [props.editable, props.point, location]);
  return (
    <div
      dir="ltr"
      ref={host}
      className="case-map"
      role="region"
      aria-label={props.label}
    />
  );
}
function makePin(selected: boolean) {
  return L.divIcon({
    className: "map-pin" + (selected ? " chosen" : ""),
    html: "<span></span>",
    iconSize: [23, 27],
    iconAnchor: [11, 25],
  });
}
