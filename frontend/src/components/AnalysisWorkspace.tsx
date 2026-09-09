"use client";

import MapPanel from "@/components/MapPanel";
import { useLanguage } from "@/components/LanguageProvider";
import type { VectorProcessingResponse } from "@/types/analysis";
import { useState } from "react";

interface Props {
  result: VectorProcessingResponse;
  selectedErrorId: string | null;
  onSelectError: (id: string) => void;
}

const severityTone: Record<string, string> = {
  critical: "bg-red-100 text-red-700",
  high: "bg-red-100 text-red-700",
  medium: "bg-amber-100 text-amber-700",
  low: "bg-blue-100 text-blue-700",
};

export default function AnalysisWorkspace({ result, selectedErrorId, onSelectError }: Props) {
  const { language } = useLanguage();
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [severityTable, setSeverityTable] = useState<"critical" | "medium" | "low" | null>(null);
  const arabic = language === "ar";
  const errors = result.validation.errors;
  const selected = errors.find((error) => String(error.result_id) === selectedErrorId) ?? errors[0] ?? null;
  const analysis = selected ? result.analysis.analyses.find((item) => item.result_id === selected.result_id) : null;
  const critical = errors.filter((item) => item.severity === "critical" || item.severity === "high").length;
  const medium = errors.filter((item) => item.severity === "medium" || item.severity === "warning").length;
  const low = errors.filter((item) => item.severity === "low").length;
  const severityErrors = severityTable === "critical"
    ? errors.filter((item) => item.severity === "critical" || item.severity === "high")
    : severityTable === "medium"
      ? errors.filter((item) => item.severity === "medium" || item.severity === "warning")
      : severityTable === "low"
        ? errors.filter((item) => item.severity === "low")
        : [];
  const selectedIndex = Math.max(0, errors.findIndex((item) => item.result_id === selected?.result_id));
  const move = (offset: number) => {
    if (!errors.length) return;
    const next = (selectedIndex + offset + errors.length) % errors.length;
    onSelectError(String(errors[next].result_id));
  };

  return <><section style={{ direction: "ltr" }} className="grid min-h-[610px] overflow-hidden rounded-2xl border border-[#dfe5e1] bg-white shadow-sm xl:grid-cols-[320px_minmax(0,1fr)]">
    <aside dir={arabic ? "rtl" : "ltr"} className="order-2 border-t border-slate-200 bg-[#fdfefc] xl:order-1 xl:border-e xl:border-t-0">
      <div className="border-b border-slate-200 p-5">
        <div className="flex items-center gap-4">
          <div className="flex size-[82px] shrink-0 flex-col items-center justify-center rounded-full border-[7px] border-[#0b806c] bg-white text-[#075f50]"><strong className="text-2xl leading-none">{Math.round(result.compliance_score)}</strong><span className="mt-1 text-[9px]">/100</span></div>
          <div><p className="text-xs text-slate-500">{arabic ? "جودة البيانات" : "Data quality"}</p><strong className="mt-1 block text-lg text-[#17332f]">{result.validation.layer_name}</strong><p dir="auto" className="mt-1 max-w-[170px] truncate text-xs text-slate-400">{result.filename}</p></div>
        </div>
        <div className="mt-4 grid grid-cols-3 gap-2 text-center text-xs">
          <button type="button" onClick={() => setSeverityTable("critical")} className="rounded-lg py-2 transition hover:bg-red-50 focus-visible:outline-2 focus-visible:outline-red-500"><b className="block text-red-600">{critical}</b><span className="text-slate-500">{arabic ? "حرجة" : "Critical"}</span></button>
          <button type="button" onClick={() => setSeverityTable("medium")} className="rounded-lg py-2 transition hover:bg-amber-50 focus-visible:outline-2 focus-visible:outline-amber-500"><b className="block text-amber-500">{medium}</b><span className="text-slate-500">{arabic ? "متوسطة" : "Medium"}</span></button>
          <button type="button" onClick={() => setSeverityTable("low")} className="rounded-lg py-2 transition hover:bg-blue-50 focus-visible:outline-2 focus-visible:outline-blue-500"><b className="block text-blue-600">{low}</b><span className="text-slate-500">{arabic ? "طفيفة" : "Low"}</span></button>
        </div>
      </div>

      {selected ? <div className="p-5"><div className="flex items-start justify-between gap-3"><div><span className={`rounded px-2 py-1 text-[10px] font-bold ${severityTone[selected.severity] ?? "bg-slate-100"}`}>{selected.severity}</span><h2 className="mt-3 text-lg font-extrabold capitalize text-[#17332f]">{selected.error_type.replaceAll("_", " ")}</h2><p className="mt-1 text-[11px] text-slate-400">{selected.rule_id}</p></div><span className="text-xs text-slate-400">{selectedIndex + 1} / {errors.length}</span></div><p className="mt-3 text-xs leading-6 text-slate-600">{analysis?.explanation ?? selected.details}</p><div className="mt-4"><strong className="text-xs text-[#17332f]">{arabic ? "عنصر الجودة" : "Quality element"}</strong><p className="mt-1 text-xs text-slate-500">Logical Consistency</p></div><div className="mt-4"><strong className="text-xs text-[#17332f]">{arabic ? "التوصية" : "Recommendation"}</strong><p className="mt-1 text-xs leading-5 text-slate-600">{analysis?.recommendation ?? (arabic ? "راجع العنصر وصحح هندسته وفق المعيار." : "Review and correct the feature geometry.")}</p></div><div className="mt-5 flex items-center justify-between"><button type="button" onClick={() => move(-1)} className="rounded-lg border border-slate-200 px-3 py-2">‹</button><span className="text-xs font-bold">{selectedIndex + 1} / {errors.length}</span><button type="button" onClick={() => move(1)} className="rounded-lg border border-slate-200 px-3 py-2">›</button></div><button type="button" onClick={() => setDetailsOpen(true)} className="mt-5 w-full rounded-xl border border-slate-300 bg-white py-3 text-sm font-bold text-[#17332f] hover:bg-[#edf7f3]">{arabic ? "عرض جميع التفاصيل ←" : "View all details →"}</button></div> : <p className="p-8 text-center text-sm text-emerald-700">{arabic ? "لا توجد أخطاء" : "No errors found"}</p>}
    </aside>
    <div dir={arabic ? "rtl" : "ltr"} className="order-1 min-w-0 bg-[#f7f8f5] p-3 xl:order-2"><MapPanel result={result} selectedErrorId={selectedErrorId} /></div>
  </section>
  {severityTable && <div className="fixed inset-0 z-[4900] flex items-center justify-center bg-slate-950/55 p-4" role="dialog" aria-modal="true" onMouseDown={(event) => { if (event.target === event.currentTarget) setSeverityTable(null); }}><section dir={arabic ? "rtl" : "ltr"} className="max-h-[86vh] w-full max-w-5xl overflow-hidden rounded-2xl bg-white shadow-2xl"><header className="flex items-center justify-between border-b border-slate-200 px-5 py-4"><div><h2 className="text-xl font-extrabold text-[#17332f]">{severityTable === "critical" ? (arabic ? "جميع الأخطاء الحرجة" : "All critical errors") : severityTable === "medium" ? (arabic ? "جميع الأخطاء المتوسطة" : "All medium errors") : (arabic ? "جميع الأخطاء الطفيفة" : "All low errors")}</h2><p className="mt-1 text-xs text-slate-500">{arabic ? `${severityErrors.length} أخطاء` : `${severityErrors.length} errors`}</p></div><button type="button" onClick={() => setSeverityTable(null)} aria-label={arabic ? "إغلاق" : "Close"} className="rounded-full bg-slate-100 px-3 py-1.5 text-lg hover:bg-slate-200">×</button></header><div className="max-h-[68vh] overflow-auto"><table className="w-full min-w-[720px] text-sm"><thead className="sticky top-0 bg-[#f5f8f6] text-slate-500"><tr><th className="p-4 text-start">#</th><th className="p-4 text-start">{arabic ? "نوع الخطأ" : "Error type"}</th><th className="p-4 text-start">{arabic ? "معرّف العنصر" : "Feature ID"}</th><th className="p-4 text-start">{arabic ? "الطبقة" : "Layer"}</th><th className="p-4 text-start">{arabic ? "الخطورة" : "Severity"}</th><th className="p-4 text-start">{arabic ? "التفاصيل" : "Details"}</th></tr></thead><tbody className="divide-y divide-slate-100">{severityErrors.map((item, index) => <tr key={String(item.result_id)} onClick={() => { onSelectError(String(item.result_id)); setSeverityTable(null); }} className="cursor-pointer transition hover:bg-[#edf7f3]"><td className="p-4 font-bold text-slate-400">{index + 1}</td><td className="p-4 font-bold capitalize text-[#17332f]">{item.error_type.replaceAll("_", " ")}</td><td className="p-4">{item.feature_id || "—"}</td><td className="p-4">{item.layer_name}</td><td className="p-4"><span className={`rounded-full px-2.5 py-1 text-xs font-bold ${severityTone[item.severity] ?? "bg-slate-100"}`}>{arabic ? (item.severity === "critical" || item.severity === "high" ? "حرجة" : item.severity === "medium" || item.severity === "warning" ? "متوسطة" : "طفيفة") : item.severity}</span></td><td className="max-w-xs truncate p-4 text-slate-500">{item.details}</td></tr>)}</tbody></table>{severityErrors.length === 0 && <p className="p-10 text-center text-slate-500">{arabic ? "لا توجد أخطاء ضمن هذه الدرجة" : "No errors in this severity"}</p>}</div></section></div>}
  {detailsOpen && selected && <div className="fixed inset-0 z-[5000] flex items-center justify-center bg-slate-950/55 p-4" role="dialog" aria-modal="true"><section style={{ direction: "ltr" }} className="grid max-h-[92vh] w-full max-w-6xl overflow-y-auto rounded-2xl bg-white p-3 shadow-2xl lg:grid-cols-[1.1fr_.9fr]"><div className="min-w-0"><MapPanel result={result} selectedErrorId={String(selected.result_id)} initialBasemap="satellite" /></div><aside dir={arabic ? "rtl" : "ltr"} className="p-5 lg:p-7"><div className="flex items-start justify-between gap-3"><div><div className="flex items-center gap-2"><span className={`rounded px-3 py-1 text-xs font-bold ${severityTone[selected.severity] ?? "bg-slate-100"}`}>{selected.severity}</span><span className="text-sm font-bold text-slate-500">{selected.rule_id}</span></div><h2 className="mt-3 text-2xl font-extrabold capitalize text-[#17332f]">{selected.error_type.replaceAll("_", " ")}</h2><p className="mt-2 text-sm leading-6 text-slate-600">{analysis?.explanation ?? selected.details}</p></div><button type="button" onClick={() => setDetailsOpen(false)} className="rounded-full bg-slate-100 px-3 py-1.5 text-lg">×</button></div><dl className="mt-6 space-y-4 border-t border-slate-200 pt-5 text-sm"><div className="flex justify-between gap-4"><dt className="text-slate-400">{arabic ? "الطبقة" : "Layer"}</dt><dd className="font-bold">{selected.layer_name}</dd></div><div className="flex justify-between gap-4"><dt className="text-slate-400">{arabic ? "معرف العنصر" : "Feature ID"}</dt><dd className="font-bold">{selected.feature_id}</dd></div><div className="flex justify-between gap-4"><dt className="text-slate-400">GeoSA</dt><dd className="font-bold">{selected.rule_id}</dd></div><div className="flex justify-between gap-4"><dt className="text-slate-400">{arabic ? "التوصية" : "Recommendation"}</dt><dd className="max-w-[280px] text-end font-semibold">{analysis?.recommendation ?? selected.details}</dd></div></dl><div className="mt-8 flex gap-3"><button type="button" onClick={() => setDetailsOpen(false)} className="flex-1 rounded-xl border border-slate-300 py-3 text-sm font-bold">{arabic ? "إغلاق" : "Close"}</button><button type="button" onClick={() => setDetailsOpen(false)} className="flex-[1.7] rounded-xl bg-[#075f50] py-3 text-sm font-bold text-white">{arabic ? "عرض موقع الخطأ على الخريطة" : "Show error on map"}</button></div></aside></section></div>}
  </>;
}
