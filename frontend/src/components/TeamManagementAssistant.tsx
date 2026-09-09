"use client";

import { useState } from "react";
import { activateTeam, addExistingTeamMember, createTeam, createTeamUser, deleteTeam, getManagedTeamMemberSummary, getManagedTeamsOverview, getMe, interpretTeamCommands, removeTeamMember, searchUserDirectory, updateTeamMemberRole } from "@/lib/api";
import type { AuthUser, ManagedTeamMemberOverview, ManagedTeamOverview, NewUserPreview, TeamCommandPlan, TeamDashboardData, UserDirectoryEntry } from "@/types/analysis";
import { useLanguage } from "@/components/LanguageProvider";

type Props = { data: TeamDashboardData; onClose: () => void; onComplete: (user: AuthUser) => void };
type VoiceLanguage = "ar" | "en";
type SpeechRecognitionEventLike = { results: ArrayLike<{ 0: { transcript: string } }> };
type SpeechRecognitionLike = { lang: string; continuous: boolean; interimResults: boolean; onresult: ((event: SpeechRecognitionEventLike) => void) | null; onerror: (() => void) | null; onend: (() => void) | null; start: () => void };
type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

// The LLM may use form-like examples for a vague request. They must never become
// real account data; leave the review fields empty and ask the manager instead.
function clearExampleValue(value: string | null | undefined, kind: "name" | "email") {
  const normalized = value?.trim() ?? "";
  const examples = kind === "name"
    ? ["new member name", "member name", "new user", "user name", "name"]
    : ["newmember@example.com", "member@example.com", "email@example.com", "example@example.com"];
  return !normalized || examples.includes(normalized.toLowerCase()) ? null : normalized;
}

