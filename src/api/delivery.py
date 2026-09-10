from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.reporting.report_generator import build_quality_summary, create_pdf, generate_report_content
from src.voice.voice_summary import create_audio_summary


def _stage(status: str, **extra) -> dict:
    return {"status": status, **extra}


def _report_inputs(filename: str, input_type: str, result: dict) -> tuple[dict, dict]:
    if input_type != "vector":
        raise ValueError("Existing PDF/audio report functions currently support vector validation results.")

    validation = result.get("validation_after") or result.get("validation") or {}
    dataset = {
        "file_name": filename,
        "layer_type": result.get("layer_name", validation.get("layer_name", "Unknown")),
        "feature_count": result.get("total_features", 0),
        "crs": (result.get("insertion") or {}).get("crs", "Not Available"),
    }
    validation = dict(validation)
    validation.setdefault("run_id", result.get("run_id", "unknown-run"))
    validation.setdefault("layer_name", result.get("layer_name", "Unknown"))
    validation.setdefault("total_findings", result.get("total_findings", 0))
    return dataset, validation


def _send_brevo_email(
    pdf_path: str | None,
    audio_path: str | None,
    filename: str,
    recipient: str,
) -> dict:
    api_key = os.getenv("BREVO_API_KEY")
    sender_email = os.getenv("BREVO_SENDER_EMAIL")
    sender_name = os.getenv("BREVO_SENDER_NAME", "Meyaar")

    if not api_key or not sender_email:
        raise RuntimeError("BREVO_API_KEY and BREVO_SENDER_EMAIL must be configured in .env.")

    attachments = []
    for path in (pdf_path, audio_path):
        if path and Path(path).exists():
            attachments.append({
                "name": Path(path).name,
                "content": base64.b64encode(Path(path).read_bytes()).decode("ascii"),
            })

    payload = {
        "sender": {"name": sender_name, "email": sender_email},
        "to": [{"email": recipient}],
        "subject": f"Meyaar analysis report - {filename}",
        "htmlContent": "<p>Your Meyaar analysis has completed. The generated report files are attached.</p>",
    }

    if attachments:
        payload["attachment"] = attachments

    request = Request(
        "https://api.brevo.com/v3/smtp/email",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8") or "{}")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Brevo API returned HTTP {exc.code}: {detail[:500]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Brevo API request failed: {exc.reason}") from exc

    return {
        "recipient": recipient,
        "message_id": body.get("messageId"),
    }


def run_post_inspection_delivery(
    filename: str,
    input_type: str,
    result: dict,
    recipient: str,
) -> dict:
    delivery = {
        "pdf": _stage("pending"),
        "audio": _stage("pending"),
        "email": _stage("pending"),
    }

    pdf_path = None
    audio_path = None
    dataset = None
    validation = None
    report = None

    try:
        dataset, validation = _report_inputs(filename, input_type, result)
        report = generate_report_content(dataset=dataset, validation=validation)

        run_id = str(validation.get("run_id", "report")).replace("/", "_")

        pdf_path = create_pdf(
            dataset=dataset,
            validation=validation,
            report=report,
            output_path=f"outputs/{run_id}_MEYAAR_Report.pdf",
        )

        delivery["pdf"] = _stage("success", path=pdf_path)

    except Exception as exc:
        delivery["pdf"] = _stage("failed", error=str(exc))

    try:
        if dataset is None or validation is None:
            dataset, validation = _report_inputs(filename, input_type, result)

        if report is None:
            report = generate_report_content(dataset=dataset, validation=validation)

        quality_summary = build_quality_summary(validation)
        run_id = str(validation.get("run_id", "report")).replace("/", "_")

        audio = create_audio_summary(
            dataset=dataset,
            validation=validation,
            quality_summary=quality_summary,
            report=report,
            output_path=f"outputs/{run_id}_MEYAAR_Summary.wav",
            voice="lulwa",
        )

        audio_path = audio.get("audio_path")
        delivery["audio"] = _stage("success", path=audio_path)

    except Exception as exc:
        delivery["audio"] = _stage("failed", error=str(exc))

    try:
        email = _send_brevo_email(
            pdf_path,
            audio_path,
            filename,
            recipient,
        )
        delivery["email"] = _stage("success", **email)

    except Exception as exc:
        delivery["email"] = _stage(
            "failed",
            recipient=recipient,
            error=str(exc),
        )

    return delivery