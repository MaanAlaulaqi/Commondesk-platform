import { CircleHelp } from "lucide-react";
import { useContext, useEffect, useId, useRef, useState } from "react";
import { Locale } from "./locale";
import { orientation, type Topic } from "./orientation-copy";

export function PageOrientation({ topic }: { topic: Topic }) {
  const lang = useContext(Locale);
  const [summary, label, explanation] = (orientation[lang] || orientation.en)[
    topic
  ];
  const [mode, setMode] = useState<"closed" | "preview" | "pinned">("closed");
  const box = useRef<HTMLDivElement>(null);
  const id = useId();
  const open = mode !== "closed";

  useEffect(() => {
    if (!open) return;
    function outside(event: PointerEvent) {
      if (!box.current?.contains(event.target as Node)) setMode("closed");
    }
    function escape(event: KeyboardEvent) {
      if (event.key === "Escape") setMode("closed");
    }
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  return (
    <>
      <p className="page-summary">{summary}</p>
      <div
        ref={box}
        className="page-help"
        onBlur={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget))
            setMode("closed");
        }}
        onPointerLeave={() => {
          if (!box.current?.contains(document.activeElement)) {
            setMode((current) => (current === "preview" ? "closed" : current));
          }
        }}
      >
        <button data-ui-action="help_open"
          type="button"
          className="help-trigger"
          aria-expanded={open}
          aria-controls={id}
          aria-describedby={open ? id : undefined}
          onPointerEnter={(event) => {
            if (event.pointerType === "mouse")
              setMode((current) =>
                current === "closed" ? "preview" : current,
              );
          }}
          onFocus={() =>
            setMode((current) => (current === "closed" ? "preview" : current))
          }
          onClick={(event) => {
            setMode((current) =>
              current === "pinned" ||
              (event.detail === 0 && current === "preview")
                ? "closed"
                : "pinned",
            );
          }}
        >
          <CircleHelp size={16} aria-hidden="true" />
          {label}
        </button>
        <p id={id} className="help-content" hidden={!open}>
          {explanation}
        </p>
      </div>
    </>
  );
}
