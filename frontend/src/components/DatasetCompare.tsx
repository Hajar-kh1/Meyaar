"use client";

import {
  useMemo,
  useState,
} from "react";

import {
  compareDatasets,
  type DatasetCompareResponse,
} from "@/lib/intelligence-api";

export default function DatasetCompare() {
  const [fileA, setFileA] =
    useState<File | null>(null);

  const [fileB, setFileB] =
    useState<File | null>(null);

  const [result, setResult] =
    useState<DatasetCompareResponse | null>(
      null
    );

  const [loading, setLoading] =
    useState(false);

  async function run() {
    if (!fileA || !fileB) return;

    setLoading(true);

    try {
      setResult(
        await compareDatasets(
          fileA,
          fileB
        )
      );
    } finally {
      setLoading(false);
    }
  }

  const issues = useMemo(() => {
    if (!result) return [];

    const keys = new Set([
      ...Object.keys(
        result.quality.dataset_a
          .issues
      ),
      ...Object.keys(
        result.quality.dataset_b
          .issues
      ),
    ]);

    return [...keys].map(
      (key) => ({
        key,
        a:
          result.quality.dataset_a
            .issues[key] ?? 0,
        b:
          result.quality.dataset_b
            .issues[key] ?? 0,
      })
    );
  }, [result]);

  return (
    <div className="space-y-5">
      <section className="rounded-3xl border border-[#dfe8e3] bg-white p-6 shadow-sm">
        <p className="text-xs font-bold uppercase tracking-[0.17em] text-[#0b7664]">
          Dataset Intelligence
        </p>

        <h2 className="mt-1 text-2xl font-extrabold text-[#17332f]">
          Dataset Compare
        </h2>

        <p className="mt-2 text-sm text-slate-500">
          قارن أي مجموعتي بيانات جيومكانية متوافقتين من حيث البنية والمحتوى المكاني والجودة.
        </p>

        <div className="mt-6 grid gap-4 lg:grid-cols-[1fr_1fr_auto]">
          <DatasetUpload
            label="Dataset A"
            file={fileA}
            onChange={setFileA}
          />

          <DatasetUpload
            label="Dataset B"
            file={fileB}
            onChange={setFileB}
          />

          <button
            type="button"
            disabled={
              !fileA ||
              !fileB ||
              loading
            }
            onClick={() =>
              void run()
            }
            className="rounded-2xl bg-[#0b7664] px-7 py-3 text-sm font-bold text-white disabled:opacity-40"
          >
            {loading
              ? "Comparing..."
              : "Compare"}
          </button>
        </div>
      </section>

      {result && (
        <>
          <section
            className={`rounded-3xl border p-5 ${
              result.compatibility
                .compatible
                ? "border-emerald-200 bg-emerald-50"
                : "border-amber-200 bg-amber-50"
            }`}
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.15em]">
                  Compatibility
                </p>

                <h3 className="mt-1 text-lg font-extrabold">
                  {result
                    .compatibility
                    .compatible
                    ? "Datasets are comparable"
                    : "Datasets are not directly comparable"}
                </h3>

                <p className="mt-1 text-xs opacity-70">
                  {
                    result.compatibility
                      .reason
                  }
                </p>
              </div>

              <strong className="text-3xl">
                {
                  result.compatibility
                    .score
                }
                %
              </strong>
            </div>
          </section>

          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Metric
              label="Dataset A"
              value={
                result.dataset_a
                  .feature_count
              }
              detail={
                result.dataset_a.name
              }
            />

            <Metric
              label="Dataset B"
              value={
                result.dataset_b
                  .feature_count
              }
              detail={
                result.dataset_b.name
              }
            />

            <Metric
              label="Matched"
              value={
                result.spatial
                  .matched_count
              }
            />

            <Metric
              label="Spatial overlap"
              value={`${result.compatibility.spatial_overlap}%`}
            />
          </section>

          <section className="grid gap-5 xl:grid-cols-2">
            <QualityChart
              result={result}
            />

            <SpatialChart
              result={result}
            />
          </section>

          <section className="grid gap-5 xl:grid-cols-2">
            <IssueChart
              issues={issues}
            />

            <SchemaChart
              result={result}
            />
          </section>

          <section className="rounded-3xl border border-[#dfe8e3] bg-white p-6 shadow-sm">
            <h3 className="font-bold text-[#17332f]">
              Spatial comparison
            </h3>

            <div className="mt-5 grid gap-3 sm:grid-cols-4">
              <MiniMetric
                label="Matched"
                value={
                  result.spatial
                    .matched_count
                }
              />

              <MiniMetric
                label="Only A"
                value={
                  result.spatial
                    .only_a_count
                }
              />

              <MiniMetric
                label="Only B"
                value={
                  result.spatial
                    .only_b_count
                }
              />

              <MiniMetric
                label="Geometry differences"
                value={
                  result.spatial
                    .geometry_different_count
                }
              />
            </div>

            <p className="mt-4 rounded-xl bg-[#f6f9f7] p-4 text-xs leading-6 text-slate-600">
              العناصر الموجودة في Dataset واحدة فقط أو ذات هندسة مختلفة لا تعتبر أخطاء تلقائيًا؛ هي اختلافات تحتاج تفسيرًا حسب مصدر ونطاق كل Dataset.
            </p>
          </section>

          <section className="rounded-3xl border border-[#dfe8e3] bg-white p-6 shadow-sm">
            <p className="text-xs font-bold uppercase tracking-[0.17em] text-[#0b7664]">
              AI Comparison
            </p>

            <div className="mt-3 whitespace-pre-wrap text-sm leading-7 text-[#344b46]">
              {result.interpretation ??
                "AI interpretation unavailable."}
            </div>
          </section>

          <section className="rounded-3xl border border-amber-200 bg-amber-50 p-5">
            <h3 className="font-bold text-amber-950">
              GeoSA Compliance
            </h3>

            <p className="mt-2 text-sm leading-6 text-amber-800">
              {
                result.compliance
                  .message
              }
            </p>
          </section>
        </>
      )}
    </div>
  );
}

