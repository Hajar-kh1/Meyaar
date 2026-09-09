"use client";

// Main workspace controller: authentication, navigation, and active analysis state.

import { useEffect, useMemo, useState } from "react";
import AgentChat from "@/components/AgentChat";
import AppSidebar, { type AppView } from "@/components/AppSidebar";
import FilterBar from "@/components/FilterBar";
import LandingPage from "@/components/LandingPage";
import ReportActions from "@/components/ReportActions";
import StatsCards from "@/components/StatsCards";
import UploadPanel from "@/components/UploadPanel";
import FolderRemediation from "@/components/FolderRemediation";
import type { BatchUploadItem } from "@/components/UploadPanel";
import VisionPreview from "@/components/VisionPreview";
import AuthScreen from "@/components/AuthScreen";
import AnalysisHistory from "@/components/AnalysisHistory";
import TeamDashboard from "@/components/TeamDashboard";
import OverallDashboard from "@/components/OverallDashboard";
import TeamOnboarding from "@/components/TeamOnboarding";
import ProfilePanel from "@/components/ProfilePanel";
import SettingsPanel from "@/components/SettingsPanel";
import FirstLoginPassword from "@/components/FirstLoginPassword";
import DisplayControls from "@/components/DisplayControls";
import AnalysisWorkspace from "@/components/AnalysisWorkspace";
import { getAuthToken, getMe, logout, processVectorFile, updatePresence } from "@/lib/api";
import { useLanguage } from "@/components/LanguageProvider";
import type { AuthUser, ProcessingResult, VectorProcessingResponse, VisionAnalysisResponse } from "@/types/analysis";

const viewTitles: Record<AppView, { title: string; description: string }> = {
  dashboard: { title: "Intelligence Dashboard", description: "Live overview of your latest geospatial quality analysis." },
  upload: { title: "Upload Data", description: "Start a new vector or imagery validation workflow." },
  analysis: { title: "Error Analysis", description: "Filter, inspect, and resolve detected quality issues." },
  reports: { title: "Reports", description: "Review the run summary and export audit-ready results." },
  history: { title: "Saved Analyses", description: "Open validation results saved to your account." },
  team: { title: "Team Management", description: "Monitor your team members and their validation activity." },
  profile: { title: "My Profile", description: "Review your personal information and account security." },
  settings: { title: "Settings", description: "Manage your password and account security." },
  assistant: { title: "Meyaar AI Assistant", description: "Ask grounded questions about the current validation run." },
};

function EmptyState({ onUpload }: { onUpload: () => void }) {
  const { t } = useLanguage();
  return <section className="flex min-h-[460px] items-center justify-center rounded-3xl border border-dashed border-slate-300 bg-white p-8 text-center shadow-sm"><div className="max-w-md"><div className="mx-auto flex size-16 items-center justify-center rounded-2xl bg-blue-100 text-3xl text-blue-700">⇧</div><h2 className="mt-5 text-2xl font-bold">{t("No analysis selected")}</h2><p className="mt-2 text-sm leading-6 text-slate-500">{t("Upload vector data or a map image to populate the dashboard with live results.")}</p><button type="button" onClick={onUpload} className="mt-6 rounded-xl bg-blue-600 px-5 py-3 text-sm font-bold text-white hover:bg-blue-700">{t("Upload data")}</button></div></section>;
}

