import Image from "next/image";
import { useState } from "react";
import { useLanguage } from "@/components/LanguageProvider";

import type { VisionAnalysisResponse } from "@/types/analysis";

interface VisionPreviewProps { result: VisionAnalysisResponse; imageUrl: string | null; }

export default function VisionPreview({ result, imageUrl }: VisionPreviewProps) {
  const { t, language } = useLanguage();
  const [title, setTitle] = useState("");
  const [placement, setPlacement] = useState<"left" | "center" | "right">("center");
  const [showLegend, setShowLegend] = useState(false);
  const [showScale, setShowScale] = useState(false);
  const [showNorthArrow, setShowNorthArrow] = useState(false);
  const missingElements = result.elements.filter((element) => !element.present);
  const titleMissing = missingElements.some((element) => element.element === "title");
  const arabic = language === "ar";
  const copy = arabic ? { add: "أضيفي عناصر الخريطة", placeholder: "اكتبي عنوان الخريطة", remove: "حذف", download: "تنزيل النسخة المعدّلة", position: "موضع العنوان", left: "يسار", center: "وسط", right: "يمين", note: "هذه معاينة مؤقتة؛ الصورة الأصلية لن تتغير.", legend: "المفتاح", scale: "مقياس الرسم", north: "سهم الشمال", addItem: "إضافة", removeItem: "إزالة", missing: "عناصر ناقصة", none: "كل عناصر الخريطة موجودة" } : { add: "Add map elements", placeholder: "Enter map title", remove: "Remove", download: "Download updated copy", position: "Title position", left: "Left", center: "Center", right: "Right", note: "This is a temporary preview; your original image is unchanged.", legend: "Legend", scale: "Scale", north: "North arrow", addItem: "Add", removeItem: "Remove", missing: "Missing elements", none: "All map elements are present" };

  async function downloadTitledCopy() {
    if (!imageUrl || !title.trim()) return;
    const source = new window.Image();
    source.src = imageUrl;
    await new Promise<void>((resolve, reject) => { source.onload = () => resolve(); source.onerror = () => reject(new Error("Could not load the map image.")); });
    const canvas = document.createElement("canvas");
    canvas.width = source.naturalWidth;
    canvas.height = source.naturalHeight;
    const context = canvas.getContext("2d");
    if (!context) return;
    context.drawImage(source, 0, 0);
    const fontSize = Math.max(22, Math.round(canvas.width * 0.038));
    context.font = `700 ${fontSize}px Arial, sans-serif`;
    context.textBaseline = "top";
    const padding = Math.round(fontSize * 0.65);
    const measured = context.measureText(title.trim()).width;
    const x = placement === "left" ? padding : placement === "right" ? canvas.width - measured - padding : (canvas.width - measured) / 2;
    context.fillStyle = "rgba(255,255,255,0.9)";
    context.fillRect(x - padding / 2, padding / 2, measured + padding, fontSize + padding);
    context.fillStyle = "#071c33";
    context.fillText(title.trim(), x, padding);
    const box = Math.max(14, Math.round(canvas.width * 0.018));
    if (showLegend) {
      const lx = canvas.width - Math.round(canvas.width * 0.22), ly = Math.round(canvas.height * 0.56);
      context.fillStyle = "rgba(255,255,255,0.92)"; context.fillRect(lx, ly, Math.round(canvas.width * 0.18), box * 6);
      context.fillStyle = "#071c33"; context.font = `700 ${box}px Arial, sans-serif`; context.fillText(copy.legend, lx + box, ly + box);
      ["#1d4ed8", "#22c55e", "#f59e0b"].forEach((color, index) => { context.fillStyle = color; context.fillRect(lx + box, ly + box * (index + 2), box, box * 0.65); });
    }
    if (showScale) {
      const sx = Math.round(canvas.width * 0.06), sy = canvas.height - Math.round(canvas.height * 0.08), width = Math.round(canvas.width * 0.18);
      context.strokeStyle = "#071c33"; context.lineWidth = Math.max(2, Math.round(canvas.width * 0.003)); context.beginPath(); context.moveTo(sx, sy); context.lineTo(sx + width, sy); context.moveTo(sx, sy - box / 2); context.lineTo(sx, sy + box / 2); context.moveTo(sx + width, sy - box / 2); context.lineTo(sx + width, sy + box / 2); context.stroke(); context.fillStyle = "#071c33"; context.font = `700 ${box}px Arial, sans-serif`; context.fillText("0                 100 m", sx, sy + box * 1.4);
    }
    if (showNorthArrow) {
      const nx = Math.round(canvas.width * 0.08), ny = Math.round(canvas.height * 0.15), size = Math.round(canvas.width * 0.035);
      context.fillStyle = "rgba(255,255,255,0.88)"; context.fillRect(nx - size, ny - size * 1.5, size * 2, size * 3.3); context.fillStyle = "#071c33"; context.font = `700 ${box}px Arial, sans-serif`; context.fillText("N", nx - box / 2, ny - size); context.beginPath(); context.moveTo(nx, ny - size * 0.45); context.lineTo(nx - size * 0.45, ny + size * 0.85); context.lineTo(nx, ny + size * 0.48); context.lineTo(nx + size * 0.45, ny + size * 0.85); context.closePath(); context.fill();
    }
    const link = document.createElement("a");
    link.href = canvas.toDataURL("image/png");
    link.download = `${result.filename.replace(/\.[^.]+$/, "")}-with-title.png`;
    link.click();
  }
  return (
    <section className="grid overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm lg:grid-cols-2">
      <div className="flex min-h-80 items-center justify-center bg-slate-100 p-5">
        {imageUrl ? <div className="relative max-w-full"><Image src={imageUrl} alt={`Uploaded map ${result.filename}`} width={1200} height={800} unoptimized className="max-h-[520px] h-auto max-w-full rounded-xl object-contain shadow" />{title.trim() && <div className={`absolute top-4 max-w-[calc(100%-2rem)] rounded-md bg-white/90 px-3 py-1.5 text-center text-sm font-extrabold text-[#071c33] shadow-sm sm:text-base ${placement === "left" ? "left-4" : placement === "right" ? "right-4" : "left-1/2 -translate-x-1/2"}`}>{title}</div>}{showLegend && <div className="absolute right-[7%] top-[56%] rounded bg-white/90 p-2 text-[9px] text-[#071c33] shadow"><b>{copy.legend}</b><span className="mt-1 block text-blue-700">■ Area 1</span><span className="block text-emerald-600">■ Area 2</span><span className="block text-amber-500">■ Area 3</span></div>}{showScale && <div className="absolute bottom-[8%] left-[6%] rounded bg-white/90 px-2 py-1 text-[9px] font-bold text-[#071c33] shadow"><span className="inline-block w-20 border-b-2 border-[#071c33]"/><br/>0　　　 100 m</div>}{showNorthArrow && <div className="absolute left-[8%] top-[10%] rounded bg-white/90 px-2 py-1 text-center text-sm font-black text-[#071c33] shadow">N<br/>▲</div>}</div> : <p className="text-sm text-slate-500">Image preview unavailable.</p>}
      </div>
      <div className="p-6">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-blue-600">{t("Vision analysis")}</p>
        <h2 className="mt-2 text-2xl font-bold">{t("Map elements")}</h2>
        <div className="mt-5 grid grid-cols-2 gap-2">
          {Object.entries(result.quality_checks ?? {}).map(([key, value]) => <div key={key} className="rounded-xl bg-slate-50 p-3"><p className="text-xs capitalize text-slate-500">{key.replaceAll('_', ' ')}</p><p className="mt-1 font-bold text-slate-900">{value}</p></div>)}
        </div>
        {result.geotiff && <div className="mt-4 rounded-2xl border border-blue-100 bg-blue-50 p-4"><h3 className="font-bold text-blue-950">GeoTIFF</h3>{result.geotiff.available ? <dl className="mt-2 space-y-1 text-xs text-blue-900"><div>CRS: <strong>{result.geotiff.crs ?? 'Missing'}</strong></div><div>Size: <strong>{result.geotiff.width} × {result.geotiff.height}</strong></div><div>Pixel size: <strong>{result.geotiff.pixel_size?.join(' × ')}</strong></div><div>NoData: <strong>{result.geotiff.nodata_ratio ?? 0}%</strong></div><div className="break-all">Bounds: <strong>{result.geotiff.bounds?.join(', ')}</strong></div></dl> : <p className="mt-2 text-xs text-red-700">{result.geotiff.message}</p>}</div>}
        {missingElements.length > 0 && <div className="mt-5 rounded-2xl border border-blue-200 bg-blue-50 p-4"><div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-bold text-blue-950">{copy.add}</h3><span className="rounded-full bg-red-100 px-2 py-1 text-xs font-bold text-red-700">{missingElements.length} {copy.missing}</span></div><p className="mt-1 text-xs text-blue-800">{copy.note}</p>{titleMissing && <><input value={title} onChange={(event) => setTitle(event.target.value)} placeholder={copy.placeholder} className="mt-3 w-full rounded-xl border border-blue-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500" /><div className="mt-3 flex flex-wrap items-center gap-2"><span className="text-xs font-bold text-blue-900">{copy.position}</span>{(["left", "center", "right"] as const).map((option) => <button key={option} type="button" onClick={() => setPlacement(option)} className={`rounded-lg px-2.5 py-1.5 text-xs font-bold ${placement === option ? "bg-blue-600 text-white" : "bg-white text-blue-700 ring-1 ring-blue-200"}`}>{copy[option]}</button>)}</div></>}{(["legend", "scale", "north_arrow"] as const).filter((name) => missingElements.some((element) => element.element === name)).map((name) => { const shown = name === "legend" ? showLegend : name === "scale" ? showScale : showNorthArrow; const toggle = name === "legend" ? setShowLegend : name === "scale" ? setShowScale : setShowNorthArrow; const label = name === "north_arrow" ? copy.north : copy[name]; return <div key={name} className="mt-3 flex items-center justify-between rounded-xl bg-white px-3 py-2"><span className="text-sm font-bold text-[#071c33]">{label}</span><button type="button" onClick={() => toggle(!shown)} className={`rounded-lg px-3 py-1.5 text-xs font-bold ${shown ? "bg-red-50 text-red-700" : "bg-blue-600 text-white"}`}>{shown ? copy.removeItem : copy.addItem}</button></div>; })}{(title.trim() || showLegend || showScale || showNorthArrow) && <button type="button" onClick={() => void downloadTitledCopy()} className="mt-3 rounded-xl bg-blue-600 px-3 py-2 text-xs font-bold text-white hover:bg-blue-700">{copy.download}</button>}</div>}
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