function DatasetUpload({
  label,
  file,
  onChange,
}: {
  label: string;
  file: File | null;
  onChange: (
    file: File | null
  ) => void;
}) {
  return (
    <label className="rounded-2xl border border-dashed border-[#b7d2c8] bg-[#f7fbf9] p-4">
      <strong className="text-sm text-[#17332f]">
        {label}
      </strong>

      <p className="mt-1 truncate text-xs text-slate-500">
        {file?.name ??
          "GeoJSON, GPKG or zipped Shapefile"}
      </p>

      <input
        type="file"
        accept=".geojson,.json,.gpkg,.zip"
        className="mt-3 block w-full text-xs"
        onChange={(event) =>
          onChange(
            event.target.files?.[0] ??
              null
          )
        }
      />
    </label>
  );
}

function Metric({
  label,
  value,
  detail,
}: {
  label: string;
  value: string | number;
  detail?: string;
}) {
  return (
    <div className="rounded-3xl border border-[#dfe8e3] bg-white p-5 shadow-sm">
      <p className="text-xs text-slate-500">
        {label}
      </p>

      <strong className="mt-2 block text-2xl text-[#17332f]">
        {value}
      </strong>

      {detail && (
        <p className="mt-1 truncate text-[10px] text-slate-400">
          {detail}
        </p>
      )}
    </div>
  );
}

function MiniMetric({
  label,
  value,
}: {
  label: string;
  value: number;
}) {
  return (
    <div className="rounded-xl bg-[#f6f9f7] p-4">
      <small className="text-slate-500">
        {label}
      </small>

      <strong className="mt-1 block text-xl text-[#17332f]">
        {value}
      </strong>
    </div>
  );
}

function QualityChart({
  result,
}: {
  result: DatasetCompareResponse;
}) {
  const a =
    result.quality.dataset_a
      .quality_score;

  const b =
    result.quality.dataset_b
      .quality_score;

  return (
    <ChartCard title="Quality Score">
      <Bar
        label="Dataset A"
        value={a}
        max={100}
        suffix="%"
      />

      <Bar
        label="Dataset B"
        value={b}
        max={100}
        suffix="%"
      />
    </ChartCard>
  );
}

