"use client";

import { createContext, useContext, useEffect, useMemo, useRef, useState } from "react";

export type Language = "en" | "ar";

const translations: Record<string, string> = {
  "Platform": "المنصة",
  "Geospatial AI Platform": "منصة ذكاء اصطناعي جغرافية",
  "How it Works": "كيف تعمل",
  "About": "عن معيار",
  "Validate Geospatial Data.": "تحقق من جودة البيانات الجغرافية.",
  "Make Reliable Decisions.": "اتخذ قرارات موثوقة.",
  "Detect spatial changes, validate map accuracy, identify inconsistencies, and generate AI-powered recommendations across satellite, aerial, and vector data.": "اكتشف التغيّرات المكانية، وتحقق من دقة الخرائط، وحدد حالات عدم الاتساق، وأنشئ توصيات مدعومة بالذكاء الاصطناعي عبر بيانات الأقمار الصناعية والتصوير الجوي والبيانات المتجهة.",
  "Start Validation": "ابدأ الفحص",
  "Explore Capabilities": "استكشف الإمكانات",
  "Change comparison": "مقارنة التغيّرات",
  "Same location, validated with AI": "الموقع نفسه، تم التحقق منه بالذكاء الاصطناعي",
  "Road Change Detected": "تم اكتشاف تغيّر في الطريق",
  "Building Mismatch": "عدم تطابق في المبنى",
  "New road segment": "مقطع طريق جديد",
  "New structure detected": "تم اكتشاف مبنى جديد",
  "Confidence": "الثقة",
  "Change Detection": "اكتشاف التغيّرات",
  "Spatial Validation": "الفحص المكاني",
  "AI Recommendations": "توصيات الذكاء الاصطناعي",
  "Identify real-world changes": "تعرّف على التغيّرات الفعلية",
  "Ensure map accuracy": "تحقق من دقة الخرائط",
  "Generate actionable insights": "أنشئ توصيات قابلة للتنفيذ",
  "Intelligence Dashboard": "لوحة المعلومات الذكية",
  "Interactive Map": "الخريطة التفاعلية",
  "Upload Data": "رفع البيانات",
  "Error Analysis": "تحليل الأخطاء",
  "Reports": "التقارير",
  "Saved Analyses": "التحليلات المحفوظة",
  "My Team": "فريقي",
  "Team Management": "إدارة الفريق",
  "Sign out": "تسجيل الخروج",
  "Personal information": "المعلومات الشخصية",
  "Dashboard": "لوحة التحكم",
  "Map": "الخريطة",
  "Satellite": "الأقمار الصناعية",
  "Analysis": "التحليل",
  "All systems online": "جميع الأنظمة تعمل",
  "Backend offline": "الخادم غير متصل",
  "Checking services": "جارٍ فحص الخدمات",
  "Turn Geospatial Data into": "حوّل البيانات الجغرافية إلى",
  "Reliable Decisions": "قرارات موثوقة",
  "Detect changes, analyze errors, and get AI-powered recommendations across vector and map imagery data.": "اكتشف التغيّرات، وحلّل الأخطاء، واحصل على توصيات ذكية للبيانات المتجهة وصور الخرائط.",
  "Open platform": "فتح المنصة",
  "Upload data": "رفع البيانات",
  "View capabilities": "عرض الإمكانات",
  "Detect errors": "اكتشاف الأخطاء",
  "Explore locations": "استكشاف المواقع",
  "Understand results": "فهم النتائج",
  "Export evidence": "تصدير النتائج",
  "Latest analysis": "آخر تحليل",
  "New analysis": "تحليل جديد",
  "Detected issues": "الأخطاء المكتشفة",
  "Priority findings": "النتائج ذات الأولوية",
  "View all": "عرض الكل",
  "No analysis selected": "لم يتم اختيار تحليل",
  "Upload vector data or a map image to populate the dashboard with live results.": "ارفع بيانات متجهة أو صورة خريطة لعرض نتائج التحليل في لوحة التحكم.",
  "Upload geospatial data": "رفع البيانات الجغرافية",
  "Upload vector data for PostGIS validation or a map image for visual element analysis.": "ارفع بيانات متجهة لفحصها عبر PostGIS أو صورة خريطة لتحليل عناصرها بصريًا.",
  "Vector data": "بيانات متجهة",
  "Map image": "صورة خريطة",
  "Layer type": "نوع الطبقة",
  "Roads": "الطرق",
  "Buildings": "المباني",
  "Select file": "اختيار الملف",
  "Choose a file to upload": "اختر ملفًا للرفع",
  "Start analysis": "بدء التحليل",
  "Analysis overview": "نظرة عامة على التحليل",
  "Result summary": "ملخص النتائج",
  "Total errors": "إجمالي الأخطاء",
  "High priority": "أولوية عالية",
  "Medium priority": "أولوية متوسطة",
  "Human review": "مراجعة بشرية",
  "Elements checked": "العناصر المفحوصة",
  "Elements present": "العناصر الموجودة",
  "Missing elements": "العناصر المفقودة",
  "Completion": "نسبة الاكتمال",
  "Spatial view": "العرض المكاني",
  "Original layer": "الطبقة الأصلية",
  "Errors": "الأخطاء",
  "Reset view": "إعادة ضبط العرض",
  "Search error or Feature ID": "ابحث عن خطأ أو معرّف عنصر",
  "All severities": "كل مستويات الخطورة",
  "All error types": "كل أنواع الأخطاء",
  "Clear": "مسح",
  "Errors and recommendations": "الأخطاء والتوصيات",
  "Review validation details and the recommended corrective actions.": "راجع تفاصيل الفحص والإجراءات التصحيحية المقترحة.",
  "Error": "الخطأ",
  "Feature": "العنصر",
  "Severity": "الخطورة",
  "Details": "التفاصيل",
  "Recommendation": "التوصية",
  "View on map": "عرض على الخريطة",
  "Selected on map": "محدد على الخريطة",
  "Full details": "التفاصيل الكاملة",
  "No errors detected": "لم يتم اكتشاف أخطاء",
  "Export report": "تصدير التقرير",
  "Download structured data or save this page as PDF.": "نزّل البيانات المنظمة أو احفظ الصفحة بصيغة PDF.",
  "Download JSON": "تنزيل JSON",
  "Save as PDF": "حفظ PDF",
  "Download PDF": "تنزيل PDF",
  "Generating PDF...": "جارٍ إنشاء PDF...",
  "Compliance score": "درجة الالتزام",
  "Internal data quality score": "درجة جودة البيانات الداخلية",
  "Internal image quality score": "درجة جودة الصورة الداخلية",
  "Review status": "حالة المراجعة",
  "New": "جديد",
  "Confirmed": "مؤكد",
  "Resolved": "تم الإصلاح",
  "False positive": "نتيجة خاطئة",
  "Add a review comment...": "أضف تعليق المراجعة...",
  "Save review": "حفظ المراجعة",
  "Saving...": "جارٍ الحفظ...",
  "Review saved": "تم حفظ المراجعة",
  "Vision analysis": "التحليل البصري",
  "Map elements": "عناصر الخريطة",
  "Present": "موجود",
  "Missing": "مفقود",
  "AI assistant": "المساعد الذكي",
  "Ask about this analysis": "اسأل عن هذا التحليل",
  "Send": "إرسال",
  "Ask a question about the detected errors...": "اسأل عن الأخطاء المكتشفة...",
  "Answers are grounded in the current validation run. Voice input and playback use your browser.": "تعتمد الإجابات على نتائج الفحص الحالي، ويستخدم الإدخال والنطق الصوتي المتصفح.",
  "Try: “Which errors should I fix first?”": "جرّب: «ما الأخطاء التي يجب أن أصلحها أولًا؟»",
  "Asking...": "جارٍ الإجابة...",
  "Listen": "استماع",
  "Download explanation": "تنزيل الشرح",
  "Download audio": "تنزيل الصوت",
  "Preparing audio...": "جارٍ تجهيز الصوت...",
  "Run information": "معلومات التشغيل",
  "File": "الملف",
  "Status": "الحالة",
  "Layer": "الطبقة",
  "Live overview of your latest geospatial quality analysis.": "نظرة مباشرة على أحدث نتائج جودة البيانات الجغرافية.",
  "Explore detected issues and their spatial context.": "استكشف الأخطاء المكتشفة وسياقها المكاني.",
  "Start a new vector or imagery validation workflow.": "ابدأ فحصًا جديدًا للبيانات المتجهة أو الصور.",
  "Filter, inspect, and resolve detected quality issues.": "صفِّ الأخطاء وافحصها واتخذ الإجراء المناسب لمعالجتها.",
  "Review the run summary and export audit-ready results.": "راجع ملخص التشغيل وصدّر النتائج الجاهزة للتقرير.",
  "Ask grounded questions about the current validation run.": "اطرح أسئلة مرتبطة بنتائج الفحص الحالي.",
  "Monitor your team members and their validation activity.": "تابع أعضاء فريقك وأنشطة الفحص الخاصة بهم.",
  "Team overview": "نظرة عامة على الفريق",
  "My workspace": "مساحة عملي",
  "Welcome": "مرحبًا",
  "Manage teams": "إدارة الفرق",
  "Saved files": "الملفات المحفوظة",
  "Compliance": "نسبة الالتزام",
  "Needs review": "تحتاج مراجعة",
  "Across all analyses": "في جميع التحليلات",
  "Average quality score": "متوسط جودة البيانات",
  "Files with errors": "ملفات تحتوي أخطاء",
  "Usage": "الاستخدام",
  "Quality": "الجودة",
  "Latest": "الأحدث",
  "Vector": "بيانات متجهة",
  "Imagery": "صور",
  "Average": "المتوسط",
  "Best": "الأفضل",
  "No activity": "لا يوجد نشاط",
  "Recent files": "أحدث الملفات",
  "Open a file to view its map, errors and report.": "افتح ملفًا لعرض الأخطاء والتقرير.",
  "Employee": "الموظف",
  "Type": "النوع",
  "Open": "فتح",
  "Opening...": "جارٍ الفتح...",
  "Loading dashboard...": "جارٍ تحميل لوحة التحكم...",
  "No files have been analyzed yet.": "لم يتم تحليل أي ملف بعد.",
  "Upload the first file": "ارفع أول ملف",
  "Vector validation": "فحص البيانات المتجهة",
  "Imagery analysis": "تحليل الصور",
  "Loading...": "جارٍ التحميل...",
  "Sign in": "تسجيل الدخول",
  "Access your analyses and saved geospatial results.": "ادخل إلى تحليلاتك ونتائجك الجغرافية المحفوظة.",
  "Name": "الاسم",
  "Email": "البريد الإلكتروني",
  "Email or username": "البريد الإلكتروني أو اسم المستخدم",
  "Password": "كلمة المرور",
  "Please wait...": "يرجى الانتظار...",
  "Forgot password": "نسيت كلمة المرور",
  "Forgot password?": "نسيت كلمة المرور؟",
  "Enter your email or username to receive a temporary password.": "أدخل بريدك الإلكتروني أو اسم المستخدم لاستلام كلمة مرور مؤقتة.",
  "Send temporary password": "إرسال كلمة مرور مؤقتة",
  "Back to sign in": "العودة إلى تسجيل الدخول",
  "If a matching employee account has a personal email, a temporary password has been sent.": "إذا كان حساب الموظف موجودًا ومرتبطًا ببريد شخصي، فقد تم إرسال كلمة مرور مؤقتة إليه.",
  "New? Create an account": "مستخدم جديد؟ أنشئ حسابًا",
  "Already have an account? Sign in": "لديك حساب؟ سجّل الدخول",
  "Create your private password": "أنشئ كلمة مرور خاصة بك",
  "Temporary password": "كلمة المرور المؤقتة",
  "New password": "كلمة المرور الجديدة",
  "Confirm password": "تأكيد كلمة المرور",
  "Set password and continue": "تعيين كلمة المرور والمتابعة",
  "Manage your teams": "إدارة فرقك",
  "Create your own team or join an existing team. Your role is assigned securely inside each team.": "أنشئ فريقك أو انضم إلى فريق موجود. يتم تعيين صلاحيتك بأمان داخل كل فريق.",
  "Create a team": "إنشاء فريق",
  "You become the Manager": "ستصبح مدير الفريق",
  "Join a team": "الانضمام إلى فريق",
  "You join as a Member": "ستنضم كعضو",
  "Team name": "اسم الفريق",
  "Invitation code": "رمز الدعوة",
  "Create team": "إنشاء الفريق",
  "Join team": "الانضمام للفريق",
  "A Manager can later promote a Member to Team Leader. Users cannot grant themselves elevated permissions.": "يمكن للمدير ترقية العضو إلى قائد فريق لاحقًا، ولا يمكن للمستخدم منح نفسه صلاحيات أعلى.",
  "Personal account information": "معلومات الحساب الشخصية",
  "Current team": "الفريق الحالي",
  "No active team": "لا يوجد فريق نشط",
  "Current role": "الدور الحالي",
  "Teams": "الفرق",
  "My teams": "فرقي",
  "Change password": "تغيير كلمة المرور",
  "Other active sessions will be signed out.": "سيتم تسجيل خروج الجلسات النشطة الأخرى.",
  "Current password": "كلمة المرور الحالية",
  "Confirm new password": "تأكيد كلمة المرور الجديدة",
  "Update password": "تحديث كلمة المرور",
  "Password changed successfully.": "تم تغيير كلمة المرور بنجاح.",
  "New passwords do not match.": "كلمتا المرور الجديدتان غير متطابقتين.",
  "Password could not be changed.": "تعذر تغيير كلمة المرور.",
  "Saved analyses": "التحليلات المحفوظة",
  "Loading saved analyses...": "جارٍ تحميل التحليلات المحفوظة...",
  "Select files to export together.": "حدد الملفات لتصديرها معًا.",
  "Select all": "تحديد الكل",
  "Preparing...": "جارٍ التجهيز...",
  "No saved analyses yet.": "لا توجد تحليلات محفوظة حتى الآن.",
  "Folder analysis": "تحليل المجلد",
  "Uploaded files": "الملفات المرفوعة",
  "Choose a file to review its errors and recommendations.": "اختر ملفًا لمراجعة أخطائه وتوصياته.",
  "View": "عرض",
  "Back to uploaded files": "العودة إلى الملفات المرفوعة",
  "Run ID": "معرّف التشغيل",
  "Assistant requires a vector run": "يتطلب المساعد تحليل بيانات متجهة",
  "Upload vector data so the assistant can answer from stored validation results.": "ارفع بيانات متجهة ليجيب المساعد اعتمادًا على نتائج الفحص المحفوظة.",
  "Choose a folder": "اختر مجلدًا",
  "or": "أو",
  "Home": "الرئيسية",
  "New check": "فحص جديد",
  "Settings": "الإعدادات",
  "Team members": "أعضاء الفريق",
  "Member": "العضو",
  "Role": "الدور",
  "Analyses": "التحليلات",
  "Detected errors": "الأخطاء المكتشفة",
  "Hours": "الساعات",
  "Progress": "التقدم",
  "Joined": "تاريخ الانضمام",
  "Team Leader": "قائد الفريق",
  "Actions": "الإجراءات",
  "Delete": "حذف",
  "Manager": "مدير",
  "Online": "متصل",
  "Offline": "غير متصل",
  "Username account": "حساب باسم مستخدم",
  "Invite employee": "دعوة موظف",
  "Share invitation": "مشاركة الدعوة",
  "Download QR": "تنزيل رمز QR",
  "Cancel": "إلغاء",
  "Delete permanently": "حذف نهائي",
  "Deleting...": "جارٍ الحذف...",
  "Close": "إغلاق",
  "Image preview unavailable.": "معاينة الصورة غير متاحة.",
  "Quality element": "عنصر الجودة",
  "Feature ID": "معرّف العنصر",
  "View all details": "عرض جميع التفاصيل",
  "Show error on map": "عرض الخطأ على الخريطة",
  "No errors found": "لا توجد أخطاء",
  "critical": "حرجة",
  "high": "عالية",
  "medium": "متوسطة",
  "low": "منخفضة",
  "Member name": "اسم العضو",
  "Personal email": "البريد الإلكتروني الشخصي",
  "Choose member": "اختر عضوًا",
  "Edit": "تعديل",
  "Confirm": "تأكيد",
  "Working…": "جارٍ التنفيذ…",
  "Manager workspace": "مساحة عمل المدير",
  "Only your team is visible here.": "يظهر هنا فريقك فقط.",
  "Team management assistant": "مساعد إدارة الفريق",
  "Employee email": "البريد الإلكتروني للموظف",
  "Invite": "إرسال دعوة",
  "Sending...": "جارٍ الإرسال...",
  "Invitation sent successfully.": "تم إرسال الدعوة بنجاح.",
  "Invitation could not be sent.": "تعذر إرسال الدعوة.",
  "Average compliance": "متوسط الالتزام",
  "Managers can promote a Member to Team Leader. Activity is limited to this team.": "يمكن للمدير ترقية العضو إلى قائد فريق. ويقتصر النشاط على هذا الفريق.",
  "Most active employee": "الموظف الأكثر نشاطًا",
  "Try again": "إعادة المحاولة",
  "Loading team dashboard...": "جارٍ تحميل لوحة الفريق...",
  "Team dashboard could not be loaded": "تعذر تحميل لوحة الفريق",
  "Could not load the team.": "تعذر تحميل الفريق.",
  "Back": "رجوع",
  "Create a new team": "إنشاء فريق جديد",
  "You will become the manager and the new team will become active.": "ستصبح مدير الفريق وسيتم تفعيل الفريق الجديد.",
  "Change member role": "تغيير دور العضو",
  "Review the selected member and new role before confirming.": "راجع العضو المحدد والدور الجديد قبل التأكيد.",
  "Select a member": "اختر عضوًا",
  "New role": "الدور الجديد",
  "Confirm role": "تأكيد الدور",
  "Updating...": "جارٍ التحديث...",
  "Team summary": "ملخص الفريق",
  "Members": "الأعضاء",
  "Remove a member from this team": "إزالة عضو من هذا الفريق",
  "The account will remain available, but it will no longer belong to this team.": "سيبقى الحساب متاحًا، لكنه لن يكون تابعًا لهذا الفريق.",
  "Confirm removal": "تأكيد الإزالة",
  "Removing...": "جارٍ الإزالة...",
  "Copy credentials": "نسخ بيانات الدخول",
  "Login email": "بريد تسجيل الدخول",
  "Create and email": "إنشاء الحساب وإرسال البريد",
  "Create account": "إنشاء حساب",
  "Tell the assistant what to do": "أخبر المساعد بما تريد تنفيذه",
  "Arabic and English are supported. Create or delete teams, add or remove members, change roles, list members, or show team statistics. Changes always require confirmation.": "يدعم المساعد العربية والإنجليزية. يمكنك إنشاء الفرق أو حذفها، وإضافة الأعضاء أو إزالتهم، وتغيير الأدوار وعرض إحصاءات الفريق. تتطلب التغييرات تأكيدًا دائمًا.",
  "Understanding request...": "جارٍ فهم الطلب...",
  "Review command": "مراجعة الأمر",
  "Permanent action": "إجراء نهائي",
  "My Profile": "الملف الشخصي",
  "Review your personal information and account security.": "راجع معلوماتك الشخصية وبيانات حسابك.",
  "Manage your password and account security.": "أدر كلمة المرور وأمان حسابك.",
  "This removes the team, its memberships, and all saved analyses belonging to it. This action cannot be undone.": "سيؤدي هذا إلى حذف الفريق وعضوياته وجميع تحليلاته المحفوظة، ولا يمكن التراجع عن هذا الإجراء.",
};

