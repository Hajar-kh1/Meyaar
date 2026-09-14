"use client";

import { useState } from "react";

import MapPanel from "@/components/MapPanel";
import { useLanguage } from "@/components/LanguageProvider";
import type {
  ValidationError,
  VectorProcessingResponse,
} from "@/types/analysis";

interface Props {
  result: VectorProcessingResponse;
  selectedErrorId: string | null;
  onSelectError: (id: string) => void;
}

type SeverityGroup = "critical" | "medium" | "low";

const severityTone: Record<string, string> = {
  critical: "bg-red-100 text-red-700",
  high: "bg-red-100 text-red-700",
  medium: "bg-amber-100 text-amber-700",
  warning: "bg-amber-100 text-amber-700",
  low: "bg-blue-100 text-blue-700",
};

function matchesSeverity(
  error: ValidationError,
  group: SeverityGroup,
) {
  if (group === "critical") {
    return (
      error.severity === "critical" ||
      error.severity === "high"
    );
  }

  if (group === "medium") {
    return (
      error.severity === "medium" ||
      error.severity === "warning"
    );
  }

  return error.severity === "low";
}

function severityLabel(
  severity: string,
  arabic: boolean,
) {
  if (!arabic) {
    return severity;
  }

  if (
    severity === "critical" ||
    severity === "high"
  ) {
    return "حرجة";
  }

  if (
    severity === "medium" ||
    severity === "warning"
  ) {
    return "متوسطة";
  }

  return "طفيفة";
}

function severityGroupTitle(
  group: SeverityGroup,
  arabic: boolean,
) {
  if (group === "critical") {
    return arabic
      ? "جميع الأخطاء الحرجة"
      : "All critical errors";
  }

  if (group === "medium") {
    return arabic
      ? "جميع الأخطاء المتوسطة"
      : "All medium errors";
  }

  return arabic
    ? "جميع الأخطاء الطفيفة"
    : "All low errors";
}

function getMapUnavailableMessage(
  error: ValidationError | null,
  arabic: boolean,
) {
  if (!error) {
    return null;
  }

  if (
    error.rule_id === "GIS002" ||
    error.error_type
      ?.toLowerCase()
      .includes("invalid coordinates")
  ) {
    return arabic
      ? "لا يمكن عرض موقع هذا الخطأ على الخريطة لأن الإحداثيات خارج النطاق الجغرافي الصالح."
      : "This error cannot be shown on the map because its coordinates are outside the valid geographic range.";
  }

  if (
    error.rule_id === "BLD004" ||
    error.rule_id === "RD005" ||
    !error.geometry
  ) {
    return arabic
      ? "لا يمكن عرض هذا العنصر على الخريطة لأنه لا يحتوي على هندسة مكانية."
      : "This feature cannot be shown on the map because it has no spatial geometry.";
  }

  return null;
}

function MapUnavailable({
  message,
  arabic,
  compact = false,
}: {
  message: string;
  arabic: boolean;
  compact?: boolean;
}) {
  return (
    <div
      className={`flex items-center justify-center rounded-2xl border border-amber-200 bg-amber-50/40 p-8 text-center ${
        compact
          ? "min-h-[420px]"
          : "min-h-[610px]"
      }`}
    >
      <div className="max-w-md">
        <div className="mx-auto flex size-14 items-center justify-center rounded-full bg-amber-100 text-xl font-extrabold text-amber-700">
          !
        </div>

        <h3 className="mt-4 text-lg font-extrabold text-[#17332f]">
          {arabic
            ? "تعذر عرض موقع الخطأ"
            : "Error location unavailable"}
        </h3>

        <p className="mt-2 text-sm leading-6 text-slate-500">
          {message}
        </p>
      </div>
    </div>
  );
}

