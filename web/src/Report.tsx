import { useContext, useState } from "react";
import {
  ArrowRight,
  Check,
  LocateFixed,
  MapPin,
  Paperclip,
} from "lucide-react";
import CaseMap from "./Map";
import {
  ApiError,
  type Case,
  type Coordinate,
  langs,
  post,
  pretty,
  upload,
  url,
} from "./client";
import { Locale, useWords } from "./locale";
import { Breadcrumb, Field, Notice } from "./ui";
type Draft = {
  text: string;
  language: string;
  intent: string;
  photo: string;
  point: Coordinate | null;
  clarification: string;
  key: string;
};
type Proposal = {
  proposal_digest?: string;
  interpretation: string;
  category: string;
  urgency: string;
  intent: string;
  evidence: string | string[];
  question: string | null;
  version: string;
};
function draft(lang: string): Draft {
  try {
    const v = JSON.parse(sessionStorage.getItem("commondesk-draft") || "null");
    if (v?.key) return v;
  } catch {
    /* ignore old draft */
  }
  return {
    text: "",
    language: lang,
    intent: "",
    photo: "",
    point: null,
    clarification: "",
    key: crypto.randomUUID(),
  };
}
export default function Report() {
  const lang = useContext(Locale),
    t = useWords(),
    [d, set] = useState(() => draft(lang)),
    [proposal, setProposal] = useState<Proposal | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [file, setFile] = useState<File | null>(null);
  const [lat, setLat] = useState(String(d.point?.latitude ?? "")),
    [lon, setLon] = useState(String(d.point?.longitude ?? ""));
  function change(v: Partial<Draft>) {
    const next = { ...d, ...v };
    set(next);
    sessionStorage.setItem("commondesk-draft", JSON.stringify(next));
  }
  function point(p: Coordinate | null) {
    change({ point: p });
    setLat(p ? String(p.latitude) : "");
    setLon(p ? String(p.longitude) : "");
    setError("");
  }
  function typedPoint(): Coordinate | null {
    if (!lat.trim() && !lon.trim()) return null;
    const a = Number(lat),
      b = Number(lon);
    if (
      !lat.trim() ||
      !lon.trim() ||
      !Number.isFinite(a) ||
      Math.abs(a) > 90 ||
      !Number.isFinite(b) ||
      Math.abs(b) > 180
    )
      throw Error(t("geoInvalid"));
    return d.point?.latitude === a && d.point.longitude === b
      ? d.point
      : { latitude: a, longitude: b, location_source: "manual" };
  }
  function locate() {
    if (!navigator.geolocation) {
      setError(t("locDenied"));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (p) =>
        point({
          latitude: +p.coords.latitude.toFixed(6),
          longitude: +p.coords.longitude.toFixed(6),
          accuracy: p.coords.accuracy,
          location_source: "device",
        }),
      () => setError(t("locDenied")),
      { timeout: 10000 },
    );
  }
  async function prepare(notice = "") {
    setBusy(true);
    setError("");
    try {
      const p = typedPoint();
      const photo = file ? await upload(file) : d.photo;
      change({ photo, point: p });
      setFile(null);
      const result = await post<Proposal>("/proposal", {
        text: d.text,
        language: d.language,
        intent: d.intent || undefined,
        photo: photo || null,
        ...p,
        clarification: d.clarification || null,
      });
      setProposal(result);
      setError(notice);
      window.scrollTo(0, 0);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function submit(manual: boolean) {
    setBusy(true);
    setError("");
    try {
      const created = await post<Case>("/cases", {
        text: d.text,
        intent: d.intent || undefined,
        language: d.language,
        photo: d.photo || null,
        ...d.point,
        clarification: d.clarification || null,
        manual_review: manual,
        proposal_digest: proposal?.proposal_digest,
        idempotency_key: d.key,
      });
      if (!created.id)
        throw Error(
          "The service did not return a case number. Retry with this draft.",
        );
      sessionStorage.removeItem("commondesk-draft");
      location.hash = url("case/" + encodeURIComponent(created.id), {
        source: "live",
        receipt: "1",
      });
    } catch (e) {
      if (
        e instanceof ApiError &&
        e.status === 409 &&
        e.message.startsWith("Assessment changed.")
      ) {
        await prepare(e.message);
      } else {
        setError((e as Error).message);
      }
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="narrow">
      <Breadcrumb to="#/explore" word="explore" />
      <div className="page-head">
        <h1>{proposal ? t("continue") : t("newReport")}</h1>
      </div>
      <Notice error={error} />
      {!proposal ? (
        <form
          className="form-sheet"
          onSubmit={(e) => {
            e.preventDefault();
            void prepare();
          }}
        >
          <div className="form-line">
            <Field label={t("intent")}>
              <select
                value={d.intent}
                onChange={(e) => change({ intent: e.target.value })}
              >
                <option value="">{t("infer")}</option>
                {(["complaint", "suggestion", "feedback"] as const).map((i) => (
                  <option key={i} value={i}>
                    {t(i)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={t("originalLanguage")}>
              <select
                value={d.language}
                onChange={(e) => change({ language: e.target.value })}
              >
                {Object.entries(langs).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <Field label={t("describe")}>
            <textarea
              required
              minLength={1}
              maxLength={6000}
              rows={5}
              dir="auto"
              lang={d.language}
              value={d.text}
              onChange={(e) => change({ text: e.target.value })}
            />
          </Field>
          <Field label={t("addPhoto") + " · " + t("optional")}>
            <input
              type="file"
              accept="image/png,image/jpeg,image/webp"
              onChange={(e) => {
                setFile(e.target.files?.[0] || null);
                change({ photo: "" });
              }}
            />
          </Field>
          {d.photo && (
            <p>
              <Paperclip size={15} />
              {t("photo")}{" "}
              <button type="button" onClick={() => change({ photo: "" })}>
                {t("clear")}
              </button>
            </p>
          )}
          <fieldset className="location-box">
            <legend>
              <MapPin size={18} />
              {t("location")} · {t("optional")}
            </legend>
            <p>{t("locationHelp")}</p>
            <CaseMap
              editable
              point={d.point}
              onPoint={point}
              label={t("place")}
            />
            <div className="form-line">
              <Field label={t("latitude")}>
                <input
                  inputMode="decimal"
                  value={lat}
                  onChange={(e) => setLat(e.target.value)}
                />
              </Field>
              <Field label={t("longitude")}>
                <input
                  inputMode="decimal"
                  value={lon}
                  onChange={(e) => setLon(e.target.value)}
                />
              </Field>
            </div>
            <div className="actions">
              <button
                type="button"
                onClick={() => {
                  try {
                    point(typedPoint());
                  } catch (e) {
                    setError((e as Error).message);
                  }
                }}
              >
                {t("setPin")}
              </button>
              <button type="button" onClick={locate}>
                <LocateFixed size={16} />
                {t("locate")}
              </button>
              <button
                className="text-btn"
                type="button"
                onClick={() => point(null)}
              >
                {t("clearPin")}
              </button>
            </div>
          </fieldset>
          <button className="primary" disabled={busy || !d.text.trim()}>
            {busy ? t("loading") : t("continue")}
            <ArrowRight size={17} />
          </button>
        </form>
      ) : (
        <div className="form-sheet">
          <h2>{t("original")}</h2>
          <blockquote dir="auto">{d.text}</blockquote>
          <dl className="definition">
            <dt>{t("intent")}</dt>
            <dd>{pretty(proposal.intent)}</dd>
            <dt>{t("category")}</dt>
            <dd>{pretty(proposal.category)}</dd>
            <dt>{t("urgency")}</dt>
            <dd>{pretty(proposal.urgency)}</dd>
          </dl>
          <p dir="auto">{proposal.interpretation}</p>
          {proposal.evidence && (
            <p className="evidence">
              {Array.isArray(proposal.evidence)
                ? proposal.evidence.join(" · ")
                : proposal.evidence}
            </p>
          )}
          {proposal.question && (
            <Field label={proposal.question}>
              <input
                dir="auto"
                value={d.clarification}
                onChange={(e) => change({ clarification: e.target.value })}
              />
            </Field>
          )}
          {d.point && (
            <p>
              <MapPin size={15} /> {d.point.latitude}, {d.point.longitude}
            </p>
          )}
          <div className="actions">
            <button
              className="primary"
              disabled={
                busy || (!!proposal.question && !d.clarification.trim())
              }
              onClick={() => (proposal.question ? prepare() : submit(false))}
            >
              <Check size={17} />
              {busy
                ? t("sending")
                : proposal.question
                  ? t("continue")
                  : t("confirm")}
            </button>
            <button disabled={busy} onClick={() => setProposal(null)}>
              {t("edit")}
            </button>
            <button disabled={busy} onClick={() => submit(true)}>
              {t("manual")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
