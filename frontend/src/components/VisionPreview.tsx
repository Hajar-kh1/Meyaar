import Image from "next/image";
import { useRef, useState } from "react";
import { useLanguage } from "@/components/LanguageProvider";
import { suggestMapElement } from "@/lib/api";

import type { MissingMapElement, VisionAnalysisResponse } from "@/types/analysis";

interface VisionPreviewProps { result: VisionAnalysisResponse; imageUrl: string | null; }

export default function VisionPreview({ result, imageUrl }: VisionPreviewProps) {
  const { t, language } = useLanguage();
  const [title, setTitle] = useState("");
  const [placement, setPlacement] = useState<"left" | "center" | "right">("center");
  const [showLegend, setShowLegend] = useState(false);
  const [showScale, setShowScale] = useState(false);
  const [showNorthArrow, setShowNorthArrow] = useState(false);
  const [northPosition, setNorthPosition] = useState({ x: 8, y: 15 });
  const [draggingNorth, setDraggingNorth] = useState(false);
  const [choice, setChoice] = useState<Partial<Record<MissingMapElement, "manual" | "agent">>>({});
  const [agentReason, setAgentReason] = useState<Partial<Record<MissingMapElement, string>>>({});
  const [agentLoading, setAgentLoading] = useState<MissingMapElement | null>(null);
  const [agentError, setAgentError] = useState<string | null>(null);
  const imageShellRef = useRef<HTMLDivElement>(null);
  const missingElements = result.elements.filter((element) => !element.present);
  const titleMissing = missingElements.some((element) => element.element === "title");
  const arabic = language === "ar";
  const copy = arabic ? { add: "إكمال عناصر الخريطة", placeholder: "اكتبي عنوان الخريطة", remove: "حذف", download: "تنزيل النسخة المعدّلة", position: "موضع العنوان", left: "يسار", center: "وسط", right: "يمين", note: "هذه معاينة مؤقتة؛ الصورة الأصلية لن تتغير.", legend: "المفتاح", scale: "مقياس الرسم", north: "سهم الشمال", addItem: "إضافة", removeItem: "إزالة", missing: "عناصر ناقصة", none: "كل عناصر الخريطة موجودة", manual: "هل تريد أن تقوم بإصلاحه؟", agent: "أو أقوم أنا بإصلاحه؟", proposed: "اقتراح الإيجنت" } : { add: "Complete map elements", placeholder: "Enter map title", remove: "Remove", download: "Download updated copy", position: "Title position", left: "Left", center: "Center", right: "Right", note: "This is a temporary preview; your original image is unchanged.", legend: "Legend", scale: "Scale", north: "North arrow", addItem: "Add", removeItem: "Remove", missing: "Missing elements", none: "All map elements are present", manual: "Would you like to fix it yourself?", agent: "Or should I suggest a fix?", proposed: "Agent suggestion" };

  const elementLabel = (element: MissingMapElement) => element === "north_arrow" ? copy.north : element === "title" ? "Title" : copy[element];
  async function chooseAgent(element: MissingMapElement) {
    setChoice((current) => ({ ...current, [element]: "agent" })); setAgentLoading(element); setAgentError(null);
    try {
      const response = await suggestMapElement(result.filename, element);
      setAgentReason((current) => ({ ...current, [element]: response.reason }));
      if (element === "title") setTitle(response.suggestion.title || result.filename.replace(/\.[^.]+$/, ""));
      if (element === "legend") setShowLegend(true);
      if (element === "scale") setShowScale(true);
      if (element === "north_arrow") setShowNorthArrow(true);
    } catch (error) { setAgentError(error instanceof Error ? error.message : "The agent could not create a suggestion."); }
    finally { setAgentLoading(null); }
  }

  async function downloadTitledCopy() {
    if (!imageUrl || !title.trim()) return;
    const source = new window.Image();
    source.src = imageUrl;
    await new Promise<void>((resolve, reject) => { source.onload = () => resolve(); source.onerror = () => reject(new Error("Could not load the map image.")); });
    const canvas = document.createElement("canvas");
    const headerHeight = title.trim() ? Math.max(70, Math.round(source.naturalHeight * 0.1)) : 0;
    canvas.width = source.naturalWidth;
    canvas.height = source.naturalHeight + headerHeight;
    const context = canvas.getContext("2d");
    if (!context) return;
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(source, 0, headerHeight);
    const fontSize = Math.max(22, Math.round(canvas.width * 0.038));
    context.font = `700 ${fontSize}px Arial, sans-serif`;
    context.textBaseline = "top";
    const padding = Math.round(fontSize * 0.65);
    const measured = context.measureText(title.trim()).width;
    const x = placement === "left" ? padding : placement === "right" ? canvas.width - measured - padding : (canvas.width - measured) / 2;
    if (title.trim()) { context.fillStyle = "#071c33"; context.fillText(title.trim(), x, Math.max(padding, (headerHeight - fontSize) / 2)); }
    const box = Math.max(14, Math.round(canvas.width * 0.018));
    if (showLegend) {
      const lx = canvas.width - Math.round(canvas.width * 0.22), ly = headerHeight + Math.round(source.naturalHeight * 0.56);
      context.fillStyle = "rgba(255,255,255,0.92)"; context.fillRect(lx, ly, Math.round(canvas.width * 0.18), box * 6);
      context.fillStyle = "#071c33"; context.font = `700 ${box}px Arial, sans-serif`; context.fillText(copy.legend, lx + box, ly + box);
      ["#1d4ed8", "#22c55e", "#f59e0b"].forEach((color, index) => { context.fillStyle = color; context.fillRect(lx + box, ly + box * (index + 2), box, box * 0.65); });
    }
    if (showScale) {
      const sx = Math.round(canvas.width * 0.06), sy = headerHeight + source.naturalHeight - Math.round(source.naturalHeight * 0.08), width = Math.round(canvas.width * 0.18);
      context.strokeStyle = "#071c33"; context.lineWidth = Math.max(2, Math.round(canvas.width * 0.003)); context.beginPath(); context.moveTo(sx, sy); context.lineTo(sx + width, sy); context.moveTo(sx, sy - box / 2); context.lineTo(sx, sy + box / 2); context.moveTo(sx + width, sy - box / 2); context.lineTo(sx + width, sy + box / 2); context.stroke(); context.fillStyle = "#071c33"; context.font = `700 ${box}px Arial, sans-serif`; context.fillText("0                 100 m", sx, sy + box * 1.4);
    }
    if (showNorthArrow) {
      const nx = Math.round(canvas.width * northPosition.x / 100), ny = Math.round(canvas.height * northPosition.y / 100), size = Math.round(canvas.width * 0.035);
      context.fillStyle = "rgba(255,255,255,0.88)"; context.fillRect(nx - size, ny - size * 1.5, size * 2, size * 3.3); context.fillStyle = "#071c33"; context.font = `700 ${box}px Arial, sans-serif`; context.fillText("N", nx - box / 2, ny - size); context.beginPath(); context.moveTo(nx, ny - size * 0.45); context.lineTo(nx - size * 0.45, ny + size * 0.85); context.lineTo(nx, ny + size * 0.48); context.lineTo(nx + size * 0.45, ny + size * 0.85); context.closePath(); context.fill();
    }
    const link = document.createElement("a");
    link.href = canvas.toDataURL("image/png");
    link.download = `${result.filename.replace(/\.[^.]+$/, "")}-with-title.png`;
    link.click();
  }
  return (
    <section className="grid overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm lg:grid-cols-[1.1fr_.9fr]">
      <div className="flex min-h-64 items-center justify-center bg-slate-100 p-3">
        {imageUrl ? <div ref={imageShellRef} onPointerMove={(event) => { if (!draggingNorth || !imageShellRef.current) return; const rect = imageShellRef.current.getBoundingClientRect(); setNorthPosition({ x: Math.min(94, Math.max(6, ((event.clientX - rect.left) / rect.width) * 100)), y: Math.min(92, Math.max(8, ((event.clientY - rect.top) / rect.height) * 100)) }); }} onPointerUp={() => setDraggingNorth(false)} onPointerLeave={() => setDraggingNorth(false)} className="relative max-w-full overflow-hidden rounded-xl shadow">{title.trim() && <div className={`flex h-11 items-center bg-white px-4 text-xs font-extrabold text-[#071c33] sm:text-sm ${placement === "left" ? "justify-start" : placement === "right" ? "justify-end" : "justify-center"}`}>{title}</div>}<Image src={imageUrl} alt={`Uploaded map ${result.filename}`} width={1200} height={800} unoptimized className="max-h-[430px] h-auto max-w-full object-contain" />{showLegend && <div className="absolute right-[7%] top-[56%] rounded bg-white/90 p-2 text-[9px] text-[#071c33] shadow"><b>{copy.legend}</b><span className="mt-1 block text-blue-700">■ Area 1</span><span className="block text-emerald-600">■ Area 2</span><span className="block text-amber-500">■ Area 3</span></div>}{showScale && <div className="absolute bottom-[8%] left-[6%] rounded bg-white/90 px-2 py-1 text-[9px] font-bold text-[#071c33] shadow"><span className="inline-block w-20 border-b-2 border-[#071c33]"/><br/>0　　　 100 m</div>}{showNorthArrow && <div onPointerDown={(event) => { event.preventDefault(); event.currentTarget.setPointerCapture(event.pointerId); setDraggingNorth(true); }} style={{ left: `${northPosition.x}%`, top: `${northPosition.y}%` }} className="absolute z-10 -translate-x-1/2 -translate-y-1/2 cursor-grab touch-none rounded bg-white/90 px-2 py-1 text-center text-sm font-black text-[#071c33] shadow active:cursor-grabbing" title={arabic ? "اسحبي السهم لتغيير موقعه" : "Drag to move the north arrow"}>N<br/>▲</div>}</div> : <p className="text-sm text-slate-500">Image preview unavailable.</p>}
      </div>
      <div className="max-h-[560px] overflow-y-auto p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-600">{t("Vision analysis")}</p>
        <h2 className="mt-1 text-xl font-bold">{t("Map elements")}</h2>
        <div className="mt-3 grid grid-cols-2 gap-1.5 xl:grid-cols-4">
          {Object.entries(result.quality_checks ?? {}).map(([key, value]) => <div key={key} className="rounded-lg bg-slate-50 p-2"><p className="text-[10px] capitalize text-slate-500">{key.replaceAll('_', ' ')}</p><p className="mt-0.5 text-sm font-bold text-slate-900">{value}</p></div>)}
        </div>
        {result.geotiff && <div className="mt-4 rounded-2xl border border-blue-100 bg-blue-50 p-4"><h3 className="font-bold text-blue-950">GeoTIFF</h3>{result.geotiff.available ? <dl className="mt-2 space-y-1 text-xs text-blue-900"><div>CRS: <strong>{result.geotiff.crs ?? 'Missing'}</strong></div><div>Size: <strong>{result.geotiff.width} × {result.geotiff.height}</strong></div><div>Pixel size: <strong>{result.geotiff.pixel_size?.join(' × ')}</strong></div><div>NoData: <strong>{result.geotiff.nodata_ratio ?? 0}%</strong></div><div className="break-all">Bounds: <strong>{result.geotiff.bounds?.join(', ')}</strong></div></dl> : <p className="mt-2 text-xs text-red-700">{result.geotiff.message}</p>}</div>}
        {missingElements.length > 0 && <div className="mt-5 rounded-2xl border border-blue-200 bg-blue-50 p-4"><div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-bold text-blue-950">{copy.add}</h3><span className="rounded-full bg-red-100 px-2 py-1 text-xs font-bold text-red-700">{missingElements.length} {copy.missing}</span></div><p className="mt-1 text-xs text-blue-800">{copy.note}</p>{agentError && <p className="mt-3 rounded-lg bg-red-50 p-2 text-xs text-red-700">{agentError}</p>}<div className="mt-3 space-y-3">{missingElements.map(({ element }) => { const name = element as MissingMapElement; const mode = choice[name]; const shown = name === "title" ? Boolean(title.trim()) : name === "legend" ? showLegend : name === "scale" ? showScale : showNorthArrow; const toggle = name === "legend" ? setShowLegend : name === "scale" ? setShowScale : setShowNorthArrow; return <div key={name} className="rounded-xl border border-blue-100 bg-white p-3"><div className="flex flex-wrap items-center justify-between gap-2"><b className="text-sm text-[#071c33]">{elementLabel(name)}</b>{shown && <button type="button" onClick={() => { if (name === "title") setTitle(""); else toggle(false); }} className="text-xs font-bold text-red-600">{copy.removeItem}</button>}</div>{!mode && <div className="mt-3 grid gap-2 sm:grid-cols-2"><button type="button" onClick={() => setChoice((current) => ({ ...current, [name]: "manual" }))} className="rounded-xl border border-blue-200 px-3 py-2 text-sm font-bold text-blue-700 hover:bg-blue-50">{copy.manual}</button><button type="button" onClick={() => void chooseAgent(name)} className="rounded-xl bg-blue-600 px-3 py-2 text-sm font-bold text-white hover:bg-blue-700">{copy.agent}</button></div>}{mode === "manual" && <div className="mt-3">{name === "title" ? <><input value={title} onChange={(event) => setTitle(event.target.value)} placeholder={copy.placeholder} className="w-full rounded-xl border border-blue-200 px-3 py-2 text-sm outline-none focus:border-blue-500" /><div className="mt-2 flex flex-wrap items-center gap-2"><span className="text-xs font-bold text-blue-900">{copy.position}</span>{(["left", "center", "right"] as const).map((option) => <button key={option} type="button" onClick={() => setPlacement(option)} className={`rounded-lg px-2.5 py-1.5 text-xs font-bold ${placement === option ? "bg-blue-600 text-white" : "bg-slate-50 text-blue-700 ring-1 ring-blue-200"}`}>{copy[option]}</button>)}</div></> : <button type="button" onClick={() => toggle(!shown)} className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-bold text-white">{shown ? copy.removeItem : copy.addItem}</button>}</div>}{mode === "agent" && <div className="mt-3 rounded-lg bg-blue-50 p-2 text-xs text-blue-900"><b>{agentLoading === name ? "…" : copy.proposed}</b><p className="mt-1">{agentReason[name] || (agentLoading === name ? "Preparing a safe preview…" : "")}</p></div>}</div>; })}</div>{(title.trim() || showLegend || showScale || showNorthArrow) && <button type="button" onClick={() => void downloadTitledCopy()} className="mt-4 rounded-xl bg-blue-600 px-3 py-2 text-xs font-bold text-white hover:bg-blue-700">{copy.download}</button>}</div>}
        <div className="mt-5 space-y-3">
          {result.elements.map((element) => (
            <div key={element.element} className="flex items-center justify-between rounded-xl border border-slate-200 px-4 py-3">
              <span className="font-semibold capitalize">{element.element.replaceAll('_', ' ')}</span>
              <span className={`rounded-full px-3 py-1 text-xs font-bold ${element.present ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'}`}>
                {element.present ? t('Present') : t('Missing')}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
