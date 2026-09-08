"use client";

// Handles single files and folders, including progress and automatic layer detection.

import { useEffect, useRef, useState } from "react";

import {
  analyzeMapImage,
  processVectorFile,
} from "@/lib/api";

import type {
  ProcessingResult,
} from "@/types/analysis";
import { useLanguage } from "@/components/LanguageProvider";


interface UploadPanelProps {
  onResult: (
    result: ProcessingResult,
    file: File,
    mode: UploadMode,
    batch: BatchUploadItem[],
  ) => void;
}


type UploadMode = "vector" | "image";
export interface BatchUploadItem { result: ProcessingResult; file: File; mode: UploadMode; }

function detectUploadMode(file: File): UploadMode | null {
  const name = file.name.toLowerCase();
  if (/\.(png|jpe?g|tiff?)$/.test(name)) return "image";
  if (/\.(geojson|json|gpkg|csv|parquet|zip)$/.test(name) && !/\.(png|jpe?g|tiff?|webp)\.json$/.test(name)) return "vector";
  return null;
}

async function splitMixedGeoJson(files: File[]): Promise<File[]> {
  const expanded: File[] = [];
  for (const file of files) {
    if (!/\.geo?json$/i.test(file.name)) { expanded.push(file); continue; }
    try {
      const collection = JSON.parse(await file.text()) as { type?: string; features?: Array<{ geometry?: { type?: string } | null }>; [key: string]: unknown };
      if (collection.type !== "FeatureCollection" || !Array.isArray(collection.features)) { expanded.push(file); continue; }
      const roads = collection.features.filter((feature) => /LineString$/i.test(feature.geometry?.type ?? ""));
      const buildings = collection.features.filter((feature) => /Polygon$/i.test(feature.geometry?.type ?? ""));
      const unsupported = collection.features.length - roads.length - buildings.length;
      if (!roads.length || !buildings.length || unsupported > 0) { expanded.push(file); continue; }
      const base = file.name.replace(/\.geo?json$/i, "");
      expanded.push(new File([JSON.stringify({ ...collection, name: `${base}_roads`, features: roads })], `${base}_roads.geojson`, { type: "application/geo+json" }));
      expanded.push(new File([JSON.stringify({ ...collection, name: `${base}_buildings`, features: buildings })], `${base}_buildings.geojson`, { type: "application/geo+json" }));
    } catch { expanded.push(file); }
  }
  return expanded;
}


