import { PageOrientation } from "./PageOrientation";
import { useContext, useRef, useState } from "react";
import { Search as SearchIcon } from "lucide-react";
import { type CaseList, type Filters, post, upload, url } from "./client";
import { Locale, useWords } from "./locale";
import {
  Busy,
  CaseRow,
  Field,
  FilterBar,
  Notice,
  SourceSelect,
  useLoad,
  type Facets,
} from "./ui";
const PAGE_SIZE = 50;
type SubmittedSearch = { text: string; photo?: string; source: string; filters: Filters };

// Keep both ends and the current neighborhood reachable even for the historical archive.
function pageNumbers(page: number, last: number) {
  const pages = new Set([1, last]);
  for (let i = Math.max(1, Math.min(page - 2, last - 4)); i <= Math.min(last, Math.max(5, page + 2)); i++) {
    pages.add(i);
  }
  return Array.from(pages).sort((a, b) => a - b);
}

export default function Search({ query }: { query: Filters }) {
  const [text, setText] = useState("");
  const source = query.source || "seed";
  return (
    <SearchForm key={source} source={source} text={text} setText={setText} />
  );
}

function SearchForm({
  source,
  text,
  setText,
}: {
  source: string;
  text: string;
  setText: (text: string) => void;
}) {
  const t = useWords(),
    locale = useContext(Locale),
    [file, setFile] = useState<File | null>(null),
    [f, set] = useState<Filters>({ source }),
    [rows, load] = useState<CaseList | null>(null),
    [busy, setBusy] = useState(false),
    [error, err] = useState(""),
    [page, setPage] = useState(1),
    [submitted, setSubmitted] = useState<SubmittedSearch | null>(null),
    generation = useRef(0),
    heading = useRef<HTMLHeadingElement>(null);
  const total = rows?.total ?? 0;
  const last = Math.ceil(total / PAGE_SIZE);
  const number = new Intl.NumberFormat(locale);
  const facets = useLoad<Facets>(
    f.source === "archive" ? null : "/facets?source=" + f.source,
  );
  function resetResults() {
    generation.current++;
    load(null);
    setSubmitted(null);
    setPage(1);
    setBusy(false);
    err("");
  }
  async function run(nextPage = 1, previous?: SubmittedSearch) {
    const version = ++generation.current;
    setBusy(true);
    err("");
    if (!previous) {
      load(null);
      setSubmitted(null);
    }
    try {
      const query = previous ?? {
        text,
        photo: file ? await upload(file) : undefined,
        source: f.source,
        filters: Object.fromEntries(Object.entries(f).filter(([key]) => key !== "source")),
      };
      if (version !== generation.current) return;
      const fetchPage = (n: number) => post<CaseList>("/search", {
        ...query, locale, page: n, limit: PAGE_SIZE,
      });
      let result = await fetchPage(nextPage);
      if (version !== generation.current) return;
      const finalPage = Math.max(1, Math.ceil(result.total / PAGE_SIZE));
      if (nextPage > finalPage) {
        nextPage = finalPage;
        result = await fetchPage(nextPage);
      }
      if (version !== generation.current) return;
      load(result);
      setSubmitted(query);
      setPage(nextPage);
      if (previous) requestAnimationFrame(() => heading.current?.focus());
    } catch (e) {
      if (version === generation.current) err((e as Error).message);
    } finally {
      if (version === generation.current) setBusy(false);
    }
  }
  const pager = submitted && last > 1 && (
    <nav className="search-pager" aria-label={t("resultPages")} aria-busy={busy}>
      <button disabled={busy || page === 1} onClick={() => void run(page - 1, submitted)}>
        {t("previous")}
      </button>
      {pageNumbers(page, last).map((n, index, pages) => (
        <span key={n}>
          {index > 0 && n - pages[index - 1] > 1 && <span aria-hidden="true">…</span>}
          <button
            aria-label={t("page") + " " + number.format(n)}
            aria-current={page === n ? "page" : undefined}
            disabled={busy}
            onClick={() => { if (page !== n) void run(n, submitted); }}
          >
            {number.format(n)}
          </button>
        </span>
      ))}
      <button disabled={busy || page === last} onClick={() => void run(page + 1, submitted)}>
        {t("next")}
      </button>
    </nav>
  );
  return (
    <>
      <div className="page-head">
        <div className="page-intro">
          <h1>{t("search")}</h1>
          <PageOrientation topic="search" />
        </div>
        <SourceSelect
          value={f.source}
          onChange={(s) => {
            location.hash = url("search", { source: s });
          }}
        />
      </div>
      <form
        className="search-form"
        onSubmit={(e) => {
          e.preventDefault();
          void run();
        }}
      >
        <Field label={t("searchHint")}>
          <input
            type="search"
            dir="auto"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </Field>
        <div className="search-actions">
          {f.source !== "archive" && (
            <Field label={t("reference") + " · " + t("optional")}>
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
            </Field>
          )}
          <button data-ui-action="search_submit"
            className="primary"
            disabled={busy || (!text.trim() && !file)}
          >
            <SearchIcon size={17} />
            {t("searchCases")}
          </button>
        </div>
      </form>
      {f.source !== "archive" && (
        <FilterBar
          f={f}
          set={(v) => {
            set(v);
            resetResults();
          }}
          facets={facets.data}
        />
      )}
      <Notice error={error} />
      {busy && <Busy />}
      {rows && (
        <>
          <h2 className="section-heading" ref={heading} tabIndex={-1}>
            {t("results")} <small>{number.format(total)}</small>
          </h2>
          {rows.items.length > 0 && (
            <p className="search-range" aria-live="polite">
              {number.format((page - 1) * PAGE_SIZE + 1)}–{number.format((page - 1) * PAGE_SIZE + rows.items.length)} / {number.format(total)}
            </p>
          )}
          {pager}
          {rows.items.length ? (
            <div className="search-grid">
              {rows.items.map((c) => (
                <CaseRow item={c} key={c.id} />
              ))}
            </div>
          ) : (
            <p>{t("empty")}</p>
          )}
          {pager}
        </>
      )}
    </>
  );
}
