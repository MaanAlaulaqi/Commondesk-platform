import { type Filters, pretty, url } from "./client";
import { useWords } from "./locale";
import {
  Busy,
  FilterBar,
  Notice,
  SourceSelect,
  params,
  useLoad,
  type Facets,
  type Insights as Data,
} from "./ui";
export default function Insights({ query }: { query: Filters }) {
  const t = useWords(),
    f = { ...query, source: query.source || "seed" },
    stats = useLoad<Data>("/insights?" + params(f)),
    facets = useLoad<Facets>("/facets?source=" + f.source);
  const update = (v: Filters) => {
    location.hash = url("insights", v);
  };
  function drill(key: string, label: string) {
    const v: Filters = { ...f, [key]: label };
    if (key === "date_from") {
      const d = new Date(label + "T12:00:00Z");
      d.setUTCDate(d.getUTCDate() + 6);
      v.date_to = d.toISOString().slice(0, 10);
    }
    return url("explore", v);
  }
  const data = stats.data;
  return (
    <>
      <div className="page-head">
        <h1>{t("insights")}</h1>
        <SourceSelect
          value={f.source}
          onChange={(s) => update({ source: s })}
          archive={false}
        />
      </div>
      <FilterBar f={f} set={update} facets={facets.data} />
      <Notice error={stats.error} retry={stats.retry} />
      {stats.busy && <Busy />}
      {data && (
        <>
          <div className="denominator">
            <strong>{data.total.toLocaleString()}</strong> {t("count")}{" "}
            <span>
              {data.mapped.toLocaleString()} {t("mapped")}
            </span>
          </div>
          <div className="chart-grid">
            {(
              [
                { key: "categories", filter: "category", title: "categories" },
                { key: "weeks", filter: "date_from", title: "weeks" },
                { key: "urgencies", filter: "urgency", title: "urgencies" },
              ] as const
            ).map((spec) => (
              <section className={"chart " + spec.key} key={spec.key}>
                <h2>{t(spec.title)}</h2>
                {data[spec.key].length === 0 ? (
                  <p>{t("empty")}</p>
                ) : (
                  data[spec.key].map((r) => (
                    <a
                      href={drill(spec.filter, r.label)}
                      key={r.label}
                      className="chart-entry"
                    >
                      <span>{pretty(r.label)}</span>
                      <i
                        style={{
                          width:
                            (100 * r.count) /
                              Math.max(
                                1,
                                ...data[spec.key].map((x) => x.count),
                              ) +
                            "%",
                        }}
                      />
                      <b>{r.count.toLocaleString()}</b>
                    </a>
                  ))
                )}
              </section>
            ))}
          </div>
        </>
      )}
    </>
  );
}