export default function AnalysisWorkspace({
  result,
  selectedErrorId,
  onSelectError,
}: Props) {
  const { language } = useLanguage();

  const [detailsOpen, setDetailsOpen] =
    useState(false);

  const [
    severityTable,
    setSeverityTable,
  ] = useState<SeverityGroup | null>(
    null,
  );

  const arabic = language === "ar";

  const activeValidation =
    result.validation_after ??
    result.validation;

  const errors =
    activeValidation.errors ?? [];

  const requestedIndex =
    selectedErrorId === null
      ? -1
      : errors.findIndex(
          (error) =>
            String(error.result_id) ===
            selectedErrorId,
        );

  const selectedIndex =
    errors.length === 0
      ? -1
      : requestedIndex >= 0
        ? requestedIndex
        : 0;

  const selected =
    selectedIndex >= 0
      ? errors[selectedIndex]
      : null;

  const selectedMapError =
    getMapUnavailableMessage(
      selected,
      arabic,
    );

  const analysis = selected
    ? result.analysis.analyses.find(
        (item) =>
          item.result_id ===
          selected.result_id,
      ) ??
      result.analysis.analyses.find(
        (item) =>
          item.feature_id ===
            selected.feature_id &&
          item.rule_id ===
            selected.rule_id,
      )
    : null;

  const critical = errors.filter(
    (item) =>
      matchesSeverity(
        item,
        "critical",
      ),
  ).length;

  const medium = errors.filter(
    (item) =>
      matchesSeverity(
        item,
        "medium",
      ),
  ).length;

  const low = errors.filter(
    (item) =>
      matchesSeverity(
        item,
        "low",
      ),
  ).length;

  const severityErrors =
    severityTable
      ? errors.filter((item) =>
          matchesSeverity(
            item,
            severityTable,
          ),
        )
      : [];

  const revalidation =
    result.revalidation_summary;

  const showRevalidation =
    Boolean(
      revalidation?.attempted ||
        revalidation?.performed,
    );

  const move = (
    offset: number,
  ) => {
    if (
      !errors.length ||
      selectedIndex < 0
    ) {
      return;
    }

    const nextIndex =
      (
        selectedIndex +
        offset +
        errors.length
      ) % errors.length;

    onSelectError(
      String(
        errors[nextIndex].result_id,
      ),
    );
  };

  const openError = (
    error: ValidationError,
  ) => {
    onSelectError(
      String(error.result_id),
    );

    setSeverityTable(null);
  };

  const qualityScore =
    result.quality_score ??
    result.compliance_score;

  const selectedPosition =
    selectedIndex >= 0
      ? selectedIndex + 1
      : 0;

  return (
    <>
      {showRevalidation && (
        <section
          dir={
            arabic ? "rtl" : "ltr"
          }
          className="mb-4 rounded-2xl border border-emerald-200 bg-white p-5 shadow-sm"
        >
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-bold uppercase tracking-wide text-[#0b806c]">
                {arabic
                  ? "إعادة التحقق بعد الإصلاح"
                  : "Post-remediation re-validation"}
              </p>

              <h2 className="mt-1 text-lg font-extrabold text-[#17332f]">
                {revalidation.performed
                  ? arabic
                    ? "تمت إعادة التحقق بنجاح"
                    : "Re-validation completed"
                  : arabic
                    ? "تم تطبيق إصلاحات ولم تكتمل إعادة التحقق"
                    : "Fixes were applied but re-validation did not complete"}
              </h2>
            </div>

            {revalidation.performed && (
              <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-700">
                {arabic
                  ? "تم التحقق"
                  : "Verified"}
              </span>
            )}
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <div className="rounded-xl bg-slate-50 p-4">
              <p className="text-xs text-slate-500">
                {arabic
                  ? "الجودة قبل"
                  : "Before quality"}
              </p>

              <strong className="mt-1 block text-2xl text-[#17332f]">
                {Math.round(
                  revalidation.quality_before ??
                    0,
                )}
                %
              </strong>
            </div>

            <div className="rounded-xl bg-emerald-50 p-4">
              <p className="text-xs text-slate-500">
                {arabic
                  ? "الجودة بعد"
                  : "After quality"}
              </p>

              <strong className="mt-1 block text-2xl text-[#075f50]">
                {Math.round(
                  revalidation.quality_after ??
                    0,
                )}
                %
              </strong>
            </div>

            <div className="rounded-xl bg-slate-50 p-4">
              <p className="text-xs text-slate-500">
                {arabic
                  ? "التحسن"
                  : "Improvement"}
              </p>

              <strong
                className={`mt-1 block text-2xl ${
                  (
                    revalidation.quality_improvement ??
                    0
                  ) > 0
                    ? "text-emerald-600"
                    : "text-slate-600"
                }`}
              >
                {(revalidation.quality_improvement ??
                  0) > 0
                  ? "+"
                  : ""}
                {revalidation.quality_improvement ??
                  0}
                %
              </strong>
            </div>

            <div className="rounded-xl bg-emerald-50 p-4">
              <p className="text-xs text-slate-500">
                {arabic
                  ? "الإصلاحات الناجحة"
                  : "Resolved fixes"}
              </p>

              <strong className="mt-1 block text-2xl text-emerald-600">
                {revalidation.resolved_fixes ??
                  0}
              </strong>
            </div>

            <div className="rounded-xl bg-amber-50 p-4">
              <p className="text-xs text-slate-500">
                {arabic
                  ? "المتبقي"
                  : "Remaining"}
              </p>

              <strong className="mt-1 block text-2xl text-amber-600">
                {revalidation.unresolved_fixes ??
                  0}
              </strong>
            </div>
          </div>

          {revalidation.performed && (
            <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2 border-t border-slate-100 pt-4 text-xs text-slate-500">
              <span>
                {arabic
                  ? "النتائج قبل: "
                  : "Findings before: "}
                <b className="text-slate-700">
                  {revalidation.findings_before ??
                    0}
                </b>
              </span>

              <span>
                {arabic
                  ? "النتائج بعد: "
                  : "Findings after: "}
                <b className="text-slate-700">
                  {revalidation.findings_after ??
                    0}
                </b>
              </span>

              <span>
                {arabic
                  ? "العناصر المتأثرة قبل: "
                  : "Affected before: "}
                <b className="text-slate-700">
                  {revalidation.affected_features_before ??
                    0}
                </b>
              </span>

              <span>
                {arabic
                  ? "العناصر المتأثرة بعد: "
                  : "Affected after: "}
                <b className="text-slate-700">
                  {revalidation.affected_features_after ??
                    0}
                </b>
              </span>
            </div>
          )}
        </section>
      )}

      <section
        style={{
          direction: "ltr",
        }}
        className="grid min-h-[610px] overflow-hidden rounded-2xl border border-[#dfe5e1] bg-white shadow-sm xl:grid-cols-[320px_minmax(0,1fr)]"
      >
        <aside
          dir={
            arabic ? "rtl" : "ltr"
          }
          className="order-2 border-t border-slate-200 bg-[#fdfefc] xl:order-1 xl:border-e xl:border-t-0"
        >
          <div className="border-b border-slate-200 p-5">
            <div className="flex items-center gap-4">
              <div className="flex size-[82px] shrink-0 flex-col items-center justify-center rounded-full border-[7px] border-[#0b806c] bg-white text-[#075f50]">
                <strong className="text-2xl leading-none">
                  {Math.round(
                    qualityScore,
                  )}
                </strong>

                <span className="mt-1 text-[9px]">
                  /100
                </span>
              </div>

              <div>
                <p className="text-xs text-slate-500">
                  {arabic
                    ? "جودة البيانات"
                    : "Data quality"}
                </p>

                <strong className="mt-1 block text-lg text-[#17332f]">
                  {
                    activeValidation.layer_name
                  }
                </strong>

                <p
                  dir="auto"
                  className="mt-1 max-w-[170px] truncate text-xs text-slate-400"
                >
                  {result.filename}
                </p>
              </div>
            </div>

            <div className="mt-4 grid grid-cols-3 gap-2 text-center text-xs">
              <button
                type="button"
                onClick={() =>
                  setSeverityTable(
                    "critical",
                  )
                }
                className="rounded-lg py-2 transition hover:bg-red-50 focus-visible:outline-2 focus-visible:outline-red-500"
              >
                <b className="block text-red-600">
                  {critical}
                </b>

                <span className="text-slate-500">
                  {arabic
                    ? "حرجة"
                    : "Critical"}
                </span>
              </button>

              <button
                type="button"
                onClick={() =>
                  setSeverityTable(
                    "medium",
                  )
                }
                className="rounded-lg py-2 transition hover:bg-amber-50 focus-visible:outline-2 focus-visible:outline-amber-500"
              >
                <b className="block text-amber-500">
                  {medium}
                </b>

                <span className="text-slate-500">
                  {arabic
                    ? "متوسطة"
                    : "Medium"}
                </span>
              </button>

              <button
                type="button"
                onClick={() =>
                  setSeverityTable(
                    "low",
                  )
                }
                className="rounded-lg py-2 transition hover:bg-blue-50 focus-visible:outline-2 focus-visible:outline-blue-500"
              >
                <b className="block text-blue-600">
                  {low}
                </b>

                <span className="text-slate-500">
                  {arabic
                    ? "طفيفة"
                    : "Low"}
                </span>
              </button>
            </div>
          </div>

          {selected ? (
            <div className="p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <span
                    className={`rounded px-2 py-1 text-[10px] font-bold ${
                      severityTone[
                        selected.severity
                      ] ??
                      "bg-slate-100 text-slate-700"
                    }`}
                  >
                    {severityLabel(
                      selected.severity,
                      arabic,
                    )}
                  </span>

                  <h2 className="mt-3 text-lg font-extrabold capitalize text-[#17332f]">
                    {selected.error_type.replaceAll(
                      "_",
                      " ",
                    )}
                  </h2>

                  <p className="mt-1 text-[11px] text-slate-400">
                    {selected.rule_id}
                  </p>
                </div>

                <span className="text-xs text-slate-400">
                  {selectedPosition} /{" "}
                  {errors.length}
                </span>
              </div>

              <p className="mt-3 text-xs leading-6 text-slate-600">
                {analysis?.explanation ??
                  selected.details}
              </p>

              <div className="mt-4">
                <strong className="text-xs text-[#17332f]">
                  {arabic
                    ? "عنصر الجودة"
                    : "Quality element"}
                </strong>

                <p className="mt-1 text-xs text-slate-500">
                  Logical Consistency
                </p>
              </div>

              <div className="mt-4">
                <strong className="text-xs text-[#17332f]">
                  {arabic
                    ? "التوصية"
                    : "Recommendation"}
                </strong>

                <p className="mt-1 text-xs leading-5 text-slate-600">
                  {analysis?.recommendation ??
                    (arabic
                      ? "راجع العنصر وصحح هندسته وفق المعيار."
                      : "Review and correct the feature geometry.")}
                </p>
              </div>

              {selectedMapError && (
                <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-800">
                  {selectedMapError}
                </div>
              )}

              <div className="mt-5 flex items-center justify-between">
                <button
                  type="button"
                  onClick={() =>
                    move(-1)
                  }
                  disabled={
                    errors.length <= 1
                  }
                  className="rounded-lg border border-slate-200 px-3 py-2 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  ‹
                </button>

                <span className="text-xs font-bold">
                  {selectedPosition} /{" "}
                  {errors.length}
                </span>

                <button
                  type="button"
                  onClick={() =>
                    move(1)
                  }
                  disabled={
                    errors.length <= 1
                  }
                  className="rounded-lg border border-slate-200 px-3 py-2 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  ›
                </button>
              </div>

              <button
                type="button"
                onClick={() =>
                  setDetailsOpen(true)
                }
                className="mt-5 w-full rounded-xl border border-slate-300 bg-white py-3 text-sm font-bold text-[#17332f] hover:bg-[#edf7f3]"
              >
                {arabic
                  ? "عرض جميع التفاصيل ←"
                  : "View all details →"}
              </button>
            </div>
          ) : (
            <p className="p-8 text-center text-sm text-emerald-700">
              {arabic
                ? "لا توجد أخطاء متبقية"
                : "No remaining errors"}
            </p>
          )}
        </aside>

        <div
          dir={
            arabic ? "rtl" : "ltr"
          }
          className="order-1 min-w-0 bg-[#f7f8f5] p-3 xl:order-2"
        >
          {selectedMapError ? (
            <MapUnavailable
              message={
                selectedMapError
              }
              arabic={arabic}
            />
          ) : (
            <MapPanel
              result={result}
              selectedErrorId={
                selected
                  ? String(
                      selected.result_id,
                    )
                  : null
              }
            />
          )}
        </div>
      </section>

      {severityTable && (
        <div
          className="fixed inset-0 z-[4900] flex items-center justify-center bg-slate-950/55 p-4"
          role="dialog"
          aria-modal="true"
          onMouseDown={(
            event,
          ) => {
            if (
              event.target ===
              event.currentTarget
            ) {
              setSeverityTable(
                null,
              );
            }
          }}
        >
          <section
            dir={
              arabic
                ? "rtl"
                : "ltr"
            }
            className="max-h-[86vh] w-full max-w-5xl overflow-hidden rounded-2xl bg-white shadow-2xl"
          >
            <header className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
              <div>
                <h2 className="text-xl font-extrabold text-[#17332f]">
                  {severityGroupTitle(
                    severityTable,
                    arabic,
                  )}
                </h2>

                <p className="mt-1 text-xs text-slate-500">
                  {arabic
                    ? `${severityErrors.length} أخطاء`
                    : `${severityErrors.length} errors`}
                </p>
              </div>

              <button
                type="button"
                onClick={() =>
                  setSeverityTable(
                    null,
                  )
                }
                aria-label={
                  arabic
                    ? "إغلاق"
                    : "Close"
                }
                className="rounded-full bg-slate-100 px-3 py-1.5 text-lg hover:bg-slate-200"
              >
                ×
              </button>
            </header>

            <div className="max-h-[68vh] overflow-auto">
              <table className="w-full min-w-[720px] text-sm">
                <thead className="sticky top-0 bg-[#f5f8f6] text-slate-500">
                  <tr>
                    <th className="p-4 text-start">
                      #
                    </th>

                    <th className="p-4 text-start">
                      {arabic
                        ? "نوع الخطأ"
                        : "Error type"}
                    </th>

                    <th className="p-4 text-start">
                      {arabic
                        ? "معرّف العنصر"
                        : "Feature ID"}
                    </th>

                    <th className="p-4 text-start">
                      {arabic
                        ? "الطبقة"
                        : "Layer"}
                    </th>

                    <th className="p-4 text-start">
                      {arabic
                        ? "الخطورة"
                        : "Severity"}
                    </th>

                    <th className="p-4 text-start">
                      {arabic
                        ? "التفاصيل"
                        : "Details"}
                    </th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-slate-100">
                  {severityErrors.map(
                    (
                      item,
                      index,
                    ) => (
                      <tr
                        key={String(
                          item.result_id,
                        )}
                        onClick={() =>
                          openError(item)
                        }
                        className="cursor-pointer transition hover:bg-[#edf7f3]"
                      >
                        <td className="p-4 font-bold text-slate-400">
                          {index + 1}
                        </td>

                        <td className="p-4 font-bold capitalize text-[#17332f]">
                          {item.error_type.replaceAll(
                            "_",
                            " ",
                          )}
                        </td>

                        <td className="p-4">
                          {item.feature_id ||
                            "—"}
                        </td>

                        <td className="p-4">
                          {
                            item.layer_name
                          }
                        </td>

                        <td className="p-4">
                          <span
                            className={`rounded-full px-2.5 py-1 text-xs font-bold ${
                              severityTone[
                                item
                                  .severity
                              ] ??
                              "bg-slate-100 text-slate-700"
                            }`}
                          >
                            {severityLabel(
                              item.severity,
                              arabic,
                            )}
                          </span>
                        </td>

                        <td className="max-w-xs truncate p-4 text-slate-500">
                          {
                            item.details
                          }
                        </td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>

              {severityErrors.length ===
                0 && (
                <p className="p-10 text-center text-slate-500">
                  {arabic
                    ? "لا توجد أخطاء ضمن هذه الدرجة"
                    : "No errors in this severity"}
                </p>
              )}
            </div>
          </section>
        </div>
      )}

      {detailsOpen &&
        selected && (
          <div
            className="fixed inset-0 z-[5000] flex items-center justify-center bg-slate-950/55 p-4"
            role="dialog"
            aria-modal="true"
            onMouseDown={(
              event,
            ) => {
              if (
                event.target ===
                event.currentTarget
              ) {
                setDetailsOpen(
                  false,
                );
              }
            }}
          >
            <section
              style={{
                direction: "ltr",
              }}
              className="grid max-h-[92vh] w-full max-w-6xl overflow-y-auto rounded-2xl bg-white p-3 shadow-2xl lg:grid-cols-[1.1fr_.9fr]"
            >
              <div className="min-w-0">
                {selectedMapError ? (
                  <MapUnavailable
                    message={
                      selectedMapError
                    }
                    arabic={
                      arabic
                    }
                    compact
                  />
                ) : (
                  <MapPanel
                    result={
                      result
                    }
                    selectedErrorId={String(
                      selected.result_id,
                    )}
                    initialBasemap="satellite"
                  />
                )}
              </div>

              <aside
                dir={
                  arabic
                    ? "rtl"
                    : "ltr"
                }
                className="p-5 lg:p-7"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span
                        className={`rounded px-3 py-1 text-xs font-bold ${
                          severityTone[
                            selected
                              .severity
                          ] ??
                          "bg-slate-100 text-slate-700"
                        }`}
                      >
                        {severityLabel(
                          selected.severity,
                          arabic,
                        )}
                      </span>

                      <span className="text-sm font-bold text-slate-500">
                        {
                          selected.rule_id
                        }
                      </span>
                    </div>

                    <h2 className="mt-3 text-2xl font-extrabold capitalize text-[#17332f]">
                      {selected.error_type.replaceAll(
                        "_",
                        " ",
                      )}
                    </h2>

                    <p className="mt-2 text-sm leading-6 text-slate-600">
                      {analysis?.explanation ??
                        selected.details}
                    </p>
                  </div>

                  <button
                    type="button"
                    onClick={() =>
                      setDetailsOpen(
                        false,
                      )
                    }
                    className="rounded-full bg-slate-100 px-3 py-1.5 text-lg"
                  >
                    ×
                  </button>
                </div>

                <dl className="mt-6 space-y-4 border-t border-slate-200 pt-5 text-sm">
                  <div className="flex justify-between gap-4">
                    <dt className="text-slate-400">
                      {arabic
                        ? "الطبقة"
                        : "Layer"}
                    </dt>

                    <dd className="font-bold">
                      {
                        selected.layer_name
                      }
                    </dd>
                  </div>

                  <div className="flex justify-between gap-4">
                    <dt className="text-slate-400">
                      {arabic
                        ? "معرف العنصر"
                        : "Feature ID"}
                    </dt>

                    <dd className="font-bold">
                      {selected.feature_id ||
                        "—"}
                    </dd>
                  </div>

                  <div className="flex justify-between gap-4">
                    <dt className="text-slate-400">
                      GeoSA
                    </dt>

                    <dd className="font-bold">
                      {
                        selected.rule_id
                      }
                    </dd>
                  </div>

                  <div className="flex justify-between gap-4">
                    <dt className="text-slate-400">
                      {arabic
                        ? "التوصية"
                        : "Recommendation"}
                    </dt>

                    <dd className="max-w-[280px] text-end font-semibold">
                      {analysis?.recommendation ??
                        selected.details}
                    </dd>
                  </div>
                </dl>

                {selectedMapError && (
                  <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-800">
                    {
                      selectedMapError
                    }
                  </div>
                )}

                <div className="mt-8 flex gap-3">
                  <button
                    type="button"
                    onClick={() =>
                      setDetailsOpen(
                        false,
                      )
                    }
                    className="flex-1 rounded-xl border border-slate-300 py-3 text-sm font-bold"
                  >
                    {arabic
                      ? "إغلاق"
                      : "Close"}
                  </button>

                  {!selectedMapError && (
                    <button
                      type="button"
                      onClick={() =>
                        setDetailsOpen(
                          false,
                        )
                      }
                      className="flex-[1.7] rounded-xl bg-[#075f50] py-3 text-sm font-bold text-white"
                    >
                      {arabic
                        ? "عرض موقع الخطأ على الخريطة"
                        : "Show error on map"}
                    </button>
                  )}
                </div>
              </aside>
            </section>
          </div>
        )}
    </>
  );
}