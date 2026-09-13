import base64
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

from src.reporting.charts import (
    create_findings_by_rule_chart,
    create_quality_dimension_chart,
)

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"
TEMPLATE_NAME = "report_template.html"
OUTPUT_DIR = Path("outputs")

RULE_TO_DIMENSION = {
    "RD001": "Logical Consistency",
    "RD002": "Logical Consistency",
    "RD003": "Logical Consistency",
    "RD004": "Logical Consistency",
    "RD005": "Completeness",
    "BLD001": "Logical Consistency",
    "BLD002": "Logical Consistency",
    "BLD003": "Logical Consistency",
    "BLD004": "Completeness",
    "GIS001": "Spatial Reference",
    "GIS002": "Spatial Validity",
    "GIS003": "Completeness",
    "GIS004": "Attribute Quality",
    "GIS005": "Attribute Quality",
}


def normalize_dataset(dataset):
    return {
        "file_name": dataset.get(
            "file_name",
            "Unknown Dataset",
        ),
        "layer_type": dataset.get(
            "layer_type",
            "Unknown",
        ),
        "feature_count": dataset.get(
            "feature_count",
            0,
        ),
        "crs": dataset.get(
            "crs",
            "Not Available",
        ),
    }

def normalize_validation(validation):
    normalized_summary = []

    for row in validation.get(
        "summary",
        [],
    ):
        findings = row.get(
            "findings",
            row.get(
                "errors_found",
                0,
            ),
        )

        normalized_summary.append(
            {
                "rule_id": row.get(
                    "rule_id",
                    "Unknown",
                ),
                "finding_type": row.get(
                    "finding_type",
                    row.get(
                        "error_type",
                        "Unknown Finding",
                    ),
                ),
                "severity": row.get(
                    "severity",
                    "Not Specified",
                ),
                "findings": findings,
            }
        )

    total_findings = validation.get(
        "total_findings",
        validation.get(
            "total_errors",
            sum(
                row["findings"]
                for row in normalized_summary
            ),
        ),
    )

    return {
        "status": validation.get(
            "status",
            "unknown",
        ),
        "layer_name": validation.get(
            "layer_name",
            "Unknown",
        ),
        "run_id": validation.get(
            "run_id",
            "unknown-run",
        ),
        "total_findings": total_findings,
        "summary": normalized_summary,

        "quality_before": validation.get(
            "quality_before",
            {},
        ),
        "quality_after": validation.get(
            "quality_after",
            {},
        ),
        "quality_improvement": validation.get(
            "quality_improvement",
            0.0,
        ),
        "validation_before": validation.get(
            "validation_before",
            {},
        ),
        "validation_after": validation.get(
            "validation_after",
        ),
        "verified_fixes": validation.get(
            "verified_fixes",
            [],
        ),
        "revalidation_summary": validation.get(
            "revalidation_summary",
            {},
        ),
    }
def image_to_data_uri(image_path):
    if not image_path:
        return None

    image_path = Path(image_path)

    if not image_path.exists():
        return None

    encoded = base64.b64encode(
        image_path.read_bytes()
    ).decode("utf-8")

    return (
        "data:image/png;base64,"
        + encoded
    )


def build_quality_summary(validation):
    validation = normalize_validation(
        validation
    )

    dimensions = {}

    for row in validation.get(
        "summary",
        [],
    ):
        rule_id = row.get(
            "rule_id",
            "Unknown",
        )

        findings = row.get(
            "findings",
            row.get(
                "errors_found",
                0,
            ),
        )

        dimension = RULE_TO_DIMENSION.get(
            rule_id,
            "Other",
        )

        dimensions[dimension] = (
            dimensions.get(
                dimension,
                0,
            )
            + findings
        )

    rows = []

    for dimension, findings in dimensions.items():
        rows.append(
            {
                "dimension": dimension,
                "findings": findings,
                "status": (
                    "Needs Review"
                    if findings > 0
                    else "No Findings"
                ),
            }
        )

    return sorted(
        rows,
        key=lambda row: row["findings"],
        reverse=True,
    )


