"use client";

import {
  useMemo,
  useState,
} from "react";

import { useLanguage } from "@/components/LanguageProvider";

import {
  analyzePOI,
  type POIResponse,
} from "@/lib/intelligence-api";

export default function POIIntelligence() {
  const { t } = useLanguage();
  const defaultQuestion = t(
    "Analyze POI quality and identify important issues according to GeoSA."
  );

  const [file, setFile] =
    useState<File | null>(null);

  const [question, setQuestion] =
    useState<string | null>(null);

  const [result, setResult] =
    useState<POIResponse | null>(
      null
    );

  const [loading, setLoading] =
    useState(false);

  const quality =
    result?.tool_results
      .poi_quality;

  const categories =
    useMemo(
      () =>
        Object.entries(
          quality
            ?.category_distribution ??
            result?.tool_results
              .poi_summary
              ?.categories ??
            {}
        ).slice(0, 8),
      [quality, result]
    );

  async function run() {
    if (!file) return;

    setLoading(true);

    try {
      setResult(
        await analyzePOI(
          file,
          question ?? defaultQuestion
        )
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <section className="rounded-3xl border border-[#dfe8e3] bg-white p-6 shadow-sm">
        <p className="text-xs font-bold uppercase tracking-[0.17em] text-[#0b7664]">
          Agentic RAG
        </p>

        <h2 className="mt-1 text-2xl font-extrabold text-[#17332f]">
          POI Intelligence
        </h2>

        <p className="mt-2 text-sm text-slate-500">
          Upload a POI dataset and let the agent select the appropriate analysis tools.
        </p>

        <div className="mt-6 grid gap-4 lg:grid-cols-[1fr_1.6fr_auto]">
          <label className="rounded-2xl border border-dashed border-[#b7d2c8] bg-[#f7fbf9] p-4">
            <span className="block text-xs font-bold text-[#31524b]">
              POI Dataset
            </span>

            <input
              type="file"
              accept=".geojson,.json,.gpkg,.zip"
              className="mt-2 block w-full text-xs"
              onChange={(event) =>
                setFile(
                  event.target
                    .files?.[0] ??
                    null
                )
              }
            />
          </label>

          <textarea
            value={question ?? defaultQuestion}
            onChange={(event) =>
              setQuestion(
                event.target.value
              )
            }
            className="min-h-24 rounded-2xl border border-[#cadbd4] p-4 text-sm outline-none focus:border-[#4e9b89]"
          />

          <button
            type="button"
            disabled={
              !file || loading
            }
            onClick={() =>
              void run()
            }
            className="rounded-2xl bg-[#0b7664] px-6 py-3 text-sm font-bold text-white disabled:opacity-40"
          >
            {loading
              ? "Analyzing..."
              : "Analyze"}
          </button>
        </div>
      </section>

      {result && (
        <>
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Metric
              label="Total POIs"
              value={
                quality?.total_pois ??
                result.tool_results
                  .poi_summary
                  ?.total_pois ??
                0
              }
            />

            <Metric
              label="Affected"
              value={
                quality?.affected_pois ??
                0
              }
            />

            <Metric
              label="Quality Score"
              value={`${
                quality?.quality_score ??
                0
              }%`}
            />

            <Metric
              label="Agent Tools"
              value={
                result.selected_tools
                  .length
              }
            />
          </section>

          <section className="grid gap-5 xl:grid-cols-2">
            <div className="rounded-3xl border border-[#dfe8e3] bg-white p-6 shadow-sm">
              <h3 className="font-bold text-[#17332f]">
                Agent tools
              </h3>

              <div className="mt-4 flex flex-wrap gap-2">
                {result.selected_tools.map(
                  (tool) => (
                    <span
                      key={tool}
                      className="rounded-full bg-[#e4f2ed] px-3 py-1.5 text-xs font-bold text-[#0b7664]"
                    >
                      ✓ {tool}
                    </span>
                  )
                )}
              </div>

              {quality && (
                <div className="mt-6 space-y-3">
                  <IssueBar
                    label="Missing names"
                    value={
                      quality.missing_name_count
                    }
                    max={
                      quality.total_pois
                    }
                  />

                  <IssueBar
                    label="Missing categories"
                    value={
                      quality.missing_category_count
                    }
                    max={
                      quality.total_pois
                    }
                  />

                  <IssueBar
                    label="Invalid coordinates"
                    value={
                      quality.invalid_coordinates_count
                    }
                    max={
                      quality.total_pois
                    }
                  />

                  <IssueBar
                    label="Duplicates"
                    value={
                      quality.duplicate_count
                    }
                    max={
                      quality.total_pois
                    }
                  />
                </div>
              )}
            </div>

            <div className="rounded-3xl border border-[#dfe8e3] bg-white p-6 shadow-sm">
              <h3 className="font-bold text-[#17332f]">
                Category Distribution
              </h3>

              <div className="mt-5 space-y-3">
                {categories.map(
                  ([category, count]) => {
                    const max = Math.max(
                      ...categories.map(
                        (item) =>
                          item[1]
                      ),
                      1
                    );

                    return (
                      <div
                        key={category}
                      >
                        <div className="mb-1 flex justify-between text-xs">
                          <span>
                            {
                              category
                            }
                          </span>

                          <strong>
                            {count}
                          </strong>
                        </div>

                        <div className="h-2 rounded-full bg-[#edf2ef]">
                          <div
                            className="h-2 rounded-full bg-[#4d9b89]"
                            style={{
                              width: `${
                                (count /
                                  max) *
                                100
                              }%`,
                            }}
                          />
                        </div>
                      </div>
                    );
                  }
                )}
              </div>
            </div>
          </section>

          <section className="rounded-3xl border border-[#dfe8e3] bg-white p-6 shadow-sm">
            <p className="text-xs font-bold uppercase tracking-[0.17em] text-[#0b7664]">
              AI Interpretation
            </p>

            <div className="mt-3 whitespace-pre-wrap text-sm leading-7 text-[#344b46]">
              {result.answer}
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function Metric({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <div className="rounded-3xl border border-[#dfe8e3] bg-white p-5 shadow-sm">
      <p className="text-xs text-slate-500">
        {label}
      </p>

      <strong className="mt-2 block text-2xl text-[#17332f]">
        {value}
      </strong>
    </div>
  );
}

function IssueBar({
  label,
  value,
  max,
}: {
  label: string;
  value: number;
  max: number;
}) {
  const percent =
    max > 0
      ? Math.min(
          100,
          (value / max) * 100
        )
      : 0;

  return (
    <div>
      <div className="mb-1 flex justify-between text-xs">
        <span>{label}</span>
        <strong>{value}</strong>
      </div>

      <div className="h-2 rounded-full bg-[#edf2ef]">
        <div
          className="h-2 rounded-full bg-[#d39166]"
          style={{
            width: `${percent}%`,
          }}
        />
      </div>
    </div>
  );
}
