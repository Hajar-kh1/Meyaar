"use client";

import { useEffect, useState } from "react";
import { listTeams } from "@/lib/api";
import type { AuthUser, TeamMembership } from "@/types/analysis";
import { useLanguage } from "@/components/LanguageProvider";

export default function ProfilePanel({ user }: { user: AuthUser }) {
  const { language } = useLanguage();
  const arabic = language === "ar";
  const [teams, setTeams] = useState<TeamMembership[]>([]);
  useEffect(() => { listTeams().then(setTeams).catch(() => setTeams([])); }, []);
  const role = user.role === "manager" ? (arabic ? "مدير الفريق" : "Manager") : user.role === "leader" ? (arabic ? "قائد الفريق" : "Team Leader") : (arabic ? "محلل بيانات" : "Data Analyst");

  return <section className="mx-auto max-w-4xl rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
    <div className="flex items-center gap-4"><div className="flex size-16 items-center justify-center rounded-full bg-blue-600 text-2xl font-black text-white">{user.name.trim().charAt(0).toUpperCase()}</div><div><h2 className="text-2xl font-extrabold text-[#071c33]">{user.name}</h2><p className="text-sm text-slate-500">{arabic ? "معلومات الحساب الشخصية" : "Personal account information"}</p></div></div>
    <dl className="mt-6 grid gap-3 sm:grid-cols-2"><div className="rounded-xl bg-slate-50 p-4"><dt className="text-xs text-slate-500">{arabic ? "البريد الإلكتروني" : "Email"}</dt><dd className="mt-1 break-all font-bold">{user.email}</dd></div><div className="rounded-xl bg-slate-50 p-4"><dt className="text-xs text-slate-500">{arabic ? "الفريق الحالي" : "Current team"}</dt><dd className="mt-1 font-bold">{user.team_name ?? (arabic ? "لا يوجد فريق نشط" : "No active team")}</dd></div><div className="rounded-xl bg-slate-50 p-4"><dt className="text-xs text-slate-500">{arabic ? "الدور الحالي" : "Current role"}</dt><dd className="mt-1 font-bold">{role}</dd></div><div className="rounded-xl bg-slate-50 p-4"><dt className="text-xs text-slate-500">{arabic ? "الفرق" : "Teams"}</dt><dd className="mt-1 font-bold">{teams.length}</dd></div></dl>
    <h3 className="mt-6 font-bold">{arabic ? "فرقي" : "My teams"}</h3><div className="mt-3 flex flex-wrap gap-2">{teams.map((team) => <span key={team.team_id} className={`rounded-full border px-3 py-1.5 text-xs font-bold ${team.team_id === user.team_id ? "border-blue-300 bg-blue-50 text-blue-700" : "border-slate-200 text-slate-600"}`}>{team.name} · {team.role === "leader" ? (arabic ? "قائد الفريق" : "Team Leader") : team.role === "manager" ? (arabic ? "مدير الفريق" : "Manager") : (arabic ? "عضو" : "Member")}</span>)}</div>
  </section>;
}