def build_rule_rows(validation):
    validation = normalize_validation(
        validation
    )

    rows = []

    for row in validation.get(
        "summary",
        [],
    ):
        rule_id = row.get(
            "rule_id",
            "Unknown",
        )

        findings = row.get(
            "findings",
            row.get(
                "errors_found",
                0,
            ),
        )

        rows.append(
            {
                "rule_id": rule_id,
                "quality_dimension": (
                    RULE_TO_DIMENSION.get(
                        rule_id,
                        "Other",
                    )
                ),
                "finding_type": row.get(
                    "finding_type",
                    row.get(
                        "error_type",
                        "Unknown Finding",
                    ),
                ),
                "severity": row.get(
                    "severity",
                    "Not Specified",
                ),
                "findings": findings,
                "status": (
                    "Needs Review"
                    if findings > 0
                    else "No Findings"
                ),
            }
        )

    return rows


def build_rule_context(validation):
    validation = normalize_validation(
        validation
    )

    summary = validation.get(
        "summary",
        [],
    )

    if not summary:
        return (
            "No validation findings "
            "were reported."
        )

    lines = []

    for row in summary:
        findings = row.get(
            "findings",
            row.get(
                "errors_found",
                0,
            ),
        )

        lines.append(
            (
                f"- {row.get('rule_id', 'Unknown')}: "
                f"{row.get('finding_type', row.get('error_type', 'Unknown Finding'))} | "
                f"Severity: {row.get('severity', 'Not Specified')} | "
                f"Candidate Findings: "
                f"{findings:,}"
            )
        )

    return "\n".join(lines)

def build_revalidation_context(validation):
    summary = validation.get(
        "revalidation_summary",
        {},
    )

    verified_fixes = validation.get(
        "verified_fixes",
        [],
    )

    if not summary.get("attempted"):
        return (
            "No automatic corrective fixes were applied. "
            "No re-validation was required."
        )

    if not summary.get("performed"):
        return (
            "Automatic corrective fixes were applied, "
            "but re-validation did not complete successfully."
        )

    quality_before = summary.get(
        "quality_before",
        0.0,
    )

    quality_after = summary.get(
        "quality_after",
        quality_before,
    )

    improvement = summary.get(
        "quality_improvement",
        0.0,
    )

    affected_before = summary.get(
        "affected_features_before",
        0,
    )

    affected_after = summary.get(
        "affected_features_after",
        affected_before,
    )

    findings_before = summary.get(
        "findings_before",
        0,
    )

    findings_after = summary.get(
        "findings_after",
        findings_before,
    )

    applied_fixes = summary.get(
        "applied_fixes",
        0,
    )

    resolved_fixes = summary.get(
        "resolved_fixes",
        0,
    )

    unresolved_fixes = summary.get(
        "unresolved_fixes",
        0,
    )

    lines = [
        "Re-validation was performed after automatic remediation.",
        f"Quality score before remediation: {quality_before}.",
        f"Quality score after remediation: {quality_after}.",
        f"Quality score improvement: {improvement}.",
        f"Affected features before: {affected_before}.",
        f"Affected features after: {affected_after}.",
        f"Findings before: {findings_before}.",
        f"Findings after: {findings_after}.",
        f"Applied fixes: {applied_fixes}.",
        f"Verified resolved fixes: {resolved_fixes}.",
        f"Verified unresolved fixes: {unresolved_fixes}.",
    ]

    for item in verified_fixes:
        feature_id = item.get(
            "feature_id",
            "Unknown",
        )

        rule_id = item.get(
            "rule_id",
            "Unknown",
        )

        resolved = item.get(
            "resolved"
        )

        if resolved is True:
            status = "resolved"
        elif resolved is False:
            status = "still present"
        else:
            status = "not verified"

        lines.append(
            f"- Feature {feature_id}, "
            f"rule {rule_id}: {status}."
        )

    return "\n".join(lines)

