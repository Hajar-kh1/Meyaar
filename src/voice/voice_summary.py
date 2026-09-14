import asyncio
import json
import os
import re
import tempfile
import wave
from pathlib import Path

import edge_tts
import truststore
from dotenv import load_dotenv
from groq import Groq

truststore.inject_into_ssl()
load_dotenv()

EDGE_VOICE = "ar-SA-ZariyahNeural"


def _groq_client():
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not configured for audio downloads."
        )

    return Groq(api_key=api_key)


def generate_audio_report_text(
    dataset,
    validation,
    quality_summary,
    report,
):
    prompt = f"""
حوّل تقييم Meyaar إلى تقرير صوتي عربي واضح ومهني.

الهدف:
أن يفهم المستخدم أهم محتوى التقرير بدون الحاجة إلى قراءة ملف PDF.

استخدم:
- dataset لمعلومات البيانات.
- validation للأرقام ونتائج القواعد ودرجات الخطورة.
- quality_summary لأبعاد الجودة.
- report للتفسير والتوصيات.

غطِّ:
- نتيجة التقييم العامة.
- نوع البيانات ونظام الإحداثيات.
- إجمالي الحالات التي تحتاج إلى مراجعة.
- أبعاد الجودة المتأثرة.
- أهم نتائج قواعد التحقق وأعدادها.
- معنى النتائج باختصار.
- هل تم تنفيذ تصحيح أو إعادة تحقق.
- أهم التوصيات.
- تنبيه مختصر بأن Meyaar لا يمثل اعتمادًا رسميًا من GeoSA.

قواعد:
- لا تخترع معلومات أو أرقام.
- لا تغير الأرقام.
- لا تعتبر النتائج أخطاء أو مخالفات مؤكدة.
- Severity تصنيف داخلي في Meyaar.
- لا تقرأ run_id أو Rule ID.
- لا تكرر المعلومات.
- لا تستخدم أسلوب محادثة.
- اكتب نصًا عربيًا مترابطًا ومناسبًا للاستماع.
- أرجع نصًا متصلًا مخصصًا للنطق فقط، بدون عنوان أو Markdown أو نقاط أو قوائم.
- استخدم report فقط للتوصيات ولا تضف توصيات من عندك.

DATASET:
{json.dumps(dataset, ensure_ascii=False, default=str)}

VALIDATION:
{json.dumps(validation, ensure_ascii=False, default=str)}

QUALITY SUMMARY:
{json.dumps(quality_summary, ensure_ascii=False, default=str)}

REPORT:
{json.dumps(report, ensure_ascii=False, default=str)}
"""

    response = _groq_client().chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        temperature=0,
        max_completion_tokens=1200,
    )

    text = response.choices[0].message.content

    if not text:
        raise ValueError(
            "Failed to generate audio report."
        )

    return text.strip()


def generate_local_audio_text(
    dataset,
    validation,
):
    total_features = dataset.get(
        "feature_count",
        0,
    )

    total_errors = validation.get(
        "total_errors",
        validation.get(
            "total_findings",
            0,
        ),
    )

    quality_after = (
        validation.get("quality_after")
        or {}
    )

    quality_before = (
        validation.get("quality_before")
        or {}
    )

    quality_score = quality_after.get(
        "quality_score",
        quality_before.get(
            "quality_score",
            0,
        ),
    )

    improvement = validation.get(
        "quality_improvement",
        0,
    )

    revalidation = (
        validation.get("revalidation_summary")
        or {}
    )

    text = (
        f"اكتمل تقييم البيانات المكانية في منصة معيار. "
        f"يحتوي التحليل على {total_features} معلم مكاني، "
        f"وتم رصد {total_errors} حالة تحتاج إلى المراجعة. "
        f"بلغت درجة جودة البيانات {quality_score} بالمئة. "
    )

    if revalidation.get("performed"):
        resolved = revalidation.get(
            "resolved_fixes",
            0,
        )

        text += (
            f"تم تنفيذ إعادة التحقق بعد التصحيح، "
            f"وتم التحقق من معالجة {resolved} حالة. "
        )

        if improvement:
            text += (
                f"تحسنت درجة الجودة بمقدار "
                f"{improvement} نقطة مئوية. "
            )

    text += (
        f"تم إعداد التقرير التفصيلي الذي يحتوي على "
        f"نتائج التحقق والتوصيات. "
        f"هذه النتائج تمثل تقييمًا داخليًا في منصة معيار، "
        f"ولا تمثل اعتمادًا رسميًا من الهيئة العامة "
        f"للمساحة والمعلومات الجيومكانية."
    )

    return text


