import { PageOrientation } from "./PageOrientation";
import { useContext, useEffect, useRef, useState } from "react";
import { Search as SearchIcon } from "lucide-react";
import { type CaseList, type Filters, post, request, upload, url } from "./client";
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
type SearchInput = { text: string; file: File | null; filters: Filters };
type SearchPage = { input: SearchInput; page: number; focusHeading?: boolean };

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
    [active, search] = useState<SearchPage>(() => ({
      input: { text, file: null, filters: {} }, page: 1,
    })),
    uploaded = useRef<{ file: File; id: Promise<string> } | null>(null),
    heading = useRef<HTMLHeadingElement>(null);
  const total = rows?.total ?? 0;
  const last = Math.ceil(total / PAGE_SIZE);
  const number = new Intl.NumberFormat(locale);
  const facets = useLoad<Facets>(
    source === "archive" ? null : "/facets?source=" + source,
  );
  function apply(filters: Filters) {
    search({
      input: { text: text.trim(), file, filters: Object.fromEntries(
        Object.entries(filters).filter(([key, value]) => key !== "source" && value),
      ) },
      page: 1,
    });
  }
  function goTo(page: number) {
    search({ input: active.input, page, focusHeading: true });
  }
  useEffect(() => {
    let current = true;
    const { input, page: targetPage } = active;
    async function refresh() {
      err("");
      if (source === "archive" && !input.text) {
        load(null);
        setBusy(false);
        return;
      }
      setBusy(true);
      try {
        let photo: string | undefined;
        if (input.file) {
          const file = input.file;
          if (uploaded.current?.file !== file) {
            const id = upload(file).catch((error) => {
              if (uploaded.current?.id === id) uploaded.current = null;
              throw error;
            });
            uploaded.current = { file, id };
          }
          photo = await uploaded.current.id;
        }
        if (!current) return;
        const fetchPage = (n: number) => input.text || photo
          ? post<CaseList>("/search", {
              source, locale, text: input.text, photo, filters: input.filters, page: n, limit: PAGE_SIZE,
            })
          : request<CaseList>("/cases?" + new URLSearchParams({
              ...input.filters, source, locale: input.filters.language || locale,
              limit: String(PAGE_SIZE), offset: String((n - 1) * PAGE_SIZE),
            }));
        let result = await fetchPage(targetPage);
        if (!current) return;
        const finalPage = Math.min(targetPage, Math.max(1, Math.ceil(result.total / PAGE_SIZE)));
        if (finalPage !== targetPage) result = await fetchPage(finalPage);
        if (!current) return;
        load(result);
        setPage(finalPage);
        if (active.focusHeading) heading.current?.focus();
      } catch (error) {
        if (current) {
          load(null);
          err((error as Error).message);
        }
      } finally {
        if (current) setBusy(false);
      }
    }
    void refresh();
    return () => { current = false; };
  }, [active, locale, source]);
  const pager = last > 1 && (
    <nav className="search-pager" aria-label={t("resultPages")} aria-busy={busy}>
      <button disabled={busy || page === 1} onClick={() => goTo(page - 1)}>
        {t("previous")}
      </button>
      {pageNumbers(page, last).map((n, index, pages) => (
        <span key={n}>
          {index > 0 && n - pages[index - 1] > 1 && <span aria-hidden="true">…</span>}
          <button
            aria-label={t("page") + " " + number.format(n)}
            aria-current={page === n ? "page" : undefined}
            disabled={busy}
            onClick={() => { if (page !== n) goTo(n); }}
          >
            {number.format(n)}
          </button>
        </span>
      ))}
      <button disabled={busy || page === last} onClick={() => goTo(page + 1)}>
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
          apply(f);
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
            apply(v);
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
