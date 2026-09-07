"use client";

import { useEffect, useMemo, useState } from "react";
import { listAnalyses, loadAnalysis } from "@/lib/api";
import type { AuthUser, ProcessingResult, SavedAnalysisSummary } from "@/types/analysis";
import { useLanguage } from "@/components/LanguageProvider";

interface Props {
  user: AuthUser;
  refreshKey?: string | null;
  onOpen: (result: ProcessingResult) => void;
  onUpload: () => void;
  onTeam: () => void;
}

export default function OverallDashboard({ user, refreshKey, onOpen, onUpload, onTeam }: Props) {
  const { language, t } = useLanguage();
  const [items, setItems] = useState<SavedAnalysisSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [openingId, setOpeningId] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    listAnalyses().then(setItems).catch((reason) => setError(reason instanceof Error ? reason.message : "Could not load dashboard."))
      .finally(() => setLoading(false));
  }, [refreshKey]);

  const summary = useMemo(() => {
    const vectorFiles = items.filter((item) => item.analysis_type === "vector").length;
    const totalErrors = items.reduce((total, item) => total + item.total_errors, 0);
    const scores = items.map((item) => item.compliance_score).filter((score): score is number => score != null);
    const mostUsed = vectorFiles === 0 && items.length === 0 ? t("No activity") : vectorFiles >= items.length - vectorFiles ? t("Vector validation") : t("Imagery analysis");
    const latest = items[0] ?? null;
    return {
      vectorFiles,
      imageFiles: items.length - vectorFiles,
      totalErrors,
      needsReview: items.filter((item) => item.total_errors > 0).length,
      average: scores.length ? Math.round((scores.reduce((total, score) => total + score, 0) / scores.length) * 10) / 10 : null,
      best: scores.length ? Math.max(...scores) : null,
      mostUsed,
      latest,
    };
  }, [items, t]);

  async function open(item: SavedAnalysisSummary) {
    setOpeningId(item.analysis_id); setError("");
    try { onOpen(await loadAnalysis(item.analysis_id)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not open this analysis."); }
    finally { setOpeningId(null); }
  }

  const cards = [
    { label: t("Saved files"), value: items.length, hint: <span><bdi>{summary.vectorFiles}</bdi> {t("Vector")} · <bdi>{summary.imageFiles}</bdi> {t("Imagery")}</span>, color: "text-blue-600", icon: "▤" },
    { label: t("Detected errors"), value: summary.totalErrors, hint: t("Across all analyses"), color: summary.totalErrors ? "text-rose-500" : "text-emerald-600", icon: "!" },
    { label: t("Compliance"), value: summary.average == null ? "—" : `${summary.average}%`, hint: t("Average quality score"), color: "text-blue-600", icon: "✓" },
    { label: t("Needs review"), value: summary.needsReview, hint: t("Files with errors"), color: summary.needsReview ? "text-amber-500" : "text-emerald-600", icon: "◷" },
  ];

  return <div className="space-y-5">
    <section className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-blue-100 bg-gradient-to-r from-white to-blue-50 p-4 shadow-sm">
      <div><p className="text-xs font-bold uppercase tracking-widest text-blue-600">{t(user.role !== "member" ? "Team overview" : "My workspace")}</p><h2 className="mt-1 text-2xl font-extrabold text-[#071c33]">{t("Welcome")}، {user.name}</h2><p className="mt-1 text-sm text-slate-500">{language === "ar" ? (user.role !== "member" ? `ملخص أعمال فريق ${user.team_name}.` : "ملخص تحليلاتك الجغرافية المحفوظة.") : (user.role !== "member" ? `Summary of all work in ${user.team_name}.` : "Summary of all your saved geospatial analyses.")}</p></div>
      <button type="button" onClick={onTeam} className="rounded-xl border border-blue-200 bg-white px-4 py-2.5 text-sm font-bold text-blue-700 hover:bg-blue-50">{t("Manage teams")}</button>
    </section>

    <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">{cards.map((card) => <article key={card.label} className="relative min-h-[102px] rounded-2xl border border-slate-200/80 bg-white p-4 shadow-[0_2px_8px_rgba(15,23,42,0.04)]"><span className="absolute end-3 top-3 flex size-7 items-center justify-center rounded-lg bg-slate-50 text-xs font-bold text-slate-400">{card.icon}</span><p className="pe-8 text-xs font-medium text-slate-500">{card.label}</p><p className={`mt-2 text-2xl font-bold tracking-tight ${card.color}`}>{loading ? "…" : card.value}</p><p className="mt-1 text-[11px] text-slate-400">{card.hint}</p></article>)}</section>

    <section className="grid gap-3 lg:grid-cols-3">
      <article className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-[0_2px_8px_rgba(15,23,42,0.04)]"><div className="flex items-center justify-between"><h3 className="font-semibold text-[#071c33]">{t("Usage")}</h3><span className="rounded-full bg-slate-100 px-3 py-1 text-[11px] font-semibold text-slate-600">{summary.mostUsed}</span></div><div className="mt-5 space-y-4"><div><div className="mb-1.5 flex justify-between text-xs text-slate-600"><span>{t("Vector")}</span><strong>{summary.vectorFiles}</strong></div><div className="h-1.5 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-blue-500" style={{ width: `${items.length ? (summary.vectorFiles / items.length) * 100 : 0}%` }}/></div></div><div><div className="mb-1.5 flex justify-between text-xs text-slate-600"><span>{t("Imagery")}</span><strong>{summary.imageFiles}</strong></div><div className="h-1.5 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-sky-400" style={{ width: `${items.length ? (summary.imageFiles / items.length) * 100 : 0}%` }}/></div></div></div></article>
      <article className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-[0_2px_8px_rgba(15,23,42,0.04)]"><h3 className="font-semibold text-[#071c33]">{t("Quality")}</h3><div className="mt-5 flex items-end justify-between"><div><p className="text-3xl font-bold tracking-tight text-[#071c33]">{summary.average == null ? "—" : `${summary.average}%`}</p><p className="mt-1 text-xs text-slate-500">{t("Average")}</p></div><div className="text-end"><p className="text-lg font-bold text-emerald-600">{summary.best == null ? "—" : `${summary.best}%`}</p><p className="text-[11px] text-slate-400">{t("Best")}</p></div></div><div className="mt-5 h-1.5 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-emerald-500" style={{ width: `${summary.average ?? 0}%` }}/></div></article>
      <article className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-[0_2px_8px_rgba(15,23,42,0.04)]"><h3 className="font-semibold text-[#071c33]">{t("Latest")}</h3>{summary.latest ? <div className="mt-5"><p dir="auto" className="truncate font-semibold text-slate-700">{summary.latest.filename}</p><span className="mt-2 inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium capitalize text-slate-600">{summary.latest.analysis_type === "vector" ? t("Vector") : t("Imagery")}</span><p className={`mt-4 text-xs font-semibold ${summary.latest.total_errors ? "text-rose-500" : "text-emerald-600"}`}>{language === "ar" ? (summary.latest.total_errors ? `${summary.latest.total_errors} أخطاء` : "بلا أخطاء") : (summary.latest.total_errors ? `${summary.latest.total_errors} ${summary.latest.total_errors === 1 ? "error" : "errors"}` : "No errors")}</p></div> : <p className="mt-5 text-sm text-slate-500">{t("No activity")}</p>}</article>
    </section>

    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between gap-4 border-b border-slate-200 p-5"><div><h3 className="text-xl font-bold text-[#071c33]">{t("Recent files")}</h3><p className="mt-1 text-sm text-slate-500">{t("Open a file to view its map, errors and report.")}</p></div><span className="shrink-0 rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-600"><bdi>{items.length}</bdi> {language === "ar" ? "ملف" : "files"}</span></div>
      {error && <p className="m-4 rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {loading ? <p className="p-8 text-center text-slate-500">{t("Loading dashboard...")}</p> : items.length === 0 ? <div className="p-10 text-center"><p className="font-bold text-slate-700">{t("No files have been analyzed yet.")}</p><button type="button" onClick={onUpload} className="mt-4 text-sm font-bold text-blue-600">{t("Upload the first file")} <span aria-hidden="true">→</span></button></div> : <div className="overflow-x-auto"><table className="w-full min-w-[620px] text-sm"><thead className="bg-slate-50 text-slate-500"><tr><th className="p-4 text-start">{t("File")}</th>{user.role !== "member" && <th className="p-4 text-start">{t("Employee")}</th>}<th className="p-4 text-start">{t("Type")}</th><th className="p-4 text-start">{t("Errors")}</th><th className="p-4 text-start">{t("Compliance")}</th><th className="p-4" /></tr></thead><tbody className="divide-y divide-slate-100">{items.slice(0, 10).map((item) => <tr key={item.analysis_id} className="hover:bg-slate-50"><td dir="auto" className="max-w-xs truncate p-4 font-bold">{item.filename}</td>{user.role !== "member" && <td className="p-4 text-slate-600">{item.owner_name}</td>}<td className="p-4 capitalize text-slate-600">{item.analysis_type === "vector" ? t("Vector") : t("Imagery")}</td><td className={`p-4 font-bold ${item.total_errors ? "text-red-600" : "text-emerald-600"}`}>{item.total_errors}</td><td className="p-4 font-bold text-blue-600">{item.compliance_score == null ? "—" : `${item.compliance_score}%`}</td><td className="p-4 text-end"><button type="button" disabled={openingId === item.analysis_id} onClick={() => open(item)} className="font-bold text-blue-600 disabled:text-slate-400">{openingId === item.analysis_id ? t("Opening...") : t("Open")}</button></td></tr>)}</tbody></table></div>}
    </section>
  </div>;
}