def split_text(
    text,
    max_chars=190,
):
    sentences = re.split(
        r"(?<=[.!؟])\s+",
        text.strip(),
    )

    chunks = []
    current = ""

    for sentence in sentences:
        candidate = (
            f"{current} {sentence}".strip()
        )

        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)

            current = sentence

    if current:
        chunks.append(current)

    return chunks


def create_tts_chunk(
    text,
    output_path,
    voice="lulwa",
):
    response = (
        _groq_client()
        .audio.speech.create(
            model=(
                "canopylabs/"
                "orpheus-arabic-saudi"
            ),
            voice=voice,
            input=text,
            response_format="wav",
        )
    )

    response.write_to_file(
        output_path
    )


async def _create_edge_audio(
    text,
    output_path,
):
    communicate = edge_tts.Communicate(
        text=text,
        voice=EDGE_VOICE,
    )

    await communicate.save(
        str(output_path)
    )


def create_edge_fallback(
    text,
    output_path,
):
    output_path = (
        Path(output_path)
        .with_suffix(".mp3")
    )

    asyncio.run(
        _create_edge_audio(
            text,
            output_path,
        )
    )

    if not output_path.exists():
        raise RuntimeError(
            "Edge TTS did not create "
            "an audio file."
        )

    return output_path


def merge_wav_files(
    files,
    output_path,
):
    with wave.open(
        str(files[0]),
        "rb",
    ) as first:
        channels = first.getnchannels()
        sample_width = (
            first.getsampwidth()
        )
        frame_rate = (
            first.getframerate()
        )

    with wave.open(
        str(output_path),
        "wb",
    ) as output:
        output.setnchannels(
            channels
        )

        output.setsampwidth(
            sample_width
        )

        output.setframerate(
            frame_rate
        )

        for file in files:
            with wave.open(
                str(file),
                "rb",
            ) as wav_file:
                output.writeframes(
                    wav_file.readframes(
                        wav_file.getnframes()
                    )
                )


def _create_groq_audio(
    text,
    output_path,
    voice,
):
    chunks = split_text(text)

    if not chunks:
        raise ValueError(
            "No audio text was generated."
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)
        wav_files = []

        for index, chunk in enumerate(
            chunks,
            start=1,
        ):
            chunk_path = (
                temp_dir
                / f"chunk_{index}.wav"
            )

            create_tts_chunk(
                text=chunk,
                output_path=chunk_path,
                voice=voice,
            )

            wav_files.append(
                chunk_path
            )

        merge_wav_files(
            files=wav_files,
            output_path=output_path,
        )


def synthesize_speech_bytes(
    text,
    voice="lulwa",
):
    if not text.strip():
        raise ValueError(
            "No text was provided for "
            "audio generation."
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)

        output_path = (
            temp_root
            / "agent-explanation.wav"
        )

        try:
            _create_groq_audio(
                text=text[:4000],
                output_path=output_path,
                voice=voice,
            )

            return (
                output_path.read_bytes()
            )

        except Exception as exc:
            print(
                "GROQ TTS FAILED - "
                "USING EDGE FALLBACK:",
                repr(exc),
            )

            fallback_path = (
                create_edge_fallback(
                    text=text[:4000],
                    output_path=output_path,
                )
            )

            return (
                fallback_path.read_bytes()
            )


def create_audio_summary(
    dataset,
    validation,
    quality_summary,
    report,
    output_path=(
        "outputs/MEYAAR_Summary.wav"
    ),
    voice="lulwa",
):
    output_path = Path(
        output_path
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        audio_text = (
            generate_audio_report_text(
                dataset=dataset,
                validation=validation,
                quality_summary=quality_summary,
                report=report,
            )
        )

    except Exception as exc:
        print(
            "GROQ TEXT FAILED - "
            "USING LOCAL SUMMARY:",
            repr(exc),
        )

        audio_text = (
            generate_local_audio_text(
                dataset=dataset,
                validation=validation,
            )
        )

    try:
        _create_groq_audio(
            text=audio_text,
            output_path=output_path,
            voice=voice,
        )

        return {
            "status": "success",
            "provider": "groq",
            "audio_text": audio_text,
            "audio_path": str(
                output_path
            ),
        }

    except Exception as exc:
        print(
            "GROQ TTS FAILED - "
            "USING EDGE FALLBACK:",
            repr(exc),
        )

        fallback_path = (
            create_edge_fallback(
                text=audio_text,
                output_path=output_path,
            )
        )

        print(
            "EDGE TTS FALLBACK SUCCESS:",
            fallback_path,
        )

        return {
            "status": "success",
            "provider": "edge",
            "audio_text": audio_text,
            "audio_path": str(
                fallback_path
            ),
        }