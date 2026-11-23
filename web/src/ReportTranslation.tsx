import { useEffect, useState } from "react";
import { ApiError, langs, request, type Case } from "./client";
import { useWords } from "./locale";
import { Field } from "./ui";

type Result = { kind: "stored" | "machine"; text: string; attribution?: "machine" };

export function LanguageSelect({
  label,
  value,
  onChange,
  action,
}: {
  action: "report_language_select" | "answer_language_select";
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <Field label={label}>
      <select
        data-ui-action={action}
        aria-label={label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {Object.entries(langs).map(([code, name]) => (
          <option key={code} value={code}>
            {name}
          </option>
        ))}
      </select>
    </Field>
  );
}

export function ReportTranslation({
  item,
  originalLanguage,
}: {
  item: Case;
  originalLanguage: string;
}) {
  const t = useWords();
  const [target, setTarget] = useState(originalLanguage);
  const [attempt, retry] = useState(0);
  const [reply, setReply] = useState<{ key: string; result?: Result; originalOnly?: boolean } | null>(
    null,
  );
  const stored = Array.isArray(item.translations)
    ? item.translations.find((entry) => entry.language === target)?.text
    : item.translations?.[target];
  const key = JSON.stringify([
    item.source,
    item.id,
    originalLanguage,
    target,
    attempt,
  ]);
  const { id, source } = item;
  useEffect(() => {
    if (target === originalLanguage || stored) return;
    const controller = new AbortController();
    request<Result>("/cases/" + encodeURIComponent(id) + "/translation", {
      method: "POST",
      signal: controller.signal,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source, target_language: target }),
    })
      .then((result) => {
        if (!controller.signal.aborted) setReply({ key, result });
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setReply({ key, originalOnly: error instanceof ApiError && error.status === 422 });
        }
      });
    return () => controller.abort();
  }, [source, id, target, originalLanguage, stored, key]);

  const result: Result | null | undefined = stored
    ? { kind: "stored", text: stored }
    : reply?.key === key
      ? reply.result
      : null;
  return (
    <>
      <LanguageSelect
        action="report_language_select" label={t("reportLanguage")}
        value={target}
        onChange={(value) => {
          setReply(null);
          setTarget(value);
        }}
      />
      {target !== originalLanguage && (
        <div aria-live="polite">
          {result ? (
            <>
              <small>
                {t(
                  result.kind === "stored"
                    ? "storedTranslation"
                    : result.attribution === "machine"
                      ? "ordinaryMachineTranslation"
                      : "machineTranslation",
                )}
              </small>
              <blockquote lang={target} dir="auto">
                {result.text}
              </blockquote>
            </>
          ) : reply?.key === key && reply.originalOnly ? (
            <p>{t("reportOriginalOnly")}</p>
          ) : reply?.key === key ? (
            <p>
              {t("translationUnavailable")}{" "}
              <button data-ui-action="translation_retry" type="button" onClick={() => retry(attempt + 1)}>
                {t("retry")}
              </button>
            </p>
          ) : (
            <p>{t("loading")}</p>
          )}
        </div>
      )}
    </>
  );
}
