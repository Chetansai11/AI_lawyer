from __future__ import annotations

import re

from app.state import ConversationalState
from app.utils.gaps import effective_missing_fields

_GAP_READABLE = {
    "location": "location",
    "date": "date",
    "injuries": "injuries or symptoms",
    "incident_type": "incident type",
    "liability": "fault and liability",
}

_MAX_FACT_LEN = 400


def _safe_plain(value: object, *, empty: str = "not yet specified") -> str:
    """Normalize user-supplied text for Markdown (reduce header/bold injection)."""
    s = str(value or "").strip()
    if not s:
        return empty
    s = re.sub(r"[\r\n]+", " ", s)
    s = s.replace("**", "").replace("##", "").strip()
    if len(s) > _MAX_FACT_LEN:
        s = s[: _MAX_FACT_LEN - 1] + "…"
    return s


def _gap_labels(missing: list[str]) -> str:
    parts = [_GAP_READABLE.get(m, m.replace("_", " ")) for m in missing if m]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return ", ".join(parts[:-1]) + f", and {parts[-1]}"


def build_summary_paragraph(state: ConversationalState) -> str:
    """
    Production-style narrative summary: multiple sentences, neutral tone, triage disclaimer.
    """
    facts = state.get("extracted_facts") or {}
    missing = effective_missing_fields(state)

    inc = _safe_plain(facts.get("incident_type", ""))
    loc = _safe_plain(facts.get("location", ""))
    dt = _safe_plain(facts.get("date", ""))
    inj = _safe_plain(facts.get("injuries", ""))

    # Sentence 1: matter framing
    if inc != "not yet specified" and loc != "not yet specified" and dt != "not yet specified":
        lead = (
            f"This intake concerns a **{_safe_plain(inc, empty='civil')}** matter reported in "
            f"**{_safe_plain(loc, empty='an unspecified location')}** on **{_safe_plain(dt, empty='an unspecified date')}**."
        )
    elif inc != "not yet specified":
        lead = (
            f"This intake concerns a **{_safe_plain(inc, empty='civil')}** matter; "
            "location and timing have not been fully confirmed from the conversation."
        )
    else:
        lead = (
            "This is an early-stage civil intake: the incident category, location, and timing "
            "have not yet been established to a level suitable for formal attorney review."
        )

    # Sentence 2: injuries
    if inj != "not yet specified":
        body_inj = f" The client reported **{inj}** in connection with the event."
    else:
        body_inj = " Injury details have not been documented or confirmed in this thread."

    # Case score / model confidence are counsel-only (see API fields); not included in client-facing summary.

    # Gaps or completeness
    if missing:
        gap_str = _gap_labels(missing)
        gap_note = (
            f" **Outstanding information gaps** include {gap_str}; "
            "the brief below should be read as provisional until those items are clarified."
        )
    else:
        gap_note = (
            " **Core intake fields** needed for initial triage appear present; "
            "remaining risk should still be validated with documents and counsel."
        )

    para1 = (lead + body_inj + gap_note).strip()
    para2 = (
        "**Disclaimer:** This summary is generated for intake triage only, "
        "does not constitute legal advice, and does not create an attorney–client relationship."
    )

    return para1 + "\n\n" + para2


def format_brief_markdown(state: ConversationalState) -> str:
    facts = state.get("extracted_facts", {})
    assumptions = state.get("assumptions", [])
    lawyers = state.get("lawyer_matches", [])
    nq = (state.get("next_question") or "").strip()
    missing = effective_missing_fields(state)

    assumptions_md = "\n".join(
        f"- {a['text']} _(confidence {a['confidence']:.2f})_" for a in assumptions
    ) or "- _None stated_"

    lawyers_md = "\n".join(f"- **{row['name']}** – {row['specialty']}" for row in lawyers) or "- _None_"

    if missing and nq:
        follow_block = f"- **Next:** {nq}"
    elif not missing:
        follow_block = "- _(Intake complete - no blocking question pending)_"
    else:
        follow_block = "- _(Clarifying pending)_"

    summary = build_summary_paragraph(state)

    return f"""## Attorney Brief

### Summary
{summary}

### Key Facts
- **Location:** {_safe_plain(facts.get('location', ''), empty='-')}
- **Date:** {_safe_plain(facts.get('date', ''), empty='-')}
- **Incident:** {_safe_plain(facts.get('incident_type', ''), empty='-')}
- **Injuries:** {_safe_plain(facts.get('injuries', ''), empty='-')}

### Assumptions
{assumptions_md}

### Risk Analysis
{state.get('risk_analysis', '_No analysis yet._')}

### Recommended Lawyers
{lawyers_md}

### Follow-up Questions
{follow_block}
"""