def sanitize_report_language(report):
    replacements = [
        (
            r"\bcandidate errors\b",
            "candidate findings",
        ),
        (
            r"\bcandidate error\b",
            "candidate finding",
        ),
        (
            r"\bdetected errors\b",
            "detected findings",
        ),
        (
            r"\bdetected error\b",
            "detected finding",
        ),
        (
            r"\bconfirmed errors\b",
            "confirmed findings",
        ),
        (
            r"\bconfirmed error\b",
            "confirmed finding",
        ),
        (
            r"\btopology errors\b",
            "topology findings",
        ),
        (
            r"\btopology error\b",
            "topology finding",
        ),
        (
            r"\bvalidation errors\b",
            "validation findings",
        ),
        (
            r"\bvalidation error\b",
            "validation finding",
        ),
        (
            r"\bviolations\b",
            "findings",
        ),
        (
            r"\bviolation\b",
            "finding",
        ),
    ]

    for key, value in report.items():
        if not isinstance(
            value,
            str,
        ):
            continue

        for pattern, replacement in replacements:
            value = re.sub(
                pattern,
                replacement,
                value,
                flags=re.IGNORECASE,
            )

        report[key] = value.strip()

    return report


def clean_json_response(text):
    text = text.strip()

    if text.startswith(
        "```json"
    ):
        text = text[
            len("```json"):
        ]

    elif text.startswith(
        "```"
    ):
        text = text[
            len("```"):
        ]

    if text.endswith(
        "```"
    ):
        text = text[:-3]

    return text.strip()


def generate_report_content(
    dataset,
    validation,
):
    dataset = normalize_dataset(
        dataset
    )

    validation = normalize_validation(
        validation
    )

    api_key = os.getenv(
        "GROQ_API_KEY"
    )

    if not api_key:
        raise ValueError(
            "GROQ_API_KEY was not found."
        )

    client = Groq(
        api_key=api_key
    )

    rule_context = build_rule_context(
        validation
    )

    revalidation_context = build_revalidation_context(
        validation
    )

    prompt = f"""
You are writing concise explanatory text for a Meyaar
Geospatial Data Quality Assessment Report.

Meyaar uses deterministic PostGIS validation rules.

You do not perform validation.
You do not discover new findings.
You only explain the supplied results.

DATASET

{json.dumps(
    dataset,
    indent=2
)}

VALIDATION

{json.dumps(
    validation,
    indent=2
)}

RULES WITH FINDINGS

{rule_context}

REMEDIATION AND RE-VALIDATION

{revalidation_context}

STRICT RULES

1. Use only supplied information.

2. Never invent:
   rule IDs,
   finding types,
   counts,
   severity,
   locations,
   districts,
   neighborhoods,
   hotspots,
   corridors,
   intersections,
   spatial patterns,
   or map observations.

3. Preserve numerical values exactly.

4. PostGIS results are the source of truth.

5. Use "finding" or "candidate finding".

6. Do not call findings confirmed errors.

7. Do not use "violation" or "violations".

8. Do not infer the cause of a finding.

9. Do not infer intended geometry, connectivity,
   extent, location, or boundary.

10. Mention only the current layer and rules.

11. Never reuse a Road rule in a Buildings report.

12. Never reuse a Buildings rule in a Roads report.

13. Severity is Meyaar's internal classification.

14. Do not claim official GeoSA certification,
    approval, compliance, or official violation.

15. Do not invent percentages.

16. Do not claim a map was reviewed.

17. Spatial visualization is pending frontend
    integration unless explicitly provided.

18. Recommendations may recommend review,
    investigation, correction after review,
    and re-validation.

19. If remediation information shows that a fix
    was applied, you may state that the fix was applied.

20. Never claim that an applied fix was successful
    unless verified_fixes or revalidation_summary
    shows that the finding was resolved.

21. If no automatic corrective fixes were applied,
    say:
    "No corrective actions were performed on the dataset."

22. If re-validation was performed, describe only
    the supplied before and after values.

23. If re-validation was not performed, do not
    invent a before/after comparison.

24. Preserve quality scores, finding counts,
    affected feature counts, and improvement values
    exactly as supplied.

25. When re-validation is available, the
    revalidation_improvement section should clearly
    summarize:
    - quality score before remediation,
    - quality score after remediation,
    - quality improvement,
    - findings before and after,
    - affected features before and after,
    - resolved fixes,
    - unresolved fixes.

26. The actions_taken section may describe only
    actions explicitly present in the supplied
    remediation and re-validation information.

27. Keep writing concise and professional.

28. Return valid JSON only.

Return exactly:

{{
    "executive_summary": "...",
    "quality_assessment_summary": "...",
    "detailed_findings": "...",
    "actions_taken": "...",
    "revalidation_improvement": "...",
    "recommendations": "...",
    "assessment_methodology": "...",
    "standards_alignment_disclaimer": "..."
}}
"""

    response = (
        client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You write concise "
                        "geospatial quality reports. "
                        "Return JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.1,
        )
    )

    text = (
        response
        .choices[0]
        .message
        .content
    )

    text = clean_json_response(
        text
    )

    try:
        report = json.loads(
            text
        )

    except json.JSONDecodeError as exc:
        print("Groq response:")
        print(text)

        raise ValueError(
            "Groq returned invalid JSON."
        ) from exc

    required_keys = [
        "executive_summary",
        "quality_assessment_summary",
        "detailed_findings",
        "actions_taken",
        "revalidation_improvement",
        "recommendations",
        "assessment_methodology",
        "standards_alignment_disclaimer",
    ]

    for key in required_keys:
        report.setdefault(
            key,
            "",
        )

    return sanitize_report_language(
        report
    )

