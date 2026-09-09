"use client";

import { useState } from "react";
import { changePassword } from "@/lib/api";
import { useLanguage } from "@/components/LanguageProvider";

export default function SettingsPanel() {
  const { language } = useLanguage();
  const arabic = language === "ar";
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<{ text: string; error: boolean } | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault(); setNotice(null);
    if (newPassword !== confirmation) { setNotice({ text: arabic ? "كلمتا المرور الجديدتان غير متطابقتين." : "New passwords do not match.", error: true }); return; }
    setSaving(true);
    try { await changePassword(currentPassword, newPassword); setCurrentPassword(""); setNewPassword(""); setConfirmation(""); setNotice({ text: arabic ? "تم تغيير كلمة المرور بنجاح." : "Password changed successfully.", error: false }); }
    catch (reason) { setNotice({ text: reason instanceof Error ? reason.message : arabic ? "تعذر تغيير كلمة المرور." : "Password could not be changed.", error: true }); }
    finally { setSaving(false); }
  }

  return <section className="mx-auto w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><h2 className="text-xl font-extrabold text-[#071c33]">{arabic ? "تغيير كلمة المرور" : "Change password"}</h2><p className="mt-1 text-sm text-slate-500">{arabic ? "سيتم تسجيل خروج الجلسات النشطة الأخرى." : "Other active sessions will be signed out."}</p><form onSubmit={submit} className="mt-5 space-y-4"><label className="block text-sm font-semibold">{arabic ? "كلمة المرور الحالية" : "Current password"}<input required type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-3 outline-none focus:border-blue-500" /></label><label className="block text-sm font-semibold">{arabic ? "كلمة المرور الجديدة" : "New password"}<input required minLength={8} type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-3 outline-none focus:border-blue-500" /></label><label className="block text-sm font-semibold">{arabic ? "تأكيد كلمة المرور الجديدة" : "Confirm new password"}<input required minLength={8} type="password" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-3 outline-none focus:border-blue-500" /></label>{notice && <p className={`rounded-xl p-3 text-sm ${notice.error ? "bg-red-50 text-red-700" : "bg-emerald-50 text-emerald-700"}`}>{notice.text}</p>}<button disabled={saving} className="w-full rounded-xl bg-blue-600 py-3 text-sm font-bold text-white disabled:bg-slate-400">{saving ? (arabic ? "جارٍ الحفظ..." : "Saving...") : (arabic ? "تحديث كلمة المرور" : "Update password")}</button></form></section>;
}
