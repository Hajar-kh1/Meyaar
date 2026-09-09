"use client";

// Presents a safe, prioritized remediation queue for every vector file in a folder.

import type { BatchUploadItem } from "@/components/UploadPanel";
import type { RemediationRecord, VectorProcessingResponse } from "@/types/analysis";
import { useLanguage } from "@/components/LanguageProvider";
import { useState } from "react";

const severityRank: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3, warning: 4 };

function vectorItem(item: BatchUploadItem): item is BatchUploadItem & { result: VectorProcessingResponse } {
  return "validation" in item.result;
}

function downloadJson(name: string, content: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(content, null, 2)], { type: "application/geo+json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

export default function FolderRemediation({ items, onOpen, onRecheck }: { items: BatchUploadItem[]; onOpen: (item: BatchUploadItem) => void; onRecheck: (item: BatchUploadItem) => Promise<void> }) {
  const { language } = useLanguage();
  const [filter, setFilter] = useState<"all" | "priority" | "fixable" | "review">("all");
  const [rechecking, setRechecking] = useState<string | null>(null);
  const isArabic = language === "ar";
  const vectors = items.filter(vectorItem);
  const issues = vectors.flatMap((item) => item.result.validation.errors.map((error) => ({ ...error, file: item.file.name, item })));
  const ordered = [...issues].sort((a, b) => (severityRank[a.severity] ?? 9) - (severityRank[b.severity] ?? 9) || a.file.localeCompare(b.file));
  const records = vectors.flatMap((item) => (item.result.analysis.remediation ?? []).map((record) => ({ ...record, file: item.file.name, item })));
  const fixed = records.filter((record) => record.action === "auto_fix" && record.status === "applied");
  const review = records.filter((record) => record.action === "human_review" || record.status === "pending_review" || record.status === "failed");
  const top = ordered[0];
  const filtered = ordered.filter((issue) => {
    const record = records.find((item) => item.result_id === issue.result_id);
    if (filter === "priority") return issue.severity === "critical" || issue.severity === "high";
    if (filter === "fixable") return record?.action === "auto_fix";
    if (filter === "review") return record?.action === "human_review" || record?.status === "failed";
    return true;
  });
  const copy = isArabic ? {
    eyebrow: "إصلاحات المجلد الذكية", title: "ابدأ بالأخطاء الأعلى أولوية", subtitle: "رتّب معيار الأخطاء من جميع الملفات. تُصلح الحالات الآمنة فقط، وتبقى الحالات الهندسية الحساسة للمراجعة.", fixed: "تم إصلاحه تلقائيًا", review: "تحتاج مراجعة", queue: "ترتيب المعالجة", files: "ملفات", errors: "أخطاء", open: "فتح الملف", download: "تنزيل النسخة المعدّلة", original: "ملفك الأصلي لم يتغير", start: "ابدأ بهذا", noIssues: "لم تُكتشف أخطاء في الملفات المتجهة.", manual: "راجعها على الخريطة قبل اتخاذ أي إجراء.", report: "تنزيل تقرير المجلد", recheck: "إعادة فحص النسخة", rechecking: "جارٍ الفحص...", all: "الكل", priority: "High / Critical", fixable: "قابل للإصلاح", beforeAfter: "قبل / بعد" } : {
    eyebrow: "SMART FOLDER REMEDIATION", title: "Start with the highest-priority issues", subtitle: "MEYAAR ranks findings across every file. Only policy-approved fixes are applied; sensitive geometry remains for review.", fixed: "Auto-fixed", review: "Needs review", queue: "Remediation queue", files: "files", errors: "errors", open: "Open file", download: "Download fixed copy", original: "Your uploaded original is unchanged", start: "Start here", noIssues: "No errors were found in the vector files.", manual: "Review these on the map before making a change.", report: "Download folder report", recheck: "Recheck fixed copy", rechecking: "Rechecking...", all: "All", priority: "High / Critical", fixable: "Fixable", beforeAfter: "Before / after" };

  return <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
    <header className="border-b border-slate-200 p-5 sm:p-6"><p className="text-xs font-bold uppercase tracking-[0.18em] text-blue-600">{copy.eyebrow}</p><h2 className="mt-2 text-2xl font-extrabold text-[#071c33]">{copy.title}</h2><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">{copy.subtitle}</p></header>
    <div className="grid gap-3 p-5 sm:grid-cols-3 sm:p-6"><div className="rounded-2xl bg-slate-50 p-4"><b className="text-2xl text-[#071c33]">{vectors.length}</b><p className="mt-1 text-sm text-slate-500">{copy.files}</p></div><div className="rounded-2xl bg-rose-50 p-4"><b className="text-2xl text-rose-700">{issues.length}</b><p className="mt-1 text-sm text-rose-700">{copy.errors}</p></div><div className="rounded-2xl bg-emerald-50 p-4"><b className="text-2xl text-emerald-700">{fixed.length}</b><p className="mt-1 text-sm text-emerald-700">{copy.fixed}</p></div></div>
    {top ? <div className="mx-5 mb-5 rounded-2xl border border-amber-200 bg-amber-50 p-4 sm:mx-6"><p className="text-xs font-bold uppercase tracking-[0.16em] text-amber-700">{copy.start}</p><div className="mt-1 flex flex-wrap items-center justify-between gap-3"><div><b className="text-slate-900">{top.error_type}</b><span className="mx-2 rounded-full bg-amber-200 px-2 py-0.5 text-xs font-bold uppercase text-amber-900">{top.severity}</span><p className="mt-1 text-sm text-slate-600">{top.file} · {(records.find((record) => record.result_id === top.result_id)?.recommended_action || top.details)}</p></div><button type="button" onClick={() => onOpen(top.item)} className="rounded-xl bg-amber-600 px-4 py-2 text-sm font-bold text-white hover:bg-amber-700">{copy.open}</button></div></div> : <p className="px-6 pb-5 text-sm text-emerald-700">{copy.noIssues}</p>}
    <div className="border-t border-slate-100 p-5 sm:p-6"><div className="mb-3 flex flex-wrap items-center justify-between gap-3"><h3 className="font-bold text-[#071c33]">{copy.queue}</h3><div className="flex flex-wrap gap-1">{(["all", "priority", "fixable", "review"] as const).map((value) => <button key={value} type="button" onClick={() => setFilter(value)} className={`rounded-lg px-2.5 py-1 text-xs font-bold ${filter === value ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-600"}`}>{copy[value] || copy.review}</button>)}<button type="button" onClick={() => downloadJson("meyaar-folder-remediation-report.json", { created_at: new Date().toISOString(), files: vectors.map(({ file, result }) => ({ filename: file.name, run_id: result.run_id, errors: result.validation.errors, remediation: result.analysis.remediation ?? [] })) })} className="rounded-lg border border-blue-200 px-2.5 py-1 text-xs font-bold text-blue-700">{copy.report}</button></div></div><div className="space-y-2">{filtered.slice(0, 12).map((issue) => { const remediation = records.find((record) => record.result_id === issue.result_id); const done = remediation?.status === "applied"; return <div key={`${issue.file}-${issue.result_id}`} className="rounded-xl border border-slate-200 p-3"><button type="button" onClick={() => onOpen(issue.item)} className="flex w-full items-center justify-between gap-3 text-start hover:text-blue-700"><span className="min-w-0"><b className="block truncate text-sm text-[#071c33]">{issue.error_type}</b><small className="block truncate text-slate-500">{issue.file} · {issue.feature_id || "Layer"}</small></span><span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-bold ${done ? "bg-emerald-100 text-emerald-700" : issue.severity === "critical" || issue.severity === "high" ? "bg-rose-100 text-rose-700" : "bg-amber-100 text-amber-700"}`}>{done ? copy.fixed : issue.severity}</span></button>{done && <details className="mt-2 text-xs text-slate-500"><summary className="cursor-pointer font-bold text-emerald-700">{copy.beforeAfter}</summary><pre className="mt-2 max-h-28 overflow-auto rounded-lg bg-slate-50 p-2 whitespace-pre-wrap">{JSON.stringify({ before: remediation?.before_state, after: remediation?.after_state }, null, 2)}</pre></details>}</div>; })}</div></div>
    {fixed.length > 0 && <div className="border-t border-slate-100 bg-emerald-50/50 p-5 sm:px-6"><div className="flex flex-wrap items-center justify-between gap-3"><div><b className="text-emerald-900">{fixed.length} {copy.fixed.toLowerCase()}</b><p className="mt-1 text-xs text-emerald-700">{copy.original}</p></div><div className="flex flex-wrap gap-2">{vectors.filter(({ result }) => (result.analysis.remediation ?? []).some((record: RemediationRecord) => record.status === "applied") && result.fixed_layer_geojson).map(({ result, file }) => <div key={file.name} className="flex gap-2"><button type="button" onClick={() => downloadJson(`${file.name.replace(/\.[^.]+$/, "")}-meyaar-fixed.geojson`, result.fixed_layer_geojson)} className="rounded-xl bg-emerald-600 px-3 py-2 text-xs font-bold text-white hover:bg-emerald-700">{copy.download}</button><button type="button" disabled={rechecking === file.name} onClick={async () => { setRechecking(file.name); try { await onRecheck({ result, file, mode: "vector" }); } finally { setRechecking(null); } }} className="rounded-xl border border-emerald-300 px-3 py-2 text-xs font-bold text-emerald-700 disabled:opacity-60">{rechecking === file.name ? copy.rechecking : copy.recheck}</button></div>)}</div></div></div>}
    {review.length > 0 && <p className="border-t border-slate-100 px-5 py-3 text-xs text-slate-500 sm:px-6">{copy.manual}</p>}
  </section>;
}
