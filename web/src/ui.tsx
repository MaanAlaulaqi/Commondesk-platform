import { useEffect, useState, type ReactNode } from "react";
import {
  AlertTriangle,
  ArrowUpRight,
  ChevronRight,
  ChevronDown,
  Clock3,
  MapPin,
  Image as Photo,
  SlidersHorizontal,
  LoaderCircle,
  Minus,
  Circle,
  Triangle,
} from "lucide-react";
import {
  caseUrl,
  langs,
  mediaUrl,
  pretty,
  request,
  type Case,
  type Filters,
} from "./client";
import { useWords, type Word } from "./locale";
export function useLoad<T>(path: string | null) {
  const [state, set] = useState<{ data?: T; error?: string; busy: boolean }>({
      busy: true,
    }),
    [tick, retry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    set({ busy: !!path });
    if (path)
      request<T>(path, { signal: controller.signal })
        .then((data) => set({ data, busy: false }))
        .catch((e) => {
          if (!controller.signal.aborted)
            set({ error: e.message, busy: false });
        });
    return () => controller.abort();
  }, [path, tick]);
  return { ...state, retry: () => retry((v) => v + 1) };
}
export function Notice({
  error,
  retry,
}: {
  error?: string;
  retry?: () => void;
}) {
  const t = useWords();
  return error ? (
    <div className="notice error" role="alert">
      <AlertTriangle size={17} />
      <span>{error}</span>
      {retry && <button data-ui-action="control_retry" onClick={retry}>{t("retry")}</button>}
    </div>
  ) : null;
}
export function Busy() {
  const t = useWords();
  return (
    <div className="busy" role="status">
      <LoaderCircle size={18} />
      {t("loading")}
    </div>
  );
}
export function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}
export function DateLabel({ s }: { s: string }) {
  const parsed = new Date(s);
  return (
    <time dateTime={s}>
      {Number.isNaN(+parsed)
        ? s
        : parsed.toLocaleDateString(document.documentElement.lang, {
            month: "short",
            day: "numeric",
            year: "numeric",
            timeZone: "Asia/Dubai",
          })}
    </time>
  );
}
export function SourceSelect({
  value,
  onChange,
  archive = true,
}: {
  value: string;
  onChange: (v: string) => void;
  archive?: boolean;
}) {
  const t = useWords();
  return (
    <label className="source-choice">
      <span>{t("source")}</span>
      <select
        data-ui-action="source_select"
        aria-label={t("source")}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="seed">{t("seed")}</option>
        <option value="live">{t("live")}</option>
        {archive && <option value="archive">{t("archive")}</option>}
      </select>
      <ChevronDown size={15} />
    </label>
  );
}
export type Insights = {
  total: number;
  mapped: number;
  unreviewed: number;
  high_open: number;
  categories: { label: string; count: number }[];
  weeks: { label: string; count: number }[];
  urgencies: { label: string; count: number }[];
};
export type Facets = Record<string, string[]>;
export function FilterBar({
  f,
  set,
  facets,
}: {
  f: Filters;
  set: (f: Filters) => void;
  facets?: Facets;
}) {
  const t = useWords();
  const [advanced, show] = useState(false);
  const active = [
    "category",
    "district",
    "language",
    "status",
    "urgency",
    "date_from",
    "date_to",
  ].filter((k) => f[k]);
  return (
    <div className="filterbar">
      <div className="filterrow">
        <button
          data-ui-action="filter_apply"
          className={"filterbtn " + (advanced ? "on" : "")}
          aria-expanded={advanced}
          onClick={() => show(!advanced)}
        >
          <SlidersHorizontal size={16} />
          {t("filters")}
          {active.length > 0 && <b>{active.length}</b>}
        </button>
        {(["district", "category", "urgency"] as const).map((k) => (
          <label key={k} className="compact-select">
            <span className="sr-only">{t(k)}</span>
            <select
              aria-label={t(k)}
              data-ui-action="filter_apply" value={f[k] || ""}
              onChange={(e) => set({ ...f, [k]: e.target.value })}
            >
              <option value="">{t(k)}</option>
              {(facets?.[k] || []).map((v) => (
                <option key={v} value={v}>
                  {pretty(v)}
                </option>
              ))}
            </select>
            <ChevronDown size={13} />
          </label>
        ))}
        {active.length > 0 && (
          <button
            className="text-btn"
            data-ui-action="filter_apply" onClick={() => set({ source: f.source })}
          >
            {t("clear")}
          </button>
        )}
      </div>
      {advanced && (
        <div className="filterdrawer">
          {(["status", "language"] as const).map((k) => (
            <Field key={k} label={t(k)}>
              <select
                data-ui-action="filter_apply" value={f[k] || ""}
                onChange={(e) => set({ ...f, [k]: e.target.value })}
              >
                <option value="">{t("all")}</option>
                {(k === "language"
                  ? Object.keys(langs)
                  : facets?.[k] || []
                ).map((v) => (
                  <option key={v} value={v}>
                    {k === "language" ? langs[v] : pretty(v)}
                  </option>
                ))}
              </select>
            </Field>
          ))}
          {(["date_from", "date_to"] as const).map((k) => (
            <Field label={t(k)} key={k}>
              <input
                type="date"
                data-ui-action="filter_apply" value={f[k] || ""}
                onChange={(e) => set({ ...f, [k]: e.target.value })}
              />
            </Field>
          ))}
        </div>
      )}
    </div>
  );
}
export function Urgency({ level }: { level?: string | null }) {
  const t = useWords(),
    s = level || "unreviewed";
  const Icon =
    s === "high"
      ? Triangle
      : s === "low"
        ? Minus
        : s === "unreviewed"
          ? Clock3
          : Circle;
  return (
    <span className={"urgency level-" + s}>
      <Icon size={12} strokeWidth={2.5} />
      {s === "unreviewed" ? t("unreviewed") : pretty(s)}
    </span>
  );
}
export function CaseRow({
  item,
  onSelect,
  selected,
}: {
  item: Case;
  onSelect?: (id: string) => void;
  selected?: boolean;
}) {
  const t = useWords();
  if (item.source === "archive")
    return (
      <article className="case-row archive-row">
        <span className="identifier">{t("archive")}</span>
        <h3>
          <a data-ui-action="case_open" href={caseUrl(item)}>
            <bdi>{item.report_id || item.id}</bdi>
          </a>
        </h3>
        <p dir="auto">{item.text || t("archiveMissing")}</p>
        <div className="row-foot">
          <span>
            {t("offset")} <bdi>{item.source_offset ?? "—"}</bdi>
          </span>
          <a data-ui-action="case_open" href={caseUrl(item)} aria-label={t("open") + " " + item.id}>
            <ArrowUpRight size={17} />
          </a>
        </div>
      </article>
    );
  return (
    <article className={"case-row " + (selected ? "selected" : "")}>
      <div className="row-top">
        <bdi className="identifier">{item.id}</bdi>
        <Urgency level={item.urgency} />
      </div>
      <div className="row-body">
        {(item.photo || item.media_id) && (
          <a
            data-ui-action="case_open" href={caseUrl(item)}
            className="case-thumb"
            aria-label={"Open photo case " + item.id}
          >
            <img
              loading="lazy"
              alt=""
              src={mediaUrl((item.photo || item.media_id)!)}
            />
          </a>
        )}
        {onSelect && item.latitude != null ? (
          <button data-ui-action="case_open" className="case-title" onClick={() => onSelect(item.id)}>
            {pretty(item.category) || item.id}
          </button>
        ) : (
          <a className="case-title" data-ui-action="case_open" href={caseUrl(item)}>
            {pretty(item.category) || item.id}
          </a>
        )}
        <p dir="auto" lang={item.language}>
          {item.text}
        </p>
      </div>
      <div className="row-foot">
        <span>
          <MapPin size={13} />
          {pretty(item.district) || "—"}
        </span>
        {(item.photo || item.media_id) && <Photo size={14} />}
        <a data-ui-action="case_open" href={caseUrl(item)} aria-label={"Open case " + item.id}>
          <ArrowUpRight size={17} />
        </a>
      </div>
    </article>
  );
}
export function ColumnTitle({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="column-title">
      <h2>{title}</h2>
      {children}
    </div>
  );
}
export function Breadcrumb({ to, word }: { to: string; word: Word }) {
  const t = useWords();
  return (
    <a href={to} className="crumb">
      <ChevronRight size={15} />
      {t(word)}
    </a>
  );
}
export function params(f: Filters) {
  return new URLSearchParams(Object.entries(f).filter(([, v]) => v)).toString();
}
