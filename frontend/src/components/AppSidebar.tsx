"use client";

import Image from "next/image";
import { useLanguage } from "@/components/LanguageProvider";

export type AppView = "dashboard" | "team" | "profile" | "upload" | "analysis" | "reports" | "history" | "assistant";

interface AppSidebarProps {
  activeView: AppView;
  onNavigate: (view: AppView) => void;
  onLogout: () => void | Promise<void>;
}

const items: Array<{ view: AppView; label: string; arabic: string; icon: string }> = [
  { view: "dashboard", label: "Home", arabic: "الرئيسية", icon: "⌂" },
  { view: "upload", label: "New check", arabic: "فحص جديد", icon: "▱" },
  { view: "reports", label: "Reports", arabic: "التقارير", icon: "▣" },
];

export default function AppSidebar({ activeView, onNavigate, onLogout }: AppSidebarProps) {
  const { language } = useLanguage();
  return (
    <aside className="fixed inset-x-0 bottom-0 z-[3000] flex shrink-0 flex-col border-e border-[#e2e8e4] bg-[#fbfcf9] text-[#17332f] shadow-[0_-8px_30px_rgba(7,45,38,.08)] lg:inset-y-0 lg:left-0 lg:right-auto lg:w-56 lg:shadow-[2px_0_16px_rgba(18,60,53,.05)] rtl:lg:left-auto rtl:lg:right-0">
      <div className="hidden h-[104px] items-center justify-center border-b border-slate-100 px-5 lg:flex">
        <Image src="/branding/meyaar-project-icon.webp" alt="Meyaar project icon" width={62} height={62} className="size-16 object-contain" />
      </div>
      <nav className="grid grid-cols-3 gap-1 p-2 lg:flex lg:flex-1 lg:flex-col lg:gap-1.5 lg:overflow-visible lg:p-4 lg:pt-4">
        {items.map((item) => (
          <button key={item.view} type="button" onClick={() => onNavigate(item.view)} className={`flex min-w-0 flex-col items-center gap-1 rounded-lg px-1 py-2 text-[9px] font-semibold transition lg:w-full lg:flex-row lg:gap-2.5 lg:px-3.5 lg:py-3 lg:text-[13px] ${activeView === item.view ? 'bg-[#dcebe5] text-[#075f50]' : 'text-slate-600 hover:bg-[#edf7f3] hover:text-[#075f50]'}`}>
            <span className="w-5 text-center text-base">{item.icon}</span><span className="max-w-full truncate">{language === "ar" ? item.arabic : item.label}</span>
          </button>
        ))}
      </nav>
      <div className="hidden border-t border-slate-200 p-4 lg:block">
        <button type="button" onClick={() => onNavigate("profile")} className={`flex w-full items-center gap-2.5 rounded-lg px-3.5 py-3 text-[13px] font-semibold ${activeView === "profile" ? "bg-[#dcebe5] text-[#075f50]" : "text-slate-600 hover:bg-[#edf7f3]"}`}><span className="w-5 text-center">⚙</span>{language === "ar" ? "الإعدادات" : "Settings"}</button>
        <button type="button" onClick={() => void onLogout()} className="mt-1 flex w-full items-center gap-2.5 rounded-lg px-3.5 py-3 text-[13px] font-semibold text-slate-600 hover:bg-red-50 hover:text-red-700"><span className="w-5 text-center">⇥</span>{language === "ar" ? "تسجيل الخروج" : "Sign out"}</button>
      </div>
    </aside>
  );
}