def create_pdf(
    dataset,
    validation,
    report,
    output_path="outputs/MEYAAR_Report.pdf",
):
    dataset = normalize_dataset(
        dataset
    )

    validation = normalize_validation(
        validation
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = Path(
        output_path
    ).resolve()

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    quality_summary = (
        build_quality_summary(
            validation
        )
    )

    rule_rows = build_rule_rows(
        validation
    )

    safe_run_id = re.sub(
        r"[^a-zA-Z0-9_-]",
        "_",
        str(
            validation["run_id"]
        ),
    )

    findings_chart_path = (
        OUTPUT_DIR
        / f"{safe_run_id}_findings.png"
    )

    quality_chart_path = (
        OUTPUT_DIR
        / f"{safe_run_id}_quality.png"
    )

    findings_chart_path = (
        create_findings_by_rule_chart(
            validation,
            findings_chart_path,
        )
    )

    quality_chart_path = (
        create_quality_dimension_chart(
            validation,
            quality_chart_path,
        )
    )

    findings_chart_uri = (
        image_to_data_uri(
            findings_chart_path
        )
    )

    quality_chart_uri = (
        image_to_data_uri(
            quality_chart_path
        )
    )

    map_snapshot_uri = None

    environment = Environment(
        loader=FileSystemLoader(
            str(TEMPLATE_DIR)
        ),
        autoescape=True,
    )

    template = (
        environment.get_template(
            TEMPLATE_NAME
        )
    )

    html = template.render(
        dataset=dataset,
        validation=validation,
        report=report,
        quality_summary=quality_summary,
        rule_rows=rule_rows,
        findings_chart_uri=findings_chart_uri,
        quality_chart_uri=quality_chart_uri,
        map_snapshot_uri=map_snapshot_uri,
    )

    with sync_playwright() as p:
        browser = p.chromium.launch()

        try:
            page = browser.new_page()

            page.set_content(
                html,
                wait_until="networkidle",
            )

            page.pdf(
                path=str(
                    output_path
                ),
                format="A4",
                print_background=True,
                margin={
                    "top": "12mm",
                    "right": "12mm",
                    "bottom": "12mm",
                    "left": "12mm",
                },
            )

        finally:
            browser.close()

    return str(
        output_path
    )