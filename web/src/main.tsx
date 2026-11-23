import { useEffect, useLayoutEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ChartNoAxesColumn,
  Compass,
  Languages,
  Plus,
  Search as Magnify,
  SunMoon,
} from "lucide-react";
import "@fontsource/barlow/400.css";
import "@fontsource/barlow/500.css";
import "@fontsource/barlow/600.css";
import "@fontsource/barlow/700.css";
import "@fontsource/barlow-condensed/700.css";
import "@fontsource/barlow-condensed/800.css";
import "./style.css";
import { Locale, useWords } from "./locale";
import { langs, route } from "./client";
import { listenForClicks } from "./uiEvents";
import Explore from "./Explore";
import Report from "./Report";
import Search from "./Search";
import Insights from "./Insights";
import Detail from "./Detail";
function App() {
  const [r, setRoute] = useState(route),
    [lang, setLang] = useState(() => localStorage.getItem("language") || "en"),
    [theme, setTheme] = useState(
      () => localStorage.getItem("theme") || "system",
    );
  useEffect(() => {
    const sync = () => {
      setRoute(route());
      if (!route().params.event && !route().params.service) window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, []);
  useLayoutEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = ["ar", "ur"].includes(lang) ? "rtl" : "ltr";
    localStorage.setItem("language", lang);
  }, [lang]);
  useEffect(() => {
    const media = matchMedia("(prefers-color-scheme: dark)");
    const apply = () =>
      (document.documentElement.dataset.theme =
        theme === "system" ? (media.matches ? "dark" : "light") : theme);
    apply();
    media.addEventListener("change", apply);
    localStorage.setItem("theme", theme);
    return () => media.removeEventListener("change", apply);
  }, [theme]);
  return (
    <Locale.Provider value={lang}>
      <Shell
        r={r}
        lang={lang}
        theme={theme}
        setLang={(value) => {
          document.documentElement.lang = value;
          setLang(value);
        }}
        setTheme={setTheme}
      />
    </Locale.Provider>
  );
}
function Shell({
  r,
  lang,
  theme,
  setLang,
  setTheme,
}: {
  r: ReturnType<typeof route>;
  lang: string;
  theme: string;
  setLang: (s: string) => void;
  setTheme: (s: string) => void;
}) {
  const t = useWords(),
    page = r.page.split("/")[0],
    detail = page === "case" || page === "cases";
  useEffect(() => {
    document.title =
      (detail
        ? t("case")
        : page === "report"
          ? t("newReport")
          : page === "search"
            ? t("search")
            : page === "insights"
              ? t("insights")
              : t("explore")) + " · CommonDesk";
  }, [page, lang, detail, t]);
  return (
    <>
      <a
        className="skip"
        href="#main-content"
        onClick={(e) => {
          e.preventDefault();
          document.getElementById("main-content")?.focus();
        }}
      >
        {t("skip")}
      </a>
      <header className="topbar">
        <div className="top-inner">
          <a data-ui-action="explore_open" className="wordmark" href="#/explore" dir="ltr">
            <span className="brand-mark" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
            CommonDesk
          </a>
          <nav aria-label={t("nav")}>
            {(
              [
                { key: "explore", Icon: Compass },
                { key: "search", Icon: Magnify },
                { key: "insights", Icon: ChartNoAxesColumn },
              ] as const
            ).map(({ key, Icon }) => (
              <a
                data-ui-action={key + "_open"}
                href={"#/" + key}
                key={key}
                aria-current={page === key ? "page" : undefined}
              >
                <Icon size={16} />
                {t(key)}
              </a>
            ))}
          </nav>
          <div className="header-settings">
            <label title={t("language")}>
              <Languages size={18} />
              <select
                data-ui-action="interface_language"
                aria-label={t("language")}
                value={lang}
                onChange={(e) => setLang(e.target.value)}
              >
                {Object.entries(langs).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
              <span>{lang.toUpperCase()}</span>
            </label>
            <label title={t("theme")}>
              <SunMoon size={18} />
              <select
                data-ui-action="theme_change"
                aria-label={t("theme")}
                value={theme}
                onChange={(e) => setTheme(e.target.value)}
              >
                {(["system", "light", "dark"] as const).map((v) => (
                  <option value={v} key={v}>
                    {t(v)}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <a data-ui-action="report_open" href="#/report" className="primary report-action">
            <Plus size={17} />
            {t("newReport")}
          </a>
        </div>
      </header>
      <main id="main-content" tabIndex={-1}>
        {detail ? (
          <Detail
            key={r.page}
            id={decodeURIComponent(r.page.slice(r.page.indexOf("/") + 1))}
            query={r.params}
          />
        ) : page === "report" ? (
          <Report />
        ) : page === "search" ? (
          <Search key={r.params.source} query={r.params} />
        ) : page === "insights" ? (
          <Insights query={r.params} />
        ) : (
          <Explore query={r.params} />
        )}
      </main>
    </>
  );
}
const root = document.getElementById("root")!;
listenForClicks(root);
createRoot(root).render(<App />);
