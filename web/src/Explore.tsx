import { PageOrientation } from "./PageOrientation";
import { useContext, useEffect, useMemo, useState } from "react";
import {
  ArrowDown,
  ChevronLeft,
  ChevronRight,
  Layers3,
  List,
  Map as MapIcon,
  MapPin,
  PanelLeft,
  PanelRight,
  Triangle,
} from "lucide-react";
import CaseMap from "./Map";
import {
  type Case,
  type CaseList,
  type Filters,
  url,
} from "./client";
import { Locale, useWords } from "./locale";
import {
  Busy,
  CaseRow,
  ColumnTitle,
  FilterBar,
  Notice,
  SourceSelect,
  params,
  useLoad,
  type Facets,
  type Insights,
} from "./ui";
export default function Explore({ query }: { query: Filters }) {
  const t = useWords(),
    lang = useContext(Locale),
    source = query.source || "seed";
  const [mobile, setMobile] = useState<"map" | "list">(() =>
    sessionStorage.getItem("mobile-tab") === "list" ? "list" : "map",
  );
  const [layout, setLayout] = useState(
    () => localStorage.getItem("layout") || "map",
  );
  const [selected, select] = useState(""),
    [cluster, setCluster] = useState<string[]>([]),
    [page, setPage] = useState(0);
  const f = useMemo(
      () => ({ ...query, source, locale: lang }),
      [query, source, lang],
    ),
    qs = params(f),
    size = 15;
  useEffect(() => {
    setPage(0);
    select("");
    setCluster([]);
  }, [qs]);
  const stats = useLoad<Insights>("/insights?" + qs),
    facets = useLoad<Facets>("/facets?source=" + source),
    pins = useLoad<CaseList>("/map?" + qs);
  const listQS = cluster.length
    ? params({
        ...f,
        ids: cluster.slice(page * size, (page + 1) * size).join(","),
        limit: String(size),
      })
    : params({ ...f, limit: String(size), offset: String(page * size) });
  const rows = useLoad<CaseList>("/cases?" + listQS),
    chosen = useLoad<Case>(
      selected
        ? "/cases/" +
            encodeURIComponent(selected) +
            "?source=" +
            source +
            "&locale=" +
            lang
        : null,
    );
  const update = (v: Filters) => {
    location.hash = url("explore", v);
  };
  const setTab = (v: "map" | "list") => {
    setMobile(v);
    sessionStorage.setItem("mobile-tab", v);
  };
  const changeLayout = (v: string) => {
    setLayout(v);
    localStorage.setItem("layout", v);
  };
  const num = (n: number | undefined) =>
    n === undefined ? "—" : new Intl.NumberFormat(lang).format(n);
  const total = cluster.length || rows.data?.total || 0;
  return (
    <>
      <div className="page-head">
        <div className="page-intro">
          <h1>{t("explore")}</h1>
          <PageOrientation topic="explore" />
        </div>
        <SourceSelect
          value={source}
          onChange={(s) => {
            if (s === "archive") location.hash = url("search", { source: s });
            else update({ source: s });
          }}
        />
      </div>
      <div className="summary-strip">
        {(
          [
            { k: "cases", v: stats.data?.total, icon: Layers3 },
            { k: "mapped", v: stats.data?.mapped, icon: MapPin },
            { k: "unreviewed", v: stats.data?.unreviewed, icon: PanelRight },
            { k: "highOpen", v: stats.data?.high_open, icon: Triangle },
          ] as const
        ).map(({ k, v, icon: Icon }) => (
          <div key={k} className="metric">
            <span>
              <Icon size={15} />
              {t(k)}
            </span>
            <strong>{num(v)}</strong>
          </div>
        ))}
      </div>
      <FilterBar f={f} set={update} facets={facets.data} />
      <div className="mobile-tabs">
        <button aria-pressed={mobile === "map"} onClick={() => setTab("map")}>
          <MapIcon size={16} />
          {t("map")}
        </button>
        <button aria-pressed={mobile === "list"} onClick={() => setTab("list")}>
          <List size={16} />
          {t("list")}
        </button>
      </div>
      <div
        className={
          "explore-work " +
          (layout === "list" ? "list-led " : "map-led ") +
          "mobile-" +
          mobile
        }
      >
        <section className="map-panel">
          <ColumnTitle title={t("map")}>
            <span className="map-count">
              <i />
              {num(stats.data?.mapped)} {t("mapped")}
            </span>
          </ColumnTitle>
          <div className="map-stack">
            <CaseMap
              items={pins.data?.items}
              selected={selected}
              onSelect={(id) => select(id)}
              onCluster={(ids) => {
                setCluster(ids);
                setPage(0);
                select("");
              }}
              remember
              label={t("map")}
            />
            {chosen.data && (
              <div className="floating-case">
                <button
                  className="close"
                  aria-label={t("clear")}
                  onClick={() => select("")}
                >
                  ×
                </button>
                <CaseRow item={chosen.data} />
              </div>
            )}
          </div>
          <div className="map-foot">
            <span>
              <i className="pin-key" />
              {t("pin")}
            </span>
            <span>
              <i className="cluster-key" />
              {t("group")}
            </span>
            {source === "seed" && <small>{t("simulated")}</small>}
          </div>
          <Notice error={pins.error} retry={pins.retry} />
        </section>
        <section className="results-panel">
          <ColumnTitle title={t("cases")}>
            <span className="muted">
              <ArrowDown size={13} />
              {t("sort")}
            </span>
          </ColumnTitle>
          {cluster.length > 0 && (
            <button
              className="cluster-reset"
              onClick={() => {
                setCluster([]);
                setPage(0);
              }}
            >
              {t("clearCluster")} ({cluster.length})
            </button>
          )}
          <div className="scroll-list">
            <Notice error={rows.error} retry={rows.retry} />
            {rows.busy && <Busy />}
            {rows.data?.items.map((item) => (
              <CaseRow
                key={item.id}
                item={item}
                onSelect={(id) => {
                  select(id);
                  setTab("map");
                }}
                selected={item.id === selected}
              />
            ))}
            {rows.data && !rows.data.items.length && (
              <p className="empty">{t("empty")}</p>
            )}
          </div>
          <div className="pager">
            <span>
              {total
                ? num(page * size + 1) +
                  "–" +
                  num(Math.min(total, (page + 1) * size)) +
                  " / " +
                  num(total)
                : "0"}
            </span>
            <button
              aria-label={t("previous")}
              disabled={!page}
              onClick={() => setPage(page - 1)}
            >
              <ChevronLeft />
            </button>
            <button
              aria-label={t("next")}
              disabled={(page + 1) * size >= total}
              onClick={() => setPage(page + 1)}
            >
              <ChevronRight />
            </button>
          </div>
        </section>
      </div>
      <div className="layout-switch">
        <span>{t("switchLayout")}</span>
        <button
          aria-pressed={layout === "map"}
          onClick={() => changeLayout("map")}
        >
          <PanelRight size={15} />
          {t("mapLed")}
        </button>
        <button
          aria-pressed={layout === "list"}
          onClick={() => changeLayout("list")}
        >
          <PanelLeft size={15} />
          {t("listLed")}
        </button>
      </div>
    </>
  );
}
