"use client";

import Image from "next/image";
import { useLanguage } from "@/components/LanguageProvider";

export type AppView = "dashboard" | "team" | "profile" | "upload" | "analysis" | "reports" | "history" | "assistant";

interface AppSidebarProps {
  activeView: AppView;
  onNavigate: (view: AppView) => void;
}

const items: Array<{ view: AppView; label: string; icon: string }> = [
  { view: "dashboard", label: "Dashboard", icon: "⌂" },
  { view: "upload", label: "Upload Data", icon: "⇧" },
  { view: "analysis", label: "Analysis", icon: "▥" },
  { view: "reports", label: "Reports", icon: "▤" },
  { view: "history", label: "Saved Analyses", icon: "◷" },
];

export default function AppSidebar({ activeView, onNavigate }: AppSidebarProps) {
  const { t } = useLanguage();
  return (
    <aside className="fixed inset-x-0 bottom-0 z-[3000] flex shrink-0 flex-col bg-[#173846] text-white shadow-[0_-8px_30px_rgba(15,42,53,.14)] lg:inset-y-0 lg:left-0 lg:right-auto lg:w-56 lg:shadow-2xl lg:shadow-slate-950/10 rtl:lg:left-auto rtl:lg:right-0">
      <div className="hidden h-[72px] items-center gap-3 border-b border-white/10 px-5 lg:flex">
        <Image src="/branding/meyaar-project-icon.webp" alt="Meyaar project icon" width={38} height={38} className="size-9 rounded-lg bg-white object-contain p-0.5 shadow-md ring-1 ring-white/20" />
        <p className="text-lg font-black tracking-[0.08em] text-white">MEYAAR</p>
      </div>
      <nav className="grid grid-cols-5 gap-1 p-2 lg:flex lg:flex-1 lg:flex-col lg:gap-2 lg:overflow-visible lg:p-4 lg:pt-5">
        {items.map((item) => (
          <button key={item.view} type="button" onClick={() => onNavigate(item.view)} className={`flex min-w-0 flex-col items-center gap-1 rounded-xl px-1 py-2 text-[9px] font-semibold transition lg:w-full lg:flex-row lg:gap-2.5 lg:px-3.5 lg:py-3 lg:text-[13px] ${activeView === item.view ? 'bg-blue-600 text-white shadow-lg shadow-blue-950/20' : 'text-slate-300 hover:bg-white/10 hover:text-white'}`}>
            <span className="w-5 text-center text-base">{item.icon}</span><span className="max-w-full truncate">{t(item.label)}</span>
          </button>
        ))}
      </nav>
      <div className="hidden border-t border-white/10 p-4 text-[11px] text-slate-400 lg:block">Saudi geospatial quality platform</div>
    </aside>
  );
}