function SpatialChart({
  result,
}: {
  result: DatasetCompareResponse;
}) {
  const spatial =
    result.spatial;

  const total =
    spatial.matched_count +
      spatial.only_a_count +
      spatial.only_b_count ||
    1;

  const matched =
    (spatial.matched_count /
      total) *
    100;

  const onlyA =
    (spatial.only_a_count /
      total) *
    100;

  return (
    <ChartCard title="Spatial Match">
      <div className="flex items-center gap-8">
        <div
          className="size-36 shrink-0 rounded-full"
          style={{
            background: `conic-gradient(#3f8f7c 0 ${matched}%, #d59a68 ${matched}% ${
              matched + onlyA
            }%, #8ca9c4 ${
              matched + onlyA
            }% 100%)`,
          }}
        >
          <div className="m-7 flex size-22 items-center justify-center rounded-full bg-white text-center text-xs font-bold text-[#17332f]">
            {
              spatial.matched_count
            }
            <br />
            matched
          </div>
        </div>

        <div className="space-y-2 text-xs">
          <p>
            Matched:{" "}
            <strong>
              {
                spatial.matched_count
              }
            </strong>
          </p>

          <p>
            Only A:{" "}
            <strong>
              {
                spatial.only_a_count
              }
            </strong>
          </p>

          <p>
            Only B:{" "}
            <strong>
              {
                spatial.only_b_count
              }
            </strong>
          </p>
        </div>
      </div>
    </ChartCard>
  );
}

function IssueChart({
  issues,
}: {
  issues: Array<{
    key: string;
    a: number;
    b: number;
  }>;
}) {
  const max = Math.max(
    ...issues.flatMap(
      (item) => [
        item.a,
        item.b,
      ]
    ),
    1
  );

  return (
    <ChartCard title="Quality Issues">
      {issues.map((item) => (
        <div
          key={item.key}
          className="space-y-1"
        >
          <p className="text-xs font-semibold text-slate-600">
            {item.key.replaceAll(
              "_",
              " "
            )}
          </p>

          <div className="grid grid-cols-[55px_1fr_40px] items-center gap-2 text-[10px]">
            <span>A</span>

            <div className="h-2 rounded-full bg-[#edf2ef]">
              <div
                className="h-full rounded-full bg-[#d39166]"
                style={{
                  width: `${
                    (item.a /
                      max) *
                    100
                  }%`,
                }}
              />
            </div>

            <strong>
              {item.a}
            </strong>

            <span>B</span>

            <div className="h-2 rounded-full bg-[#edf2ef]">
              <div
                className="h-full rounded-full bg-[#4d9b89]"
                style={{
                  width: `${
                    (item.b /
                      max) *
                    100
                  }%`,
                }}
              />
            </div>

            <strong>
              {item.b}
            </strong>
          </div>
        </div>
      ))}
    </ChartCard>
  );
}

function SchemaChart({
  result,
}: {
  result: DatasetCompareResponse;
}) {
  const values = [
    {
      label: "Common",
      value:
        result.schema
          .common_fields_count,
    },
    {
      label: "Only A",
      value:
        result.schema
          .only_a_count,
    },
    {
      label: "Only B",
      value:
        result.schema
          .only_b_count,
    },
  ];

  const max = Math.max(
    ...values.map(
      (item) => item.value
    ),
    1
  );

  return (
    <ChartCard title="Schema Comparison">
      {values.map((item) => (
        <Bar
          key={item.label}
          label={item.label}
          value={item.value}
          max={max}
        />
      ))}

      {!!result.schema
        .type_changes.length && (
        <p className="text-xs text-amber-700">
          {
            result.schema
              .type_changes.length
          }{" "}
          field type differences
        </p>
      )}
    </ChartCard>
  );
}

function ChartCard({
  title,
  children,
}: {
  title: string;
  children:
    React.ReactNode;
}) {
  return (
    <div className="rounded-3xl border border-[#dfe8e3] bg-white p-6 shadow-sm">
      <h3 className="font-bold text-[#17332f]">
        {title}
      </h3>

      <div className="mt-5 space-y-4">
        {children}
      </div>
    </div>
  );
}

function Bar({
  label,
  value,
  max,
  suffix = "",
}: {
  label: string;
  value: number;
  max: number;
  suffix?: string;
}) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs">
        <span>{label}</span>

        <strong>
          {value}
          {suffix}
        </strong>
      </div>

      <div className="h-3 overflow-hidden rounded-full bg-[#edf2ef]">
        <div
          className="h-full rounded-full bg-[#4d9b89]"
          style={{
            width: `${
              max
                ? Math.min(
                    100,
                    (value /
                      max) *
                      100
                  )
                : 0
            }%`,
          }}
        />
      </div>
    </div>
  );
}