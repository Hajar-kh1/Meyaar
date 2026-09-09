"use client";

import dynamic from "next/dynamic";
import { useState } from "react";

import type {
  ProcessingResult,
  VectorProcessingResponse,
} from "@/types/analysis";
import { useLanguage } from "@/components/LanguageProvider";


interface MapPanelProps {
  result: ProcessingResult;
  selectedErrorId: string | null;
  initialBasemap?: "map" | "satellite";
}


function isVectorResult(
  result: ProcessingResult,
): result is VectorProcessingResponse {
  return "validation" in result;
}


const LeafletMap = dynamic(
  () =>
    import("@/components/LeafletMap").then(
      (module) => module.default,
    ),
  {
    ssr: false,
    loading: () => (
      <div className="flex min-h-[420px] items-center justify-center bg-slate-100 text-sm text-slate-500">
        Loading interactive map...
      </div>
    ),
  },
);


export default function MapPanel({
  result,
  selectedErrorId,
  initialBasemap = "map",
}: MapPanelProps) {
  const { t } = useLanguage();
  const [showLayer, setShowLayer] = useState(true);
  const [showErrors, setShowErrors] = useState(true);
  const [resetKey, setResetKey] = useState(0);
  const [basemap, setBasemap] = useState<"map" | "satellite">(initialBasemap);
  const errors = isVectorResult(result)
    ? result.validation.errors.filter(
        (error) => error.geometry,
      )
    : [];

  return (
    <section
      id="map-panel"
      className="scroll-mt-5 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
    >
      <div className="border-b border-slate-200 px-5 py-4">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-600">
          {t("Spatial view")}
        </p>

        <h2 className="mt-1.5 text-xl font-bold text-slate-950">
          {t("Interactive Map")}
        </h2>

        <p className="mt-1.5 text-xs text-slate-500">
          {errors.length > 0
            ? `${errors.length} detected error locations are highlighted.`
            : "No spatial error geometry is available for this result."}
        </p>

        {isVectorResult(result) && (
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" onClick={() => setShowLayer((value) => !value)} className={`rounded-full px-3.5 py-1.5 text-[11px] font-bold ${showLayer ? 'bg-slate-800 text-white' : 'bg-slate-100 text-slate-600'}`}>
              {t("Original layer")} {showLayer ? 'on' : 'off'}
            </button>
            <button type="button" onClick={() => setShowErrors((value) => !value)} className={`rounded-full px-3.5 py-1.5 text-[11px] font-bold ${showErrors ? 'bg-red-600 text-white' : 'bg-slate-100 text-slate-600'}`}>
              {t("Errors")} {showErrors ? 'on' : 'off'}
            </button>
            <button type="button" onClick={() => setResetKey((value) => value + 1)} className="rounded-full bg-blue-100 px-3.5 py-1.5 text-[11px] font-bold text-blue-800">
              {t("Reset view")}
            </button>
          </div>
        )}
      </div>

      <div className="relative min-h-[420px]">
        <div className="absolute end-3 top-3 z-[900] flex rounded-xl border border-white/70 bg-white/95 p-1 shadow-lg backdrop-blur">
          <button type="button" onClick={() => setBasemap("map")} aria-pressed={basemap === "map"} className={`rounded-lg px-3 py-2 text-xs font-bold ${basemap === "map" ? "bg-blue-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>{t("Map")}</button>
          <button type="button" onClick={() => setBasemap("satellite")} aria-pressed={basemap === "satellite"} className={`rounded-lg px-3 py-2 text-xs font-bold ${basemap === "satellite" ? "bg-blue-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>{t("Satellite")}</button>
        </div>
        <LeafletMap
          errors={errors}
          selectedErrorId={selectedErrorId}
          layerData={isVectorResult(result) ? result.layer_geojson : undefined}
          showLayer={showLayer}
          showErrors={showErrors}
          resetKey={resetKey}
          basemap={basemap}
        />
      </div>
    </section>
  );
}
