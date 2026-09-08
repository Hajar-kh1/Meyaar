"use client";

import MapPanel from "@/components/MapPanel";
import { useLanguage } from "@/components/LanguageProvider";
import type { VectorProcessingResponse } from "@/types/analysis";

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
  const arabic = language === "ar";
  const errors = result.validation.errors;
  const selected = errors.find((error) => String(error.result_id) === selectedErrorId) ?? errors[0] ?? null;
  const analysis = selected ? result.analysis.analyses.find((item) => item.result_id === selected.result_id) : null;
  const critical = errors.filter((item) => item.severity === "critical" || item.severity === "high").length;
  const medium = errors.filter((item) => item.severity === "medium" || item.severity === "warning").length;
  const low = errors.filter((item) => item.severity === "low").length;

  return <section dir={arabic ? "rtl" : "ltr"} className="grid min-h-[650px] overflow-hidden rounded-2xl border border-[#dfe5e1] bg-white shadow-sm xl:grid-cols-[330px_minmax(0,1fr)]">
    <aside className="order-2 border-t border-slate-200 bg-[#fdfefc] xl:order-1 xl:border-e xl:border-t-0">
      <div className="border-b border-slate-200 p-5">
        <div className="flex items-center gap-4">
          <div className="flex size-[82px] shrink-0 flex-col items-center justify-center rounded-full border-[7px] border-[#0b806c] bg-white text-[#075f50]"><strong className="text-2xl leading-none">{Math.round(result.compliance_score)}</strong><span className="mt-1 text-[9px]">/100</span></div>
          <div><p className="text-xs text-slate-500">{arabic ? "جودة البيانات" : "Data quality"}</p><strong className="mt-1 block text-lg text-[#17332f]">{result.validation.layer_name}</strong><p dir="auto" className="mt-1 max-w-[170px] truncate text-xs text-slate-400">{result.filename}</p></div>
        </div>
        <div className="mt-4 grid grid-cols-3 gap-2 text-center text-xs"><div><b className="block text-red-600">{critical}</b><span className="text-slate-500">{arabic ? "حرجة" : "Critical"}</span></div><div><b className="block text-amber-500">{medium}</b><span className="text-slate-500">{arabic ? "متوسطة" : "Medium"}</span></div><div><b className="block text-blue-600">{low}</b><span className="text-slate-500">{arabic ? "طفيفة" : "Low"}</span></div></div>
      </div>

      <div className="max-h-[245px] overflow-y-auto border-b border-slate-200 p-3">
        {errors.length ? errors.map((error) => <button key={error.result_id} type="button" onClick={() => onSelectError(String(error.result_id))} className={`mb-2 w-full rounded-xl border p-3 text-start transition last:mb-0 ${selected?.result_id === error.result_id ? "border-[#8fc6b6] bg-[#edf7f3]" : "border-slate-200 hover:bg-slate-50"}`}><div className="flex items-center justify-between gap-2"><strong className="truncate text-sm text-[#17332f]">{error.error_type.replaceAll("_", " ")}</strong><span className={`shrink-0 rounded px-2 py-1 text-[10px] font-bold ${severityTone[error.severity] ?? "bg-slate-100"}`}>{error.severity}</span></div><p className="mt-1 truncate text-[11px] text-slate-500">{error.rule_id} · {error.feature_id}</p></button>) : <p className="p-5 text-center text-sm text-emerald-700">{arabic ? "لا توجد أخطاء" : "No errors found"}</p>}
      </div>

      {selected && <div className="p-5"><span className={`rounded px-2 py-1 text-[10px] font-bold ${severityTone[selected.severity] ?? "bg-slate-100"}`}>{selected.severity}</span><h2 className="mt-3 text-lg font-extrabold capitalize text-[#17332f]">{selected.error_type.replaceAll("_", " ")}</h2><p className="mt-2 text-xs leading-6 text-slate-600">{analysis?.explanation ?? selected.details}</p><dl className="mt-4 space-y-2 text-xs"><div className="flex justify-between gap-4"><dt className="text-slate-400">{arabic ? "الطبقة" : "Layer"}</dt><dd className="font-bold">{selected.layer_name}</dd></div><div className="flex justify-between gap-4"><dt className="text-slate-400">{arabic ? "معرف العنصر" : "Feature"}</dt><dd className="font-bold">{selected.feature_id}</dd></div><div className="flex justify-between gap-4"><dt className="text-slate-400">GeoSA</dt><dd className="font-bold">{selected.rule_id}</dd></div></dl><div className="mt-4 rounded-xl bg-[#edf7f3] p-3"><strong className="text-xs text-[#075f50]">{arabic ? "التوصية" : "Recommendation"}</strong><p className="mt-1 text-xs leading-5 text-[#315d54]">{analysis?.recommendation ?? (arabic ? "راجع العنصر وصحح هندسته وفق المعيار." : "Review and correct the feature geometry.")}</p></div></div>}
    </aside>
    <div className="order-1 min-w-0 bg-[#f7f8f5] p-3 xl:order-2"><MapPanel result={result} selectedErrorId={selected ? String(selected.result_id) : selectedErrorId} /></div>
  </section>;
}