// Natural-language requests are converted into a reviewable plan. Nothing changes
// in the team until the manager confirms the actions displayed in the chat.
export default function TeamManagementAssistant({ data, onClose, onComplete }: Props) {
  const { language } = useLanguage();
  const [instruction, setInstruction] = useState("");
  const [sentMessage, setSentMessage] = useState("");
  const [plan, setPlan] = useState<TeamCommandPlan | null>(null);
  const [memberSelections, setMemberSelections] = useState<Record<number, string>>({});
  const [deleteConfirmations, setDeleteConfirmations] = useState<Record<number, string>>({});
  const [directoryMatches, setDirectoryMatches] = useState<Record<number, UserDirectoryEntry[]>>({});
  const [existingSelections, setExistingSelections] = useState<Record<number, string>>({});
  const [createNew, setCreateNew] = useState<Record<number, boolean>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [results, setResults] = useState<string[] | null>(null);
  const [managedTeams, setManagedTeams] = useState<ManagedTeamOverview[] | null>(null);
  const [selectedManagedTeam, setSelectedManagedTeam] = useState<ManagedTeamMemberOverview | null>(null);
  const [listedMembers, setListedMembers] = useState<TeamDashboardData["members"] | null>(null);
  const [voiceLanguage, setVoiceLanguage] = useState<VoiceLanguage>(language === "ar" ? "ar" : "en");
  const [listening, setListening] = useState(false);

  function speak(text: string) {
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const segments = text.match(/[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]+|[A-Za-z]+|[^\u0600-\u06FFA-Za-z]+/g) ?? [text];
    let active: VoiceLanguage = /[\u0600-\u06FF]/.test(text) ? "ar" : "en";
    const grouped: Array<{ text: string; language: VoiceLanguage }> = [];
    for (const token of segments) {
      const tokenLanguage: VoiceLanguage = /[\u0600-\u06FF]/.test(token) ? "ar" : /[A-Za-z]/.test(token) ? "en" : active;
      if (grouped.at(-1)?.language === tokenLanguage) grouped[grouped.length - 1].text += token;
      else grouped.push({ text: token, language: tokenLanguage });
      active = tokenLanguage;
    }
    const voices = window.speechSynthesis.getVoices();
    grouped.filter((segment) => segment.text.trim()).forEach((segment) => {
      const utterance = new SpeechSynthesisUtterance(segment.text);
      utterance.lang = segment.language === "ar" ? "ar-SA" : "en-US";
      utterance.rate = segment.language === "ar" ? 0.92 : 0.96;
      const voice = voices.find((item) => item.lang.toLowerCase().startsWith(segment.language));
      if (voice) utterance.voice = voice;
      window.speechSynthesis.speak(utterance);
    });
  }

  function listen() {
    const browserWindow = window as typeof window & { SpeechRecognition?: SpeechRecognitionConstructor; webkitSpeechRecognition?: SpeechRecognitionConstructor };
    const Recognition = browserWindow.SpeechRecognition ?? browserWindow.webkitSpeechRecognition;
    if (!Recognition) { setError(language === "ar" ? "الإدخال الصوتي غير مدعوم في هذا المتصفح." : "Voice input is not supported by this browser."); return; }
    const recognition = new Recognition();
    recognition.lang = voiceLanguage === "ar" ? "ar-SA" : "en-US";
    recognition.continuous = false; recognition.interimResults = false;
    recognition.onresult = (event) => setInstruction(event.results[0][0].transcript);
    recognition.onerror = () => { setListening(false); setError(language === "ar" ? "تعذر التقاط الصوت، حاولي مرة أخرى." : "Voice input could not be captured. Please try again."); };
    recognition.onend = () => setListening(false);
    setListening(true); recognition.start();
  }

  function candidates(action: NewUserPreview) {
    const available = data.members.filter((member) => member.role !== "manager");
    const needle = (action.email || action.name || "").trim().toLowerCase();
    if (!needle) return available;
    const matches = available.filter((member) =>
      [member.name, member.email || ""].some((value) => value.toLowerCase().includes(needle) || needle.includes(value.toLowerCase())),
    );
    return matches.length ? matches : available;
  }

  async function review(messageOverride?: string) {
    const message = (messageOverride ?? instruction).trim();
    if (!message) return;
    setBusy(true); setError(""); setResults(null); setManagedTeams(null); setSelectedManagedTeam(null); setListedMembers(null); setSentMessage(message);
    try {
      const interpreted = await interpretTeamCommands(message);
      const next = {
        ...interpreted,
        actions: interpreted.actions.map((action) => ({
          ...action,
          name: clearExampleValue(action.name, "name"),
          email: clearExampleValue(action.email, "email"),
        })),
      };
      const selections: Record<number, string> = {};
      next.actions.forEach((action, index) => {
        const matches = candidates(action);
        if ((action.action === "remove" || action.action === "change_role") && matches.length === 1) selections[index] = matches[0].user_id;
      });
      const searches = await Promise.all(next.actions.map(async (action, index) => {
        if (action.action !== "add" || !action.name || action.email) return [index, []] as const;
        try { return [index, await searchUserDirectory(action.name)] as const; }
        catch { return [index, []] as const; }
      }));
      setDirectoryMatches(Object.fromEntries(searches));
      setExistingSelections({});
      setCreateNew({});
      setMemberSelections(selections); setPlan(next); setInstruction("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The assistant could not understand the request.");
    } finally { setBusy(false); }
  }

  function updateAction(index: number, patch: Partial<NewUserPreview>) {
    if (!plan) return;
    setPlan({ ...plan, actions: plan.actions.map((action, actionIndex) => actionIndex === index ? { ...action, ...patch } : action) });
  }

  async function execute() {
    if (!plan) return;
    setBusy(true); setError("");
    const completed: string[] = [];
    try {
      let activeUser = await getMe();
      let activeTeamId = activeUser.team_id;
      for (let index = 0; index < plan.actions.length; index += 1) {
        const action = plan.actions[index];
        if (action.action === "create_team") {
          if (!action.team_name?.trim()) throw new Error(language === "ar" ? "أدخلي اسم الفريق الجديد." : "Enter a name for the new team.");
          await createTeam(action.team_name.trim()); activeUser = await getMe(); activeTeamId = activeUser.team_id;
          completed.push(language === "ar" ? `تم إنشاء فريق: ${action.team_name}` : `Created team: ${action.team_name}`);
        } else if (action.action === "add") {
          const existingId = existingSelections[index];
          if (existingId) {
            if (!activeTeamId) throw new Error(language === "ar" ? "أنشئي فريقًا أو اختاري فريقًا أولًا." : "Create or select a team first.");
            const added = await addExistingTeamMember(activeTeamId, existingId, action.role);
            completed.push(language === "ar" ? `تمت إضافة الحساب الموجود ${added.name} بصفة ${action.role === "leader" ? "قائد فريق" : "عضو"}.` : `Added existing account ${added.name} as ${action.role}.`);
          } else {
            if (!action.name?.trim() || !action.email?.trim()) throw new Error(language === "ar" ? `اختاري حسابًا موجودًا أو أدخلي البريد الشخصي للإجراء ${index + 1}.` : `Choose an existing account or enter a personal email for action ${index + 1}.`);
            const created = await createTeamUser(action);
            completed.push(language === "ar" ? `تم إنشاء حساب ${created.name} وإضافته بصفة ${created.role === "leader" ? "قائد فريق" : "عضو"}، وأُرسلت بيانات الدخول إلى ${created.personal_email}.` : `Created and added ${created.name} as ${created.role}. Credentials were sent privately to ${created.personal_email}.`);
          }
        } else if (action.action === "remove") {
          if (!activeTeamId || !memberSelections[index]) throw new Error(language === "ar" ? `اختاري العضو للإجراء ${index + 1}.` : `Choose the member for action ${index + 1}.`);
          const selected = data.members.find((member) => member.user_id === memberSelections[index]);
          await removeTeamMember(activeTeamId, memberSelections[index]); completed.push(language === "ar" ? `تمت إزالة ${selected?.name ?? "العضو"} من الفريق.` : `Removed ${selected?.name ?? "member"} from the team.`);
        } else if (action.action === "change_role") {
          if (!activeTeamId || !memberSelections[index]) throw new Error(language === "ar" ? `اختاري العضو للإجراء ${index + 1}.` : `Choose the member for action ${index + 1}.`);
          const selected = data.members.find((member) => member.user_id === memberSelections[index]);
          await updateTeamMemberRole(activeTeamId, memberSelections[index], action.role);
          completed.push(language === "ar" ? `تم تغيير دور ${selected?.name ?? "العضو"} إلى ${action.role === "leader" ? "قائد فريق" : "عضو"}.` : `Changed ${selected?.name ?? "member"} to ${action.role === "leader" ? "Team Leader" : "Member"}.`);
        } else if (action.action === "delete_team") {
          if (!activeTeamId) throw new Error(language === "ar" ? "لا يوجد فريق نشط لحذفه." : "No active team to delete.");
          if ((deleteConfirmations[index] ?? "").trim() !== data.team.name) throw new Error(`Type ${data.team.name} to confirm team deletion.`);
          activeUser = await deleteTeam(activeTeamId); activeTeamId = activeUser.team_id; completed.push(language === "ar" ? "تم حذف الفريق النشط." : "Deleted the active team.");
        } else if (action.action === "list_members") {
          setListedMembers(data.members);
          completed.push(language === "ar" ? `يوجد ${data.members.length} عضو في فريق ${data.team.name}.` : `${data.members.length} ${data.members.length === 1 ? "member" : "members"} in ${data.team.name}.`);
        }
        else if (action.action === "team_summary") {
          const teams = await getManagedTeamsOverview();
          setManagedTeams(teams);
          completed.push(language === "ar" ? `تم تحميل ${teams.length} من الفرق التابعة لك.` : `${teams.length} managed ${teams.length === 1 ? "team" : "teams"} loaded.`);
        }
      }
      if (activeTeamId) activeUser = await activateTeam(activeTeamId);
      setResults(completed); onComplete(activeUser);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The plan could not be completed.");
    } finally { setBusy(false); }
  }

  async function openManagedTeam(teamId: string) {
    setBusy(true); setError("");
    try { setSelectedManagedTeam(await getManagedTeamMemberSummary(teamId)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not load this team."); }
    finally { setBusy(false); }
  }

  function resetChat() { setPlan(null); setResults(null); setManagedTeams(null); setSelectedManagedTeam(null); setListedMembers(null); setSentMessage(""); setInstruction(""); setError(""); setDirectoryMatches({}); setExistingSelections({}); setCreateNew({}); }

  const isArabic = language === "ar";
  const copy = isArabic ? {
    title: "مساعد إدارة الفريق", online: "متصل الآن", greeting: "كيف أقدر أساعدك في إدارة الفريق؟", example: "اكتبي طلبك بالعربي أو الإنجليزي، مثل: «أنشئ فريق جودة وأضف سارة كقائدة فريق».", preparing: "جارٍ تجهيز مراجعة طلبك…", completed: "تم تنفيذ الطلب", more: "هل تحتاجين مساعدة أخرى؟", newTask: "مهمة جديدة", end: "إنهاء المحادثة", review: "راجعي الخطة ثم أكدي التنفيذ", placeholder: "اكتبي طلبك لإدارة الفريق…", quick: [
      { title: "إضافة عضو", hint: "عضو أو حساب جديد", prompt: "أضف عضوًا جديدًا إلى الفريق" },
      { title: "إنشاء فريق", hint: "فريق جديد", prompt: "أنشئ فريقًا جديدًا" },
      { title: "تغيير الدور", hint: "تعيين قائد فريق", prompt: "غيّر دور أحد الأعضاء إلى قائد فريق" },
      { title: "إدارة الأعضاء", hint: "عرض أو إزالة عضو", prompt: "اعرض أعضاء الفريق" },
      { title: "ملخص الفريق", hint: "الأداء والتحليلات", prompt: "اعرض ملخص الفريق" },
    ],
  } : {
    title: "Team assistant", online: "Online", greeting: "How can I help manage your team?", example: "Write in English or Arabic, for example: “Create a Quality team and add Sara as Team Leader.”", preparing: "Preparing your review…", completed: "Request completed", more: "Do you need anything else?", newTask: "New task", end: "End chat", review: "Review the plan, then confirm it.", placeholder: "Tell me what you need for the team…", quick: [
      { title: "Add member", hint: "Member or new account", prompt: "Add a new member to the team" },
      { title: "Create team", hint: "Start a new team", prompt: "Create a new team" },
      { title: "Change role", hint: "Assign a Team Leader", prompt: "Change a member role to Team Leader" },
      { title: "Manage members", hint: "View or remove a member", prompt: "List team members" },
      { title: "Team summary", hint: "Performance and analyses", prompt: "Show the team summary" },
    ],
  };

  return (
    <div className="fixed inset-0 z-[6000] flex items-center justify-center bg-slate-950/55 p-3" role="dialog" aria-modal="true">
      <section className="flex h-[min(620px,86vh)] w-full max-w-md flex-col overflow-hidden rounded-2xl bg-[#f4f7fb] shadow-2xl">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
          <div className="flex items-center gap-2.5"><span className="flex size-9 items-center justify-center rounded-full bg-blue-600 text-sm font-black text-white">M</span><div><h2 className="text-sm font-black text-[#071c33]">{copy.title}</h2><p className="flex items-center gap-1.5 text-[11px] text-slate-500"><span className="size-1.5 rounded-full bg-emerald-500" />{copy.online}</p></div></div>
          <button type="button" onClick={onClose} aria-label="Close" className="flex size-9 items-center justify-center rounded-full bg-slate-100 text-xl text-slate-600">×</button>
        </header>

        <div className="flex-1 space-y-3 overflow-y-auto p-4">
          {!sentMessage && <><AssistantBubble><p className="font-bold text-[#071c33]">{copy.greeting}</p><p className="mt-1 text-xs leading-5 text-slate-500">{copy.example}</p></AssistantBubble><div className="ms-10 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">{copy.quick.map((item, index) => <button key={item.title} type="button" disabled={busy} onClick={() => void review(item.prompt)} className={`flex w-full items-center justify-between gap-3 px-4 py-3 text-start transition hover:bg-blue-50 disabled:opacity-60 ${index ? "border-t border-slate-100" : ""}`}><span><span className="block text-sm font-bold text-[#071c33]">{item.title}</span><span className="mt-0.5 block text-[11px] text-slate-500">{item.hint}</span></span><span className="shrink-0 text-lg text-blue-600 rtl:rotate-180">→</span></button>)}</div></>}
          {sentMessage && <div className="flex justify-end"><div className="max-w-[82%] rounded-2xl rounded-tr-sm bg-blue-600 px-4 py-3 text-sm leading-6 text-white">{sentMessage}</div></div>}
          {busy && !plan && <AssistantBubble><p className="text-slate-500">{copy.preparing}</p></AssistantBubble>}

          {plan && <AssistantBubble wide><div className="flex items-start justify-between gap-2"><div><p className="font-semibold text-[#071c33]">{plan.reply ?? plan.summary}</p>{plan.reply && <p className="mt-1 text-xs text-slate-500">{plan.summary}</p>}</div><button type="button" onClick={() => speak(plan.reply ?? plan.summary)} aria-label={isArabic ? "استمع للرد" : "Listen to response"} className="shrink-0 rounded-lg bg-blue-50 px-2 py-1 text-xs text-blue-700">🔊</button></div><div className="mt-3 space-y-2">{plan.actions.map((action, index) => (
            <article key={index} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
              <div className="flex items-center gap-2"><span className="flex size-6 items-center justify-center rounded-full bg-blue-100 text-xs font-black text-blue-700">{index + 1}</span><h3 className="text-sm font-bold capitalize">{action.action.replaceAll("_", " ")}</h3></div>
              {action.action === "create_team" && <input value={action.team_name ?? ""} onChange={(event) => updateAction(index, { team_name: event.target.value })} className="mt-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm" placeholder="Team name" />}
              {action.action === "add" && <div className="mt-2 space-y-2">
                {(directoryMatches[index]?.length ?? 0) > 0 && !createNew[index] && <div className="rounded-lg border border-blue-100 bg-blue-50 p-3"><p className="mb-2 text-xs font-semibold text-blue-800">{isArabic ? `أبشري، لقيت حسابات مطابقة لاسم ${action.name}. أي واحد تقصدين؟` : `I found accounts matching ${action.name}. Which one do you mean?`}</p><div className="space-y-1.5">{directoryMatches[index].map((entry) => <label key={entry.user_id} className="flex cursor-pointer items-center gap-2 rounded-lg bg-white px-3 py-2 text-sm"><input type="radio" name={`existing-${index}`} checked={existingSelections[index] === entry.user_id} onChange={() => setExistingSelections({ ...existingSelections, [index]: entry.user_id })} className="accent-blue-600" /><span><strong>{entry.name}</strong><span className="ms-2 text-slate-500">{entry.email || entry.username}</span></span></label>)}</div><button type="button" onClick={() => { setCreateNew({ ...createNew, [index]: true }); setExistingSelections({ ...existingSelections, [index]: "" }); }} className="mt-2 text-xs font-bold text-blue-700">{isArabic ? "ولا واحد منهم — أنشئ حسابًا جديدًا" : "None of these — create a new account"}</button></div>}
                {((directoryMatches[index]?.length ?? 0) === 0 || createNew[index]) && <><p className="text-xs text-slate-500">{action.name && action.email ? (isArabic ? "راجعي بيانات الحساب قبل التأكيد." : "Review the account details before confirming.") : (isArabic ? `ما لقيت حسابًا مطابقًا. ولا يهمك، أدخلي الاسم والبريد الشخصي${action.name ? ` لـ${action.name}` : ""} وسأنشئ الحساب وأضيفه للفريق.` : "I could not find a matching account. Enter the member’s real name and personal email, and I’ll create a secure account and add it to the team.")}</p><div className="grid gap-2 sm:grid-cols-3"><label className="sr-only" htmlFor={`member-name-${index}`}>{isArabic ? "اسم العضو" : "Member name"}</label><input id={`member-name-${index}`} value={action.name ?? ""} onChange={(event) => updateAction(index, { name: event.target.value })} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm" placeholder={isArabic ? "اسم العضو" : "Member name"} /><label className="sr-only" htmlFor={`member-email-${index}`}>{isArabic ? "البريد الشخصي" : "Personal email"}</label><input id={`member-email-${index}`} type="email" value={action.email ?? ""} onChange={(event) => updateAction(index, { email: event.target.value })} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm" placeholder={isArabic ? "البريد الشخصي" : "Personal email"} /><select aria-label={isArabic ? "دور العضو" : "Member role"} value={action.role} onChange={(event) => updateAction(index, { role: event.target.value as "member" | "leader" })} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"><option value="member">{isArabic ? "عضو" : "Member"}</option><option value="leader">{isArabic ? "قائد فريق" : "Team Leader"}</option></select></div>{createNew[index] && <button type="button" onClick={() => setCreateNew({ ...createNew, [index]: false })} className="text-xs font-bold text-slate-500">{isArabic ? "العودة للحسابات المطابقة" : "Back to matching accounts"}</button>}</>}
              </div>}
              {(action.action === "remove" || action.action === "change_role") && <div className="mt-2 grid gap-2 sm:grid-cols-2"><select required value={memberSelections[index] ?? ""} onChange={(event) => setMemberSelections({ ...memberSelections, [index]: event.target.value })} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"><option value="">Choose member</option>{candidates(action).map((member) => <option key={member.user_id} value={member.user_id}>{member.name} — {member.email}</option>)}</select>{action.action === "change_role" && <select value={action.role} onChange={(event) => updateAction(index, { role: event.target.value as "member" | "leader" })} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"><option value="member">Member</option><option value="leader">Team Leader</option></select>}</div>}
              {action.action === "delete_team" && <div className="mt-2"><p className="text-xs font-semibold text-red-600">This permanently deletes the active team and its analyses.</p><input value={deleteConfirmations[index] ?? ""} onChange={(event) => setDeleteConfirmations({ ...deleteConfirmations, [index]: event.target.value })} className="mt-2 w-full rounded-lg border border-red-200 bg-white px-3 py-2 text-sm" placeholder={`Type ${data.team.name} to confirm`} /></div>}
            </article>
          ))}</div>{!results && <div className="mt-3 flex justify-end gap-2"><button type="button" onClick={resetChat} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-bold text-slate-600">Edit</button><button type="button" disabled={busy} onClick={() => void execute()} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-bold text-white disabled:bg-slate-400">{busy ? "Working…" : "Confirm"}</button></div>}</AssistantBubble>}

          {results && <AssistantBubble><div className="flex items-center justify-between gap-2"><p className="font-bold text-emerald-700">{copy.completed}</p><button type="button" onClick={() => speak([copy.completed, ...results].join(". "))} aria-label={isArabic ? "استمع للنتيجة" : "Listen to result"} className="rounded-lg bg-blue-50 px-2 py-1 text-xs text-blue-700">🔊</button></div><ul className="mt-2 space-y-1.5">{results.map((result, index) => <li key={`${index}-${result}`}>• {result}</li>)}</ul>{listedMembers && <div className="mt-3 overflow-hidden rounded-xl border border-slate-200 bg-white"><div className="border-b border-slate-100 px-3 py-2 text-xs font-bold text-[#071c33]">{isArabic ? "أعضاء الفريق" : "Team members"}</div>{listedMembers.map((member) => <div key={member.user_id} className="flex items-center justify-between gap-2 border-b border-slate-100 px-3 py-2.5 last:border-0"><div className="min-w-0"><p className="truncate text-xs font-bold text-[#071c33]">{member.name}</p><p className="truncate text-[11px] text-slate-500">{member.email || "Username account"}</p></div><div className="shrink-0 text-end"><span className="rounded-full bg-blue-50 px-2 py-1 text-[10px] font-bold text-blue-700">{member.role === "leader" ? "Team Leader" : member.role}</span><p className={`mt-1 text-[10px] font-semibold ${member.is_online ? "text-emerald-600" : "text-slate-400"}`}>{member.is_online ? (isArabic ? "متصل" : "Online") : (isArabic ? "غير متصل" : "Offline")}</p></div></div>)}</div>}{managedTeams && <div className="mt-3 overflow-hidden rounded-xl border border-slate-200 bg-white"><div className="border-b border-slate-100 px-3 py-2 text-xs font-bold text-[#071c33]">{isArabic ? "الفرق التابعة لك — اختاري فريقًا" : "Your teams — select one"}</div>{managedTeams.length ? managedTeams.map((team) => <button key={team.team_id} type="button" disabled={busy} onClick={() => void openManagedTeam(team.team_id)} className={`block w-full border-b border-slate-100 px-3 py-2.5 text-start last:border-0 hover:bg-blue-50 disabled:opacity-60 ${selectedManagedTeam?.team.team_id === team.team_id ? "bg-blue-50" : ""}`}><span className="flex items-center justify-between gap-2"><strong className="text-xs text-[#071c33]">{team.name}</strong><span className="text-[11px] font-bold text-blue-700">{team.average_compliance ?? "—"}%</span></span><span className="mt-1 block text-[11px] text-slate-500">{team.members_count} {isArabic ? "أعضاء" : "members"} · {team.analyses_count} {isArabic ? "تحليلات" : "analyses"} · {team.total_errors} {isArabic ? "أخطاء" : "errors"}</span></button>) : <p className="px-3 py-3 text-xs text-slate-500">{isArabic ? "لا توجد فرق مملوكة." : "No managed teams found."}</p>}</div>}{selectedManagedTeam && <div className="mt-3 overflow-hidden rounded-xl border border-blue-200 bg-white"><div className="border-b border-blue-100 bg-blue-50 px-3 py-2 text-xs font-bold text-blue-800">{selectedManagedTeam.team.name} · {isArabic ? "ملخص الأعضاء" : "Member activity"}</div>{selectedManagedTeam.members.map((member) => <div key={member.user_id} className="border-b border-slate-100 px-3 py-2.5 last:border-0"><div className="flex items-center justify-between gap-2"><div className="min-w-0"><p className="truncate text-xs font-bold text-[#071c33]">{member.name}</p><p className="truncate text-[11px] text-slate-500">{member.email || "Username account"}</p></div><span className={`size-2 rounded-full ${member.is_online ? "bg-emerald-500" : "bg-slate-300"}`} title={member.is_online ? "Online" : "Offline"} /></div><p className="mt-1.5 text-[11px] text-slate-600"><bdi>{member.analyses_count}</bdi> {isArabic ? "تحليلات" : "analyses"} · <bdi>{member.total_errors}</bdi> {isArabic ? "أخطاء" : "errors"} · <bdi>{member.average_compliance ?? "—"}%</bdi> {isArabic ? "التزام" : "compliance"}</p></div>)}</div>}<div className="mt-4 rounded-xl bg-slate-50 p-3"><p className="font-semibold text-[#071c33]">{copy.more}</p><div className="mt-3 flex flex-wrap gap-2"><button type="button" onClick={resetChat} className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-bold text-white">{copy.newTask}</button><button type="button" onClick={onClose} className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-bold text-slate-600">{copy.end}</button></div></div></AssistantBubble>}
          {error && <div className="ml-11 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
        </div>

        <form onSubmit={(event) => { event.preventDefault(); void review(); }} className="border-t border-slate-200 bg-white p-3"><div className="flex items-end gap-2 rounded-xl border border-slate-300 p-2 focus-within:border-blue-500"><textarea rows={1} disabled={Boolean(plan) || Boolean(results)} value={instruction} onChange={(event) => setInstruction(event.target.value)} className="max-h-28 min-h-9 flex-1 resize-none px-2 py-1.5 text-sm outline-none disabled:bg-white" placeholder={plan ? copy.review : results ? copy.more : copy.placeholder} /><select value={voiceLanguage} onChange={(event) => setVoiceLanguage(event.target.value as VoiceLanguage)} aria-label={isArabic ? "لغة الإدخال الصوتي" : "Voice input language"} className="h-9 rounded-lg border border-slate-200 bg-slate-50 px-1 text-[10px] font-bold"><option value="ar">AR</option><option value="en">EN</option></select><button type="button" onClick={listen} disabled={Boolean(plan) || Boolean(results) || listening} aria-label={isArabic ? "إدخال صوتي" : "Voice input"} className={`flex size-9 shrink-0 items-center justify-center rounded-lg border border-slate-200 ${listening ? "animate-pulse bg-red-50" : "bg-slate-50"}`}>🎙️</button><button type="submit" disabled={busy || Boolean(plan) || Boolean(results) || !instruction.trim()} aria-label="Send" className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-blue-600 text-base text-white disabled:bg-slate-300">↑</button></div></form>
      </section>
    </div>
  );
}

function AssistantBubble({ children, wide = false }: { children: React.ReactNode; wide?: boolean }) {
  const { direction } = useLanguage();
  return <div className="flex gap-2.5"><span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-blue-600 text-xs font-black text-white">M</span><div className={`${wide ? "w-full max-w-[94%]" : "max-w-[88%]"} rounded-2xl ${direction === "rtl" ? "rounded-tr-sm" : "rounded-tl-sm"} bg-white px-4 py-3 text-sm leading-6 text-slate-600 shadow-sm`}>{children}</div></div>;
}
