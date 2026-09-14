"use client";

import {
  useRef,
  useState,
} from "react";

import {
  askGeoSA,
  type GeoSASource,
} from "@/lib/intelligence-api";
import { useLanguage } from "@/components/LanguageProvider";

interface Message {
  role: "user" | "assistant";
  text: string;
  sources?: GeoSASource[];
  attachment?: string;
}

export default function GeoSAChat() {
  const { language, t } = useLanguage();

  const [messages, setMessages] =
    useState<Message[]>([]);
  const [input, setInput] =
    useState("");
  const [file, setFile] =
    useState<File | null>(null);
  const [loading, setLoading] =
    useState(false);

  const inputRef =
    useRef<HTMLInputElement>(null);

  async function send(
    preset?: string
  ) {
    const question = (
      preset ?? input
    ).trim();

    if (!question || loading) return;

    setMessages((current) => [
      ...current,
      {
        role: "user",
        text: question,
        attachment: file?.name,
      },
    ]);

    setInput("");
    setLoading(true);

    try {
      const response = await askGeoSA(
        question,
        file
      );

      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          text: response.answer,
          sources: response.sources,
        },
      ]);

      setFile(null);
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          text:
            error instanceof Error
              ? error.message
              : t("The request could not be completed."),
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function startVoice() {
    const SpeechRecognition =
      (
        window as typeof window & {
          SpeechRecognition?: new () => any;
          webkitSpeechRecognition?:
            new () => any;
        }
      ).SpeechRecognition ??
      (
        window as typeof window & {
          webkitSpeechRecognition?:
            new () => any;
        }
      ).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert(
        t("Voice input is not supported by this browser.")
      );
      return;
    }

    const recognition =
      new SpeechRecognition();

    recognition.lang = language === "ar" ? "ar-SA" : "en-US";
    recognition.interimResults = false;

    recognition.onresult = (
      event: any
    ) => {
      setInput(
        event.results[0][0]
          .transcript
      );
    };

    recognition.start();
  }

  function speak(text: string) {
    if (
      !("speechSynthesis" in window)
    ) {
      return;
    }

    window.speechSynthesis.cancel();

    const utterance =
      new SpeechSynthesisUtterance(
        text
      );

    utterance.lang = language === "ar" ? "ar-SA" : "en-US";

    window.speechSynthesis.speak(
      utterance
    );
  }

  const suggestions = [
    "What are the elements of geospatial data quality?",
    "What national spatial reference is used in Saudi Arabia?",
    "What are the quality requirements for road data?",
  ].map(t);

  return (
    <section className="mx-auto flex min-h-[calc(100vh-125px)] max-w-5xl flex-col overflow-hidden rounded-3xl border border-[#dfe8e3] bg-white shadow-sm">
      <div className="border-b border-[#edf2ef] px-6 py-5">
        <p className="text-xs font-bold uppercase tracking-[0.17em] text-[#0b7664]">
          GeoSA Intelligence
        </p>

        <h2 className="mt-1 text-xl font-extrabold text-[#17332f]">
          GeoSA Standards Assistant
        </h2>

        <p className="mt-1 text-sm text-slate-500">
          Ask about GeoSA standards or attach a file for analysis using official sources.
        </p>
      </div>

      <div className="flex-1 space-y-5 overflow-y-auto bg-[#fbfdfc] p-5 sm:p-7">
        {!messages.length && (
          <div className="mx-auto mt-10 max-w-2xl text-center">
            <div className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-[#e1f1eb] text-2xl text-[#08705e]">
              ✦
            </div>

            <h3 className="mt-4 text-xl font-bold text-[#17332f]">
              How can I help?
            </h3>

            <p className="mt-2 text-sm leading-6 text-slate-500">
              I can search GeoSA documents and connect the evidence to your file.
            </p>

            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {suggestions.map(
                (suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() =>
                      void send(
                        suggestion
                      )
                    }
                    className="rounded-full border border-[#cfe1da] bg-white px-4 py-2 text-xs font-semibold text-[#31524b] hover:bg-[#edf7f3]"
                  >
                    {suggestion}
                  </button>
                )
              )}
            </div>
          </div>
        )}

        {messages.map(
          (message, index) => (
            <div
              key={index}
              className={
                message.role ===
                "user"
                  ? "ms-auto max-w-[80%]"
                  : "me-auto max-w-[88%]"
              }
            >
              <div
                className={
                  message.role ===
                  "user"
                    ? "rounded-2xl rounded-ee-md bg-[#0b7664] px-5 py-3 text-sm leading-7 text-white"
                    : "rounded-2xl rounded-es-md border border-[#dfe8e3] bg-white px-5 py-4 text-sm leading-7 text-[#243b37] shadow-sm"
                }
              >
                {message.attachment && (
                  <div className="mb-2 rounded-lg bg-white/15 px-3 py-2 text-xs">
                    📎{" "}
                    {
                      message.attachment
                    }
                  </div>
                )}

                <div className="whitespace-pre-wrap">
                  {message.text}
                </div>
              </div>

              {message.role ===
                "assistant" && (
                <div className="mt-2 flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() =>
                      speak(
                        message.text
                      )
                    }
                    className="text-xs font-semibold text-[#0b7664]"
                  >
                    🔊 Listen
                  </button>
                </div>
              )}

              {!!message.sources?.length && (
                <details className="mt-3 rounded-xl border border-[#dfe8e3] bg-white p-3">
                  <summary className="cursor-pointer text-xs font-bold text-[#0b7664]">
                    Sources (
                    {
                      message.sources
                        .length
                    }
                    )
                  </summary>

                  <div className="mt-3 space-y-2">
                    {message.sources.map(
                      (
                        source,
                        sourceIndex
                      ) => (
                        <div
                          key={
                            sourceIndex
                          }
                          className="rounded-lg bg-[#f5f9f7] p-3 text-xs"
                        >
                          <strong className="block text-[#17332f]">
                            {
                              source.document
                            }
                          </strong>

                          <span className="text-slate-500">
                            Page{" "}
                            {
                              source.page
                            }
                          </span>

                          <p className="mt-2 line-clamp-3 leading-5 text-slate-600">
                            {
                              source.excerpt
                            }
                          </p>
                        </div>
                      )
                    )}
                  </div>
                </details>
              )}
            </div>
          )
        )}

        {loading && (
          <div className="me-auto rounded-2xl border border-[#dfe8e3] bg-white px-5 py-3 text-sm text-slate-500">
            Searching GeoSA sources...
          </div>
        )}
      </div>

      <div className="border-t border-[#e6ede9] bg-white p-4">
        {file && (
          <div className="mb-3 flex items-center justify-between rounded-xl bg-[#edf7f3] px-4 py-2 text-xs text-[#31524b]">
            <span>
              📎 {file.name}
            </span>

            <button
              type="button"
              onClick={() =>
                setFile(null)
              }
              className="font-bold"
            >
              ×
            </button>
          </div>
        )}

        <div className="flex items-end gap-2 rounded-2xl border border-[#cadbd4] bg-[#fbfdfc] p-2 focus-within:border-[#4e9b89]">
          <input
            ref={inputRef}
            type="file"
            className="hidden"
            accept=".pdf,.txt,.md,.csv,.geojson,.json,.gpkg,.zip"
            onChange={(event) =>
              setFile(
                event.target
                  .files?.[0] ??
                  null
              )
            }
          />

          <button
            type="button"
            onClick={() =>
              inputRef.current?.click()
            }
            className="flex size-10 shrink-0 items-center justify-center rounded-xl text-lg text-[#49635d] hover:bg-[#e8f3ef]"
          >
            📎
          </button>

          <textarea
            value={input}
            rows={1}
            placeholder="Ask about GeoSA standards..."
            onChange={(event) =>
              setInput(
                event.target.value
              )
            }
            onKeyDown={(event) => {
              if (
                event.key ===
                  "Enter" &&
                !event.shiftKey
              ) {
                event.preventDefault();
                void send();
              }
            }}
            className="max-h-32 min-h-10 flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none"
          />

          <button
            type="button"
            onClick={startVoice}
            className="flex size-10 shrink-0 items-center justify-center rounded-xl text-lg text-[#49635d] hover:bg-[#e8f3ef]"
          >
            🎙
          </button>

          <button
            type="button"
            disabled={
              loading ||
              !input.trim()
            }
            onClick={() =>
              void send()
            }
            className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-[#0b7664] text-white disabled:opacity-40"
          >
            ↑
          </button>
        </div>

        <p className="mt-2 text-center text-[10px] text-slate-400">
          Answers are grounded in retrieved GeoSA documents. Review the source before making an official decision.
        </p>
      </div>
    </section>
  );
}
