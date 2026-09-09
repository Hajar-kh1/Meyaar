"use client";

import { useEffect, useState } from "react";
import { useLanguage } from "@/components/LanguageProvider";

// One shared language and appearance control used across public and app headers.
export default function DisplayControls() {
  const { language, toggleLanguage } = useLanguage();
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const saved = window.localStorage.getItem("meyaar-theme");
    const enabled = saved ? saved === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.classList.toggle("dark", enabled);
    const frame = window.requestAnimationFrame(() => setDark(enabled));
    return () => window.cancelAnimationFrame(frame);
  }, []);

  function toggleTheme() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    window.localStorage.setItem("meyaar-theme", next ? "dark" : "light");
  }

  return <div className={`flex h-10 items-center gap-1 rounded-full border p-1 shadow-sm backdrop-blur transition-colors ${dark ? "border-[#365965] bg-[#17333e]" : "border-[#d4e2e7] bg-[#edf6f8]"}`}>
    <button type="button" onClick={toggleTheme} title={dark ? "Light mode" : "Dark mode"} aria-label={dark ? "Switch to light mode" : "Switch to dark mode"} className={`flex size-8 items-center justify-center rounded-full text-lg transition ${dark ? "text-[#edf6f8] hover:bg-white/10" : "text-[#18333e] hover:bg-white"}`}>{dark ? "☀" : "☾"}</button>
    <span className={`h-4 w-px ${dark ? "bg-white/15" : "bg-[#b9ccd3]"}`} />
    <button type="button" onClick={toggleLanguage} aria-label={language === "en" ? "Switch to Arabic" : "Switch to English"} className={`min-w-9 rounded-full px-2 py-1 text-xs font-black transition ${dark ? "text-[#edf6f8] hover:bg-white/10" : "text-[#18333e] hover:bg-white"}`}>{language === "en" ? "AR" : "EN"}</button>
  </div>;
}
