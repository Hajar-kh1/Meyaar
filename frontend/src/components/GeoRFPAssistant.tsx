"use client";

import {
  useState,
} from "react";

import {
  generateGeoRFP,
  type GeoRFPResponse,
} from "@/lib/intelligence-api";

export default function GeoRFPAssistant() {
  const [description, setDescription] =
    useState("");

  const [result, setResult] =
    useState<GeoRFPResponse | null>(
      null
    );

  const [loading, setLoading] =
    useState(false);

  async function generate() {
    if (
      description.trim().length <
      10
    ) {
      return;
    }

    setLoading(true);

    try {
      setResult(
        await generateGeoRFP(
          description
        )
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[0.85fr_1.15fr]">
      <section className="rounded-3xl border border-[#dfe8e3] bg-white p-6 shadow-sm">
        <p className="text-xs font-bold uppercase tracking-[0.17em] text-[#0b7664]">
          GeoSA-grounded
        </p>

        <h2 className="mt-1 text-2xl font-extrabold text-[#17332f]">
          GeoRFP Assistant
        </h2>

        <p className="mt-2 text-sm leading-6 text-slate-500">
          اكتب وصف المشروع وسيتم إنشاء الجزء الجيومكاني فقط من وثيقة RFP بالاعتماد على مصادر GeoSA.
        </p>

        <textarea
          value={description}
          onChange={(event) =>
            setDescription(
              event.target.value
            )
          }
          placeholder="مثال: مشروع لتحديث بيانات الطرق والمباني داخل مدينة الرياض وتسليم البيانات الجيومكانية وفق متطلبات الجودة..."
          className="mt-6 min-h-[270px] w-full resize-none rounded-2xl border border-[#cadbd4] bg-[#fbfdfc] p-4 text-sm leading-7 outline-none focus:border-[#4e9b89]"
        />

        <button
          type="button"
          disabled={
            loading ||
            description.trim()
              .length < 10
          }
          onClick={() =>
            void generate()
          }
          className="mt-4 w-full rounded-xl bg-[#0b7664] px-5 py-3 text-sm font-bold text-white disabled:opacity-40"
        >
          {loading
            ? "Generating..."
            : "Generate GIS Requirements"}
        </button>
      </section>

      <section className="min-h-[600px] rounded-3xl border border-[#dfe8e3] bg-white p-6 shadow-sm">
        {!result ? (
          <div className="flex h-full min-h-[520px] items-center justify-center text-center">
            <div className="max-w-sm">
              <div className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-[#e4f2ed] text-2xl text-[#0b7664]">
                ≡
              </div>

              <h3 className="mt-4 font-bold text-[#17332f]">
                GIS Requirements
              </h3>

              <p className="mt-2 text-sm leading-6 text-slate-500">
                النتيجة والمصادر ستظهر هنا بعد توليد الوثيقة.
              </p>
            </div>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between gap-3 border-b border-[#e6ede9] pb-4">
              <div>
                <p className="text-xs font-bold text-[#0b7664]">
                  Generated RFP
                </p>

                <h3 className="mt-1 font-bold text-[#17332f]">
                  Geospatial Technical Requirements
                </h3>
              </div>

              {result.rfp && (
                <button
                  type="button"
                  onClick={() =>
                    navigator.clipboard.writeText(
                      result.rfp ??
                        ""
                    )
                  }
                  className="rounded-xl border border-[#cfe1da] px-4 py-2 text-xs font-bold text-[#0b7664]"
                >
                  Copy
                </button>
              )}
            </div>

            <article className="mt-5 whitespace-pre-wrap text-sm leading-8 text-[#344b46]">
              {result.rfp ??
                "تعذر توليد المتطلبات."}
            </article>

            {!!result.sources
              .length && (
              <div className="mt-8 border-t border-[#e6ede9] pt-5">
                <h4 className="text-sm font-bold text-[#17332f]">
                  GeoSA Sources
                </h4>

                <div className="mt-3 space-y-2">
                  {result.sources.map(
                    (
                      source,
                      index
                    ) => (
                      <div
                        key={index}
                        className="rounded-xl bg-[#f6f9f7] p-3 text-xs"
                      >
                        <strong>
                          [S
                          {index +
                            1}
                          ]{" "}
                          {
                            source.document
                          }
                        </strong>

                        <span className="ms-2 text-slate-500">
                          Page{" "}
                          {
                            source.page
                          }
                        </span>
                      </div>
                    )
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}