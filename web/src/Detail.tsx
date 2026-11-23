import { PageOrientation } from "./PageOrientation";
import { useContext, useEffect, useRef, useState } from "react";
import { ArrowUpRight, Check } from "lucide-react";
import {
  type Case,
  type CaseList,
  type RoutingOption,
  type Filters,
  ApiError,
  apiBase,
  langs,
  mediaUrl,
  pretty,
  post,
  url,
} from "./client";
import { ServiceRouting, RoutingHistory } from "./ServiceRouting";
import { LanguageSelect, ReportTranslation } from "./ReportTranslation";
import { Locale, useWords } from "./locale";
import {
  Busy,
  Breadcrumb,
  CaseRow,
  DateLabel,
  Field,
  Notice,
  Urgency,
  useLoad,
  type Facets,
} from "./ui";
type Detail = Case & {
  photo_alt?: string;
  original_text?: string;
  original_language?: string;
  suggested_urgency?: string;
  final_urgency?: string | null;
  service_options?: RoutingOption[];
  service_context?: string;
  revision?: number;
  service?: string;
  index_state?: string;
  urgency_evidence?: string;
  location_source?: string;
  original_category?: string;
  suggested_category?: string;
  model_version?: string;
};
type Answer = {
  text: string;
  outcome: string;
  links?: { id: string; url: string; label: string }[];
  citations?: string[];
};
const emptyReview = {
  category: "",
  urgency: "",
  status: "",
  service: "",
  service_context: "",
  feedback: "",
};
type ReviewDraft = { fields: typeof emptyReview; key: string };
function readDraft(storageKey: string): ReviewDraft {
  try {
    const saved = JSON.parse(sessionStorage.getItem(storageKey) || "null");
    if (
      typeof saved?.key === "string" &&
      Object.keys(emptyReview).every(
        (k) => typeof saved.fields?.[k] === "string" || (k === "service_context" && saved.fields?.[k] === undefined),
      )
    )
      return { ...saved, fields: { ...emptyReview, ...saved.fields } };
  } catch {
    /* Start a fresh review if a stored draft is obsolete. */
  }
  return { fields: emptyReview, key: crypto.randomUUID() };
}
export default function DetailView({
  id,
  query,
}: {
  id: string;
  query: Filters;
}) {
  const locale = useContext(Locale),
    t = useWords(),
    [answerLanguage, setAnswerLanguage] = useState(locale),
    details = useLoad<Detail>(
      "/cases/" +
        encodeURIComponent(id) +
        "?source=" +
        encodeURIComponent(query.source || "all") +
        "&locale=" +
        locale,
    );
  const c = details.data;
  const storageKey = "commondesk-review:" + id;
  const [draft, setDraft] = useState(() => readDraft(storageKey)),
    review = draft.fields,
    [reviewed, setReviewed] = useState(false),
    [busy, setBusy] = useState(false),
    [error, err] = useState(""),
    [question, setQuestion] = useState(""),
    [kind, setKind] = useState("status"),
    [answer, show] = useState<Answer | null>(null),
    [related, similar] = useState<CaseList | null>(null);
  const answerVersion = useRef(0);
  const facets = useLoad<Facets>(
    query.source === "archive" ? null : "/facets?source=" + encodeURIComponent(query.source || "all"),
  );
  useEffect(() => {
    if (c && (query.event || query.service)) {
      const target = query.event ? "event-" + query.event : "service-" + query.service;
      const el = document.getElementById(target);
      el?.scrollIntoView({ block: "center" });
      el?.focus();
    }
  }, [c, query.event, query.service]);
  function setReview(fields: typeof emptyReview) {
    const next = { fields, key: crypto.randomUUID() };
    setDraft(next);
    setReviewed(false);
    sessionStorage.setItem(storageKey, JSON.stringify(next));
  }
  async function save() {
    setBusy(true);
    err("");
    try {
      await post("/cases/" + encodeURIComponent(id) + "/review", {
        ...Object.fromEntries(Object.entries(review).filter(([, v]) => v)),
        expected_revision: c?.revision,
        idempotency_key: draft.key,
      });
      sessionStorage.removeItem(storageKey);
      setDraft({ fields: emptyReview, key: crypto.randomUUID() });
      setReviewed(true);
      details.retry();
    } catch (e) {
      if (e instanceof ApiError && (e.status === 409 || (e.status === 422 && review.service))) {
        // A concurrent review or catalog update can invalidate a previously offered service.
        setReview({ ...review, service: "" });
        details.retry();
      }
      err((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function clearAnswer() {
    answerVersion.current += 1;
    show(null);
  }
  async function ask() {
    const version = ++answerVersion.current;
    setBusy(true);
    err("");
    show(null);
    try {
      const reply = await post<Answer>("/answer", {
        case_id: id,
        source: c?.source,
        kind,
        question,
        language: answerLanguage,
      });
      if (version === answerVersion.current) show(reply);
    } catch (e) {
      if (version === answerVersion.current) err((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function relatedCases() {
    setBusy(true);
    err("");
    try {
      similar(
        await post<CaseList>("/search", {
          text: c?.original_text || c?.text,
          source: c?.source,
          filters: {},
          limit: 4,
        }),
      );
    } catch (e) {
      err((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function link(v: string) {
    if (v.startsWith("/api/")) return apiBase + v.slice(4);
    if (v.startsWith("#/") || /^https?:\/\//i.test(v)) return v;
    return undefined;
  }
  if (!c)
    return (
      <>
        <Notice error={details.error} retry={details.retry} />
        {details.busy && <Busy />}
      </>
    );
  const originals = c.original_text || c.text,
    lang = c.original_language || c.language,
    photo = c.photo || c.media_id;
  if (c.source === "archive")
    return (
      <div className="narrow">
        <Breadcrumb to={url("search", { source: "archive" })} word="search" />
        <div className="page-head">
          <div className="page-intro">
            <h1>{t("archiveReference")}</h1>
            <PageOrientation topic="archive" />
          </div>
        </div>
        <section className="sheet">
          <h2>{t("original")}</h2>
          {originals ? (
            <>
              <blockquote lang={lang} dir="auto">{originals}</blockquote>
              {c.evidence_available && (
                <ReportTranslation key={JSON.stringify([c.source, c.id, lang, originals])} item={c} originalLanguage={lang} />
              )}
            </>
          ) : (
            <p role="status">{t("archiveMissing")}</p>
          )}
          <dl className="definition">
            <dt>{t("source")}</dt>
            <dd>{t("archive")}</dd>
            <dt>{t("archiveReference")}</dt>
            <dd>
              <bdi>{c.report_id || id}</bdi>
            </dd>
            <dt>{t("offset")}</dt>
            <dd>{c.source_offset ?? "—"}</dd>
          </dl>
        </section>
      </div>
    );
  return (
    <>
      <Breadcrumb to={url("explore", { source: c.source })} word="explore" />
      {query.receipt && (
        <div role="status" className="receipt">
          <Check size={22} />
          <div>
            <strong>{t("receipt")}</strong>
            <p>{t("receiptHelp")}</p>
          </div>
        </div>
      )}
      <div className="page-head detail-head">
        <div>
          <bdi className="identifier">{id}</bdi>
          <h1>{pretty(c.category) || t("case")}</h1>
          <PageOrientation topic="detail" />
        </div>
        <Urgency level={c.final_urgency || c.urgency} />
      </div>
      <div className="detail-grid">
        <div>
          <section className="sheet">
            <h2>{t("original")}</h2>
            <div className="metadata">
              <span>{langs[lang] || lang}</span>
              <span>{c.created_at && <DateLabel s={c.created_at} />}</span>
            </div>
            <blockquote dir="auto" lang={lang}>
              {originals}
            </blockquote>
            {originals && (
              <ReportTranslation key={JSON.stringify([c.source, c.id, lang, originals])} item={c} originalLanguage={lang} />
            )}
            {photo && (
              <figure>
                <a href={mediaUrl(photo)} target="_blank" rel="noreferrer">
                  <img
                    src={mediaUrl(photo)}
                    alt={c.photo_alt || t("photo") + " · " + id}
                  />
                </a>
                {c.source === "seed" && (
                  <figcaption>{t("sourcePhoto")}</figcaption>
                )}
              </figure>
            )}
            <dl className="definition">
              <dt>{t("source")}</dt>
              <dd>
                {c.source === "seed"
                  ? t("seed")
                  : c.source === "archive"
                    ? t("archive")
                    : t("live")}
              </dd>
              <dt>{t("location")}</dt>
              <dd>
                <bdi>
                  {c.latitude == null
                    ? t("unknown")
                    : c.latitude + ", " + c.longitude}
                </bdi>{" "}
                {pretty(c.district)}
              </dd>
              <dt>{t("status")}</dt>
              <dd>{pretty(c.status)}</dd>
              {(c.index_state || c.index_status) && (
                <>
                  <dt>{t("index")}</dt>
                  <dd>{pretty(c.index_state || c.index_status)}</dd>
                </>
              )}
            </dl>
            {c.source === "seed" && <p className="muted">{t("simulated")}</p>}
          </section>
          <section className="sheet">
            <h2>{t("timeline")}</h2>
            <ol className="timeline">
              {c.events?.map((ev) => (
                <li
                  tabIndex={-1}
                  className={ev.event_id === query.event ? "highlight" : ""}
                  id={"event-" + ev.event_id}
                  key={ev.event_id}
                >
                  <b>{pretty(ev.status || ev.type)}</b>
                  {ev.details?.routing?.purpose === "routing_intent_only" && (
                    <RoutingHistory selected={ev.details.routing.selected} />
                  )}
                  <time>{ev.at && new Date(ev.at).toLocaleString(locale)}</time>
                  <a
                    className="event-ref"
                    href={url("case/" + id, {
                      source: c.source,
                      event: ev.event_id,
                    })}
                  >
                    <bdi>{ev.event_id}</bdi>
                  </a>
                </li>
              ))}
            </ol>
          </section>
          <section className="sheet">
            <h2>{t("similar")}</h2>
            <button data-ui-action="related_search" onClick={relatedCases} disabled={busy}>
              {t("searchCases")}
            </button>
            {related && (
              <div>
                {related.items
                  .filter((x) => x.id !== id)
                  .map((x) => (
                    <CaseRow key={x.id} item={x} />
                  ))}
                {!related.items.some((x) => x.id !== id) && <p>{t("empty")}</p>}
              </div>
            )}
          </section>
        </div>
        <div>
          <section className="sheet">
            <h2>{t("answer")}</h2>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void ask();
              }}
            >
              <Field label={t("category")}>
                <select
                  value={kind}
                  onChange={(e) => {
                    setKind(e.target.value);
                    clearAnswer();
                  }}
                >
                  <option value="status">{t("status")}</option>
                  <option value="guidance">{t("guidance")}</option>
                  <option value="report">{t("reportAnswer")}</option>
                </select>
              </Field>
              <LanguageSelect action="answer_language_select" label={t("answerLanguage")} value={answerLanguage} onChange={value => {
                setAnswerLanguage(value);
                clearAnswer();
              }} />
              <Field label={t("enterQuestion")}>
                <textarea
                  rows={2}
                  value={question}
                  dir="auto"
                  onChange={(e) => {
                    setQuestion(e.target.value);
                    clearAnswer();
                  }}
                />
              </Field>
              <button data-ui-action="answer_submit" disabled={busy}>
                {t("ask")}
                <ArrowUpRight size={15} />
              </button>
            </form>
            {answer && (
              <div className="answer" role="status">
                <p dir="auto">{answer.text}</p>
                {answer.links?.map((a) => (
                  <a key={a.id} href={link(a.url)}>
                    {a.label || a.id}
                    <ArrowUpRight size={14} />
                  </a>
                ))}
              </div>
            )}
          </section>
          {c.source !== "archive" && (
            <section className="sheet">
              <h2>{t("review")}</h2>
              <dl className="definition">
                <dt>{t("proposed")}</dt>
                <dd>{pretty(c.suggested_urgency || c.urgency_suggested)}</dd>
                <dt>{t("final")}</dt>
                <dd>
                  {pretty(c.final_urgency || c.urgency_confirmed) ||
                    t("unreviewed")}
                </dd>
              </dl>
              {c.urgency_evidence && <p>{c.urgency_evidence}</p>}
              {c.proposal?.evidence != null && (
                <p>
                  {Array.isArray(c.proposal.evidence)
                    ? c.proposal.evidence.join(" · ")
                    : String(c.proposal.evidence)}
                </p>
              )}
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void save();
                }}
              >
                {(["category", "urgency", "status"] as const).map((k) => (
                  <Field key={k} label={t(k)}>
                    <select
                      disabled={busy}
                      value={review[k]}
                      onChange={(e) =>
                        setReview({ ...review, [k]: e.target.value, service: k === "status" ? review.service : "" })
                      }
                    >
                      <option value="">{t("choose")}</option>
                      {(k === "urgency"
                        ? ["low", "moderate", "high"]
                        : k === "status"
                          ? ["reported", "assigned", "completed"]
                          : [
                              ...new Set([
                                c.category,
                                "private_plumbing",
                                "private_electrical",
                                "drainage",
                                "footpath",
                                "lighting",
                                "parks",
                                "transit",
                                "waste",
                                "other",
                                "unclassified",
                                ...(facets.data?.category || []),
                              ]),
                            ]
                      )
                        .filter(Boolean)
                        .map((v) => (
                          <option key={v} value={v}>
                            {pretty(v)}
                          </option>
                        ))}
                    </select>
                  </Field>
                ))}
                <ServiceRouting
                  context={review.service_context || c.service_context || "unknown"}
                  options={c.service_options || []}
                  current={c.service || c.selected_service || undefined}
                  selection={review.service}
                  busy={busy}
                  pending={Boolean(review.category || review.urgency || review.service_context)}
                  onContext={v => setReview({ ...review, service_context: v === (c.service_context || "unknown") ? "" : v, service: "" })}
                  onSelect={service => setReview({ ...review, service })}
                />
                <Field label={t("reviewFeedback")}>
                  <select
                    disabled={busy}
                    value={review.feedback}
                    onChange={(e) =>
                      setReview({ ...review, feedback: e.target.value })
                    }
                  >
                    <option value="">{t("choose")}</option>
                    <option value="up">👍</option>
                    <option value="down">👎</option>
                  </select>
                </Field>
                <button data-ui-action="status_update"
                  className="primary"
                  disabled={busy || !Object.values(review).some(Boolean)}
                >
                  {t("save")}
                </button>
                {reviewed && <p role="status">{t("reviewed")}</p>}
              </form>
            </section>
          )}
          <Notice error={error} />
        </div>
      </div>
    </>
  );
}