function BatchOverview({ items, onOpen }: { items: BatchUploadItem[]; onOpen: (item: BatchUploadItem) => void }) {
  const errorCount = (item: BatchUploadItem) => "validation" in item.result ? item.result.validation.total_errors : item.result.issues.length;
  const totalErrors = items.reduce((total, item) => total + errorCount(item), 0);
  return <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm"><header className="flex flex-wrap items-end justify-between gap-3 border-b border-slate-200 p-6"><div><p className="text-xs font-bold uppercase tracking-[0.18em] text-blue-600">Folder analysis</p><h2 className="mt-2 text-2xl font-extrabold text-[#071c33]">Uploaded files</h2><p className="mt-1 text-sm text-slate-500">Choose a file to review its errors and recommendations.</p></div><div className="flex gap-2"><span className="rounded-xl bg-blue-50 px-4 py-2 text-sm font-bold text-blue-700">{items.length} files</span><span className="rounded-xl bg-red-50 px-4 py-2 text-sm font-bold text-red-600">{totalErrors} errors</span></div></header><div className="divide-y divide-slate-100">{items.map((item, index) => { const errors = errorCount(item); return <button key={`${item.file.name}-${index}`} type="button" onClick={() => onOpen(item)} className="grid w-full grid-cols-[auto_1fr_auto_auto] items-center gap-4 p-5 text-start transition hover:bg-blue-50/50"><span className="flex size-10 items-center justify-center rounded-xl bg-slate-100 text-lg">{item.mode === "vector" ? "▥" : "▧"}</span><span className="min-w-0"><strong className="block truncate text-[#071c33]">{item.file.name}</strong><small className="text-slate-500">{"validation" in item.result ? item.result.layer_name : "image"}</small></span><span className={`rounded-full px-3 py-1 text-xs font-bold ${errors ? "bg-red-50 text-red-600" : "bg-emerald-50 text-emerald-600"}`}>{errors} {errors === 1 ? "error" : "errors"}</span><span className="font-bold text-blue-600">View →</span></button>; })}</div></section>;
}

export default function Home() {
  const { t } = useLanguage();
  const [entered, setEntered] = useState(false);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [view, setView] = useState<AppView>("dashboard");
  const [result, setResult] = useState<ProcessingResult | null>(null);
  const [selectedErrorId, setSelectedErrorId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [severity, setSeverity] = useState("all");
  const [errorType, setErrorType] = useState("all");
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [batchUploads, setBatchUploads] = useState<BatchUploadItem[]>([]);
  const [showBatchOverview, setShowBatchOverview] = useState(false);

  useEffect(() => {
    if (!getAuthToken()) { Promise.resolve().then(() => setCheckingAuth(false)); return; }
    getMe().then(setUser).catch(() => setUser(null)).finally(() => setCheckingAuth(false));
  }, []);
  useEffect(() => {
    if (!user) return;
    const ping = () => { if (document.visibilityState === "visible") void updatePresence(); };
    ping();
    const interval = window.setInterval(ping, 45_000);
    document.addEventListener("visibilitychange", ping);
    return () => { window.clearInterval(interval); document.removeEventListener("visibilitychange", ping); };
  }, [user]);
  const vectorResult = result && "validation" in result ? result as VectorProcessingResponse : null;
  const displayedResult = useMemo<ProcessingResult | null>(() => {
    if (!vectorResult) return result;
    const needle = search.trim().toLowerCase();
    const errors = vectorResult.validation.errors.filter((error) => {
      const matchesSearch = !needle || [error.error_type, error.feature_id, error.rule_id, error.details].some((value) => value.toLowerCase().includes(needle));
      return matchesSearch && (severity === "all" || error.severity.toLowerCase() === severity) && (errorType === "all" || error.error_type === errorType);
    });
    return { ...vectorResult, validation: { ...vectorResult.validation, total_errors: errors.length, errors } };
  }, [errorType, result, search, severity, vectorResult]);

  function selectError(errorId: string) {
    setSelectedErrorId(errorId);
    setView("analysis");
    window.setTimeout(() => document.getElementById("map-panel")?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
  }

  if (!entered) return <LandingPage onStart={() => setEntered(true)} />;
  if (checkingAuth) return <><main className="flex min-h-screen items-center justify-center bg-[#eef5ff] font-bold text-blue-700">Loading...</main><AgentChat /></>;
  if (!user) return <><AuthScreen onAuthenticated={setUser} /><AgentChat /></>;
  if (user.must_change_password) return <><FirstLoginPassword user={user} onComplete={setUser} onCancel={() => setUser(null)} /><AgentChat /></>;
  if (!user.team_id) return <><TeamOnboarding user={user} onReady={setUser} /><AgentChat /></>;
  const heading = viewTitles[view];

  const filters = vectorResult && <FilterBar result={vectorResult} search={search} severity={severity} errorType={errorType} onSearchChange={setSearch} onSeverityChange={setSeverity} onErrorTypeChange={setErrorType} onClear={() => { setSearch(""); setSeverity("all"); setErrorType("all"); }} />;

  return (
    <div className="min-h-screen bg-background pb-20 text-slate-950 lg:pb-0">
      <AppSidebar user={user} activeView={view} onNavigate={setView} onLogout={async () => { await logout(); setUser(null); setResult(null); }} />
      <div className="lg:pl-[150px] rtl:lg:pl-0 rtl:lg:pr-[150px]">
        <header className="meyaar-app-header sticky top-0 z-[1000] flex min-h-[72px] items-center justify-between gap-4 border-b border-slate-200/80 bg-white/95 px-5 shadow-[0_1px_12px_rgba(15,23,42,0.04)] backdrop-blur-xl lg:px-7"><div className="min-w-0"><h1 className="truncate text-xl font-extrabold tracking-tight text-[#071c33]">{t(heading.title)}</h1><p className="mt-0.5 hidden text-xs text-slate-500 sm:block">{t(heading.description)}</p></div><DisplayControls /></header>
        <main className="mx-auto w-full max-w-[1500px] p-3 sm:p-4 lg:p-5 xl:p-6">
          {view === "upload" && <div className="mx-auto max-w-4xl"><UploadPanel onResult={(newResult, file, mode, batch) => { setBatchUploads(batch); setShowBatchOverview(batch.length > 1); setResult(newResult); setSelectedErrorId(null); setSearch(""); setSeverity("all"); setErrorType("all"); setImageUrl((current) => { if (current) URL.revokeObjectURL(current); return mode === "image" ? URL.createObjectURL(file) : null; }); setView("analysis"); }} /></div>}
          {view !== "dashboard" && view !== "upload" && view !== "history" && view !== "team" && view !== "profile" && view !== "settings" && !result && <EmptyState onUpload={() => setView("upload")} />}

          {view === "dashboard" && <OverallDashboard user={user} refreshKey={result?.analysis_id} onUpload={() => setView("upload")} onTeam={() => setView("team")} onOpen={(savedResult) => { setResult(savedResult); setSelectedErrorId(null); setView("analysis"); }} />}

          {result && view === "analysis" && showBatchOverview && batchUploads.length > 1 && <div className="space-y-6"><FolderRemediation items={batchUploads} onOpen={(item) => { setResult(item.result); setSelectedErrorId(null); setSearch(""); setSeverity("all"); setErrorType("all"); setImageUrl((current) => { if (current) URL.revokeObjectURL(current); return item.mode === "image" ? URL.createObjectURL(item.file) : null; }); setShowBatchOverview(false); }} onRecheck={async (item) => { if (!("fixed_layer_geojson" in item.result) || !item.result.fixed_layer_geojson) return; const nextFile = new File([JSON.stringify(item.result.fixed_layer_geojson)], `${item.file.name.replace(/\.[^.]+$/, "")}-meyaar-fixed.geojson`, { type: "application/geo+json" }); const nextResult = await processVectorFile(nextFile); const nextItem: BatchUploadItem = { file: nextFile, result: nextResult, mode: "vector" }; setBatchUploads((current) => current.map((entry) => entry.file.name === item.file.name ? nextItem : entry)); setResult(nextResult); setSelectedErrorId(null); setShowBatchOverview(false); }} /><BatchOverview items={batchUploads} onOpen={(item) => { setResult(item.result); setSelectedErrorId(null); setSearch(""); setSeverity("all"); setErrorType("all"); setImageUrl((current) => { if (current) URL.revokeObjectURL(current); return item.mode === "image" ? URL.createObjectURL(item.file) : null; }); setShowBatchOverview(false); }} /></div>}
          {result && view === "analysis" && !showBatchOverview && <div className="space-y-4">{batchUploads.length > 1 && <button type="button" onClick={() => setShowBatchOverview(true)} className="rounded-xl border border-blue-200 bg-white px-4 py-2 text-sm font-bold text-blue-700">← Back to uploaded files</button>}{filters}{vectorResult ? <AnalysisWorkspace result={(displayedResult ?? vectorResult) as VectorProcessingResponse} selectedErrorId={selectedErrorId} onSelectError={selectError} /> : <VisionPreview result={result as VisionAnalysisResponse} imageUrl={imageUrl} />}</div>}
          {result && view === "reports" && <div className="space-y-6"><StatsCards result={result} /><ReportActions result={result} /><section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm"><h2 className="text-xl font-bold">Run information</h2><dl className="mt-5 grid gap-4 text-sm sm:grid-cols-2"><div className="rounded-xl bg-slate-50 p-4"><dt className="text-slate-500">File</dt><dd className="mt-1 break-all font-bold">{result.filename}</dd></div><div className="rounded-xl bg-slate-50 p-4"><dt className="text-slate-500">Status</dt><dd className="mt-1 font-bold capitalize">{result.status}</dd></div>{vectorResult && <><div className="rounded-xl bg-slate-50 p-4"><dt className="text-slate-500">Run ID</dt><dd className="mt-1 break-all font-mono text-xs">{vectorResult.run_id}</dd></div><div className="rounded-xl bg-slate-50 p-4"><dt className="text-slate-500">Layer</dt><dd className="mt-1 font-bold capitalize">{vectorResult.layer_name}</dd></div></>}</dl></section></div>}
          {view === "history" && <AnalysisHistory showOwner={user.role === "manager"} onOpen={(savedResult) => { setResult(savedResult); setSelectedErrorId(null); setView("analysis"); }} />}
          {view === "team" && (user.role === "manager" || user.role === "leader" ? <TeamDashboard user={user} onTeamChange={(nextUser) => { setUser(nextUser); setResult(null); setView(nextUser.role === "manager" || nextUser.role === "leader" ? "team" : "dashboard"); }} /> : <TeamOnboarding embedded user={user} onReady={(nextUser) => { setUser(nextUser); setResult(null); setView("team"); }} />)}
          {view === "profile" && <ProfilePanel user={user} />}
          {view === "settings" && <SettingsPanel />}
          {view === "assistant" && (vectorResult ? <AgentChat runId={vectorResult.run_id} embedded /> : result ? <section className="rounded-3xl border border-amber-200 bg-amber-50 p-8 text-center"><h2 className="text-xl font-bold text-amber-950">Assistant requires a vector run</h2><p className="mt-2 text-sm text-amber-800">Upload vector data so the assistant can answer from stored validation results.</p></section> : null)}
        </main>
      </div>
      {view !== "assistant" && <AgentChat runId={vectorResult?.run_id} />}
    </div>
  );
}
