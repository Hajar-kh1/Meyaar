"use client";

import { useState } from "react";
import { forgotPassword, login } from "@/lib/api";
import type { AuthUser } from "@/types/analysis";

export default function AuthScreen({ onAuthenticated }: { onAuthenticated: (user: AuthUser) => void }) {
  const [forgotOpen, setForgotOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault(); setLoading(true); setError("");
    try {
      const response = await login(email, password);
      onAuthenticated(response.user);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Authentication failed."); }
    finally { setLoading(false); }
  }

  async function recover(event: React.FormEvent) {
    event.preventDefault(); setLoading(true); setError(""); setNotice("");
    try { const response = await forgotPassword(email); setNotice(response.message); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Password recovery failed."); }
    finally { setLoading(false); }
  }

  return <main className="flex min-h-screen items-center justify-center bg-[#eef5ff] p-5">
    <section className="w-full max-w-md rounded-3xl border border-blue-100 bg-white p-8 shadow-xl">
      <p className="text-sm font-extrabold uppercase tracking-[.2em] text-blue-600">Meyaar</p>
      <h1 className="mt-3 text-3xl font-extrabold text-[#071c33]">{forgotOpen ? "Forgot password" : "Sign in"}</h1>
      <p className="mt-2 text-sm text-slate-500">{forgotOpen ? "Enter your email or username to receive a temporary password." : "Access your analyses and saved geospatial results."}</p>
      <form onSubmit={forgotOpen ? recover : submit} className="mt-7 space-y-4">
        <label className="block text-sm font-semibold text-slate-700">Email or username<input required type="text" value={email} onChange={(e) => setEmail(e.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-3 outline-none focus:border-blue-500" /></label>
        {!forgotOpen && <label className="block text-sm font-semibold text-slate-700">Password<input required minLength={1} type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-3 outline-none focus:border-blue-500" /></label>}
        {error && <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        {notice && <p className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-700">{notice}</p>}
        <button disabled={loading} className="w-full rounded-xl bg-blue-600 py-3 font-bold text-white disabled:bg-slate-400">{loading ? "Please wait..." : forgotOpen ? "Send temporary password" : "Sign in"}</button>
      </form>
      <button type="button" onClick={() => { setForgotOpen(!forgotOpen); setError(""); setNotice(""); }} className="mt-5 w-full text-sm font-bold text-blue-700">{forgotOpen ? "Back to sign in" : "Forgot password?"}</button>
    </section>
  </main>;
}
