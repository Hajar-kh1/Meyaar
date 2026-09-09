"use client";

import Image from "next/image";
import { useLanguage } from "@/components/LanguageProvider";
import type { AuthUser } from "@/types/analysis";

export type AppView = "dashboard" | "team" | "profile" | "upload" | "analysis" | "reports" | "history" | "assistant";

interface AppSidebarProps {
  user: AuthUser;
  activeView: AppView;
  onNavigate: (view: AppView) => void;
  onLogout: () => void | Promise<void>;
}

const items: Array<{ view: AppView; label: string; arabic: string; icon: "home" | "check" | "reports" | "history" }> = [
  { view: "dashboard", label: "Home", arabic: "الرئيسية", icon: "home" },
  { view: "upload", label: "New check", arabic: "فحص جديد", icon: "check" },
  { view: "reports", label: "Reports", arabic: "التقارير", icon: "reports" },
  { view: "history", label: "Saved analyses", arabic: "التحليلات المحفوظة", icon: "history" },
];

function SidebarIcon({ name }: { name: "home" | "check" | "reports" | "history" | "settings" | "logout" }) {
  if (name === "home") return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 11 7-6 7 6v8H5v-8Z"/><path d="M9 19v-5h6v5"/></svg>;
  if (name === "check") return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 5h14v14H5z"/><path d="m8 12 2.5 2.5L16.5 9"/></svg>;
  if (name === "reports") return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 4h12v16H6z"/><path d="M9 8h6M9 12h6M9 16h4"/></svg>;
  if (name === "history") return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 5h14v14H5z"/><path d="M8 9h8M8 13h8M8 17h5"/></svg>;
  if (name === "settings") return <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19 13.5v-3l-2-.7-.8-1.8.9-1.9-2.2-2.2-1.9.9-1.8-.8-.7-2h-3l-.7 2-1.8.8-1.9-.9L.9 6.1 1.8 8 1 9.8l-2 .7v3l2 .7.8 1.8-.9 1.9 2.2 2.2 1.9-.9 1.8.8.7 2h3l.7-2 1.8-.8 1.9.9 2.2-2.2-.9-1.9.8-1.8 2-.7Z" transform="translate(2 0) scale(.83)"/></svg>;
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10 5H5v14h5M14 8l4 4-4 4M18 12H9"/></svg>;
}

export default function AppSidebar({ user, activeView, onNavigate, onLogout }: AppSidebarProps) {
  const { language } = useLanguage();
  const role = user.role === "manager"
    ? (language === "ar" ? "مدير الفريق" : "Manager")
    : user.role === "leader"
      ? (language === "ar" ? "قائد الفريق" : "Team Leader")
      : (language === "ar" ? "محلل بيانات" : "Data Analyst");
  return (
    <aside className="meyaar-app-sidebar fixed inset-x-0 bottom-0 z-[3000] flex shrink-0 flex-col border-e border-[#e1e6e3] bg-[#fdfefc] text-[#17332f] shadow-[0_-8px_30px_rgba(7,45,38,.08)] lg:inset-y-0 lg:left-0 lg:right-auto lg:w-[150px] lg:shadow-[2px_0_18px_rgba(18,60,53,.045)] rtl:lg:left-auto rtl:lg:right-0">
      <div className="meyaar-sidebar-brand hidden h-[96px] shrink-0 items-center justify-center border-b border-[#eef1ef] px-3 lg:flex">
        <span className="meyaar-sidebar-logo relative size-[62px] overflow-hidden rounded-xl"><Image src="/branding/meyaar-version-three-logo.png" alt="شعار معيار" fill sizes="62px" className="meyaar-logo-light object-contain" /><Image src="/branding/meyaar-logo-dark.webp" alt="شعار معيار للوضع الداكن" fill sizes="62px" unoptimized className="meyaar-logo-dark object-contain" /></span>
      </div>
      <nav className="grid grid-cols-4 gap-1 p-2 lg:flex lg:flex-1 lg:flex-col lg:gap-1 lg:overflow-visible lg:px-3 lg:pt-4">
        {items.map((item) => (
          <button key={item.view} type="button" onClick={() => onNavigate(item.view)} className={`flex min-w-0 flex-col items-center gap-1 rounded-lg px-1 py-2 text-[9px] font-medium transition lg:h-[46px] lg:w-full lg:flex-row lg:gap-2.5 lg:px-3 lg:py-0 lg:text-[12px] ${activeView === item.view ? 'bg-[#dcebe5] text-[#006b5a]' : 'text-[#465671] hover:bg-[#edf7f3] hover:text-[#075f50]'}`}>
            <span className="size-4 shrink-0 [&>svg]:size-full [&>svg]:fill-none [&>svg]:stroke-current [&>svg]:stroke-[1.65]"><SidebarIcon name={item.icon} /></span><span className="max-w-full truncate">{language === "ar" ? item.arabic : item.label}</span>
          </button>
        ))}
      </nav>
      <div className="hidden shrink-0 border-t border-[#dfe5e1] px-3 py-4 lg:block">
        <button type="button" onClick={() => onNavigate("profile")} className={`flex h-[42px] w-full items-center gap-2.5 rounded-lg px-3 text-[12px] font-medium ${activeView === "profile" ? "bg-[#dcebe5] text-[#075f50]" : "text-[#465671] hover:bg-[#edf7f3]"}`}><span className="size-4 [&>svg]:size-full [&>svg]:fill-none [&>svg]:stroke-current [&>svg]:stroke-[1.8]"><SidebarIcon name="settings" /></span>{language === "ar" ? "الإعدادات" : "Settings"}</button>
        <button type="button" onClick={() => void onLogout()} className="flex h-[42px] w-full items-center gap-2.5 rounded-lg px-3 text-[12px] font-medium text-[#465671] hover:bg-red-50 hover:text-red-700"><span className="size-4 [&>svg]:size-full [&>svg]:fill-none [&>svg]:stroke-current [&>svg]:stroke-[1.8]"><SidebarIcon name="logout" /></span>{language === "ar" ? "تسجيل الخروج" : "Sign out"}</button>
        <button type="button" onClick={() => onNavigate("profile")} className="meyaar-sidebar-user mt-3 flex w-full items-center gap-2 border-t border-[#dfe5e1] px-1 pt-4 text-start"><span className="flex size-9 shrink-0 items-center justify-center rounded-full border border-[#8fc6b6] bg-[#dcebe5] text-sm font-bold text-[#075f50]">{user.name.trim().charAt(0).toUpperCase()}</span><span className="min-w-0 flex-1"><strong className="block truncate text-[11px] font-bold">{user.name}</strong><small className="mt-0.5 block truncate text-[9px] text-slate-500">{role}</small></span><span className="text-lg text-slate-400 rtl:rotate-180">›</span></button>
      </div>
    </aside>
  );
}