const dynamicTranslations: Array<[RegExp, (match: RegExpMatchArray) => string]> = [
  [/^Welcome, (.+)$/, (match) => `مرحبًا، ${match[1]}`],
  [/^(\d+) files$/, (match) => `${match[1]} ملفات`],
  [/^(\d+) errors?$/, (match) => `${match[1]} أخطاء`],
  [/^(\d+) selected$/, (match) => `تم تحديد ${match[1]}`],
  [/^Scan to join (.+)$/, (match) => `امسح الرمز للانضمام إلى ${match[1]}`],
  [/^Delete (.+)\?$/, (match) => `حذف ${match[1]}؟`],
];

function translatedText(text: string) {
  const direct = translations[text];
  if (direct) return direct;
  for (const [pattern, replace] of dynamicTranslations) {
    const match = text.match(pattern);
    if (match) return replace(match);
  }
  return text;
}

interface LanguageContextValue {
  language: Language;
  direction: "ltr" | "rtl";
  toggleLanguage: () => void;
  t: (text: string) => string;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguage] = useState<Language>("en");
  const direction = language === "ar" ? "rtl" : "ltr";
  const textOriginals = useRef(new WeakMap<Node, string>());
  const attributeOriginals = useRef(new WeakMap<Element, Map<string, string>>());

  useEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.dir = direction;
  }, [direction, language]);

  useEffect(() => {
    const root = document.body;
    const originals = textOriginals.current;
    const savedAttributes = attributeOriginals.current;
    const localize = (scope: Node) => {
      const walker = document.createTreeWalker(scope, NodeFilter.SHOW_TEXT);
      const nodes: Text[] = [];
      while (walker.nextNode()) nodes.push(walker.currentNode as Text);
      if (scope.nodeType === Node.TEXT_NODE) nodes.unshift(scope as Text);
      for (const node of nodes) {
        const parent = node.parentElement;
        if (!parent || parent.closest("script, style, pre, code")) continue;
        const original = originals.get(node) ?? node.data;
        originals.set(node, original);
        const trimmed = original.trim();
        if (!trimmed) continue;
        const next = language === "ar" ? translatedText(trimmed) : trimmed;
        const localized = original.replace(trimmed, next);
        if (node.data !== localized) node.data = localized;
      }
      const elements = scope.nodeType === Node.ELEMENT_NODE
        ? [scope as Element, ...(scope as Element).querySelectorAll("[placeholder], [title], [aria-label]")]
        : [];
      for (const element of elements) {
        const saved = savedAttributes.get(element) ?? new Map<string, string>();
        for (const name of ["placeholder", "title", "aria-label"]) {
          const current = element.getAttribute(name);
          if (!current) continue;
          if (!saved.has(name)) saved.set(name, current);
          const original = saved.get(name)!;
          element.setAttribute(name, language === "ar" ? translatedText(original) : original);
        }
        savedAttributes.set(element, saved);
      }
    };
    localize(root);
    const observer = new MutationObserver((records) => {
      for (const record of records) {
        if (record.type === "characterData") {
          const node = record.target as Text;
          const original = originals.get(node);
          if (original) {
            const trimmed = original.trim();
            const expected = original.replace(trimmed, language === "ar" ? translatedText(trimmed) : trimmed);
            if (node.data !== expected) originals.set(node, node.data);
          }
          localize(node);
        }
        else record.addedNodes.forEach(localize);
      }
    });
    observer.observe(root, { childList: true, subtree: true, characterData: true });
    return () => observer.disconnect();
  }, [language]);

  useEffect(() => {
    const saved = window.localStorage.getItem("meyaar-language");
    if (saved !== "ar" && saved !== "en") return;
    const frame = window.requestAnimationFrame(() => setLanguage(saved));
    return () => window.cancelAnimationFrame(frame);
  }, []);

  const value = useMemo<LanguageContextValue>(() => ({
    language,
    direction,
    toggleLanguage: () => setLanguage((current) => {
      const next = current === "en" ? "ar" : "en";
      window.localStorage.setItem("meyaar-language", next);
      return next;
    }),
    t: (text) => language === "ar" ? translations[text] ?? text : text,
  }), [direction, language]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) throw new Error("useLanguage must be used inside LanguageProvider");
  return context;
}