export default function UploadPanel({
  onResult,
}: UploadPanelProps) {
  const { t } = useLanguage();
  const [files, setFiles] = useState<File[]>([]);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const [progress, setProgress] = useState(0);
  const [currentFile, setCurrentFile] = useState(0);

  const [isLoading, setIsLoading] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    if (!isLoading) return;
    const timer = window.setInterval(
      () => setElapsedSeconds((value) => value + 1),
      1000,
    );
    return () => window.clearInterval(timer);
  }, [isLoading]);

  useEffect(() => { folderInputRef.current?.setAttribute("webkitdirectory", ""); }, []);


  const acceptedFormats = ".geojson,.json,.gpkg,.csv,.parquet,.zip,.png,.jpg,.jpeg,.tif,.tiff";


  async function handleSubmit(
    event: React.FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (!files.length) {
      setError("Select a file or folder before starting the analysis.");
      return;
    }

    const oversized = files.find((item) => item.size > (detectUploadMode(item) === "vector" ? 500 : 100) * 1024 * 1024);
    if (oversized) {
      setError(`${oversized.name} exceeds the ${detectUploadMode(oversized) === "vector" ? 500 : 100} MB limit.`);
      return;
    }

    setElapsedSeconds(0);
    setIsLoading(true);
    setProgress(0);
    setCurrentFile(0);
    setError(null);

    try {
      const workingFiles = await splitMixedGeoJson(files);
      if (workingFiles.length !== files.length) setFiles(workingFiles);
      let finalResult: ProcessingResult | null = null;
      const completed: BatchUploadItem[] = [];
      for (let index = 0; index < workingFiles.length; index += 1) {
        const selectedFile = workingFiles[index];
        const mode = detectUploadMode(selectedFile);
        if (!mode) throw new Error(`${selectedFile.name} is not a supported vector or image file.`);
        setCurrentFile(index);
        const updateProgress = (filePercent: number) => setProgress(Math.round(((index + filePercent / 100) / workingFiles.length) * 100));
        finalResult = mode === "vector"
          ? await processVectorFile(selectedFile, undefined, updateProgress)
          : await analyzeMapImage(selectedFile, updateProgress);
        completed.push({ result: finalResult, file: selectedFile, mode });
      }
      const finalFile = workingFiles[workingFiles.length - 1];
      const finalMode = detectUploadMode(finalFile);
      if (finalResult && finalMode) onResult(finalResult, finalFile, finalMode, completed);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The analysis request failed.",
      );
    } finally {
      setIsLoading(false);
    }
  }

  if (isLoading) {
    const steps = [
      { label: "قراءة البيانات", at: 5 },
      { label: "اكتشاف نوع الطبقة", at: 18 },
      { label: "فحص الهندسة والطوبولوجيا", at: 38 },
      { label: "تقييم جودة البيانات", at: 62 },
      { label: "مطابقة متطلبات GeoSA", at: 82 },
      { label: "إعداد النتائج", at: 98 },
    ];
    return <section dir="rtl" className="overflow-hidden rounded-2xl border border-[#dfe5e1] bg-white shadow-sm">
      <div className="grid min-h-[590px] lg:grid-cols-[240px_minmax(0,1fr)_280px]">
        <aside className="border-e border-slate-200 p-6">
          <div className="space-y-5">{steps.map((step) => <div key={step.label} className={`flex items-center gap-3 text-sm ${progress >= step.at ? "font-bold text-[#075f50]" : "text-slate-400"}`}><span className={`flex size-5 items-center justify-center rounded-full text-[10px] ${progress >= step.at ? "bg-[#0b806c] text-white" : "border border-slate-300 bg-white"}`}>{progress >= step.at ? "✓" : ""}</span>{step.label}</div>)}</div>
          <button type="button" disabled className="mt-16 w-full rounded-lg border border-slate-300 py-2.5 text-sm font-bold text-slate-500">إلغاء الفحص</button>
        </aside>
        <div className="flex flex-col justify-center p-6 text-center">
          <h2 className="text-2xl font-extrabold text-[#17332f]">جاري فحص البيانات...</h2><p className="mt-2 text-sm text-slate-500">يقوم المحلل بفحص بياناتك باستخدام محرك معيار</p>
          <div className="relative mx-auto mt-6 aspect-square w-full max-w-[330px] overflow-hidden rounded-xl border border-[#dce7e2] bg-[#eff5f1]"><div className="absolute inset-0 opacity-60 [background-image:linear-gradient(32deg,transparent_46%,#75a99a_47%,#75a99a_49%,transparent_50%),linear-gradient(145deg,transparent_45%,#b8cfc7_46%,#b8cfc7_48%,transparent_49%),repeating-linear-gradient(90deg,transparent_0_34px,#cbdcd6_35px_36px),repeating-linear-gradient(0deg,transparent_0_34px,#cbdcd6_35px_36px)]"/><div className="absolute inset-x-8 top-1/2 h-1 -rotate-12 rounded-full bg-[#0b806c] shadow-[0_0_18px_rgba(11,128,108,.5)]"/></div>
          <div className="mx-auto mt-7 w-full max-w-xl"><div className="h-2 overflow-hidden rounded-full bg-slate-200"><div className="h-full rounded-full bg-[#0b806c] transition-[width]" style={{ width: `${progress}%` }}/></div><div className="mt-2 flex justify-between text-xs text-slate-500"><span>{progress}%</span><span>{files[currentFile]?.name}</span></div></div>
          <p className="mt-6 text-xs text-slate-400">قد يستغرق الفحص عدة دقائق حسب حجم البيانات — {elapsedSeconds} ثانية</p>
        </div>
        <aside className="flex items-center border-s border-slate-200 p-5"><div className="w-full rounded-xl border border-slate-200 bg-[#fdfefc] p-5 text-start"><p className="text-xs text-slate-400">الطبقة الحالية</p><strong className="mt-1 block text-lg text-[#17332f]">{detectUploadMode(files[currentFile] ?? files[0]) === "vector" ? "بيانات مكانية" : "صورة خريطة"}</strong><ul className="mt-5 space-y-3 text-sm text-slate-600"><li>تم رفع الملف بنجاح</li><li>{progress >= 18 ? "تم اكتشاف نوع الطبقة" : "جاري اكتشاف نوع الطبقة"}</li><li>{progress >= 62 ? "اكتمل فحص الجودة" : "جاري فحص التفاصيل"}</li><li>{progress >= 98 ? "النتائج جاهزة" : "لا توجد أخطاء حتى الآن"}</li></ul></div></aside>
      </div>
    </section>;
  }

  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-6">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-blue-600">
          {t("New analysis")}
        </p>

        <h2 className="mt-2 text-2xl font-bold text-slate-950">
          {t("Upload geospatial data")}
        </h2>

        <p className="mt-2 text-sm leading-6 text-slate-600">
          {t("Upload vector data for PostGIS validation or a map image for visual element analysis.")}
        </p>
      </div>

      <form
        onSubmit={handleSubmit}
        className="space-y-5"
      >
        <div>
          <label
            htmlFor="dataset-file"
            className="mb-2 block text-sm font-semibold text-slate-800"
          >
            {t("Select file")}
          </label>

          <label
            htmlFor="dataset-file"
            className="flex min-h-32 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 bg-slate-50 px-4 py-4 text-center transition hover:border-blue-400 hover:bg-blue-50"
          >
            <span className="text-2xl">↑</span>

            <span className="mt-2 text-sm font-semibold text-slate-900">
              {files.length
                ? files.length === 1 ? files[0].name : `${files.length} files selected`
                : t("Choose a file to upload")}
            </span>

            <span className="mt-1 text-xs text-slate-500">
              GeoJSON, GeoPackage, CSV, GeoParquet, zipped Shapefile, PNG, JPG, or TIFF
            </span>

            {files.length > 0 && (
              <span className="mt-2 rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-600 shadow-sm">
                {(files.reduce((total, item) => total + item.size, 0) / 1024 / 1024).toFixed(2)} MB total
              </span>
            )}
          </label>

          <input
            id="dataset-file"
            type="file"
            accept={acceptedFormats}
            onChange={(event) => {
              setFiles(Array.from(event.target.files ?? []));
              setError(null);
            }}
            className="sr-only"
          />
          <div className="mt-2 flex items-center justify-center gap-2"><span className="text-[11px] text-slate-400">or</span><label htmlFor="dataset-folder" className="cursor-pointer rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-bold text-blue-700 hover:bg-blue-100">Choose a folder</label></div>
          <input ref={folderInputRef} id="dataset-folder" type="file" multiple accept={acceptedFormats} onChange={(event) => { const supported = Array.from(event.target.files ?? []).filter((item) => detectUploadMode(item)); setFiles(supported); setError(supported.length ? null : "The folder does not contain supported vector or image files."); }} className="sr-only" />
        </div>

        {error && (
          <div
            role="alert"
            className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
          >
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={isLoading}
          className="w-full rounded-xl bg-blue-600 px-5 py-3.5 text-sm font-bold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-400"
        >
          {isLoading
            ? `Analyzing... ${elapsedSeconds}s`
            : t("Start analysis")}
        </button>

        {isLoading && (
          <div className="rounded-xl bg-blue-50 px-4 py-3 text-xs leading-5 text-blue-800" aria-live="polite">
            <div className="mb-2 flex justify-between font-bold"><span>{files[currentFile]?.name}</span><span>{progress}%</span></div><div className="mb-2 h-2 overflow-hidden rounded-full bg-blue-100"><div className="h-full rounded-full bg-blue-600 transition-[width]" style={{ width: `${progress}%` }} /></div>
            {files.length > 1 && <p className="mb-1 font-semibold">File {currentFile + 1} of {files.length}</p>}
            {elapsedSeconds < 5
              ? "Uploading and validating the file..."
              : elapsedSeconds < 20
                ? "Running spatial rules and preparing results..."
                : "Large datasets can take a few minutes. Keep this page open while processing continues."}
          </div>
        )}
      </form>
    </section>
  );
}
