from __future__ import annotations

import asyncio
import json

from app.llm import chat_text, get_client
from app.state import ConversationalState, empty_conversational_state
from app.utils.logger import agent_log

CASE_RESEARCH_SYSTEM = """You are RESEARCHER for a legal intake system (not a lawyer).

Given the extracted facts JSON and incident context, write a concise **illustrative** research note for both the client-facing brief and counsel:
- 3–5 bullet lines (each starting with "- "), describing how similar *categories* of claims are typically analyzed (duty, breach, causation, damages, notice, statutes of limitations themes — pick what fits).
- Mention that outcomes are **fact- and jurisdiction-specific** and vary widely.
- Do NOT invent specific case names or citations unless you are certain they are widely known public decisions; prefer generic patterns.
- End with one line: "_Illustrative only — not legal advice or guaranteed outcomes._"

Plain text only, no JSON, no markdown headings."""

_HEURISTIC_BY_INCIDENT: dict[str, str] = {
    "car accident": (
        "- Auto injury claims often hinge on fault allocation, insurance coverage limits, and documented medical causation.\n"
        "- Damages typically track treatment records, lost wages, and permanency evaluations where applicable.\n"
        "- _Illustrative only — not legal advice or guaranteed outcomes._"
    ),
    "slip and fall": (
        "- Premises cases often turn on notice: whether the property owner knew or should have known of the hazard.\n"
        "- Spoliation of evidence (e.g. surveillance) and incident reports are common focal points.\n"
        "- _Illustrative only — not legal advice or guaranteed outcomes._"
    ),
    "workplace injury": (
        "- Workplace matters may intersect workers' compensation exclusivity and third-party liability theories.\n"
        "- OSHA reports and employer policies often inform how claims are framed.\n"
        "- _Illustrative only — not legal advice or guaranteed outcomes._"
    ),
    "medical malpractice": (
        "- Med-mal matters typically require expert review of the standard of care and causation.\n"
        "- Filing windows (limitations) are often sensitive and fact-specific.\n"
        "- _Illustrative only — not legal advice or guaranteed outcomes._"
    ),
    "contract dispute": (
        "- Contract claims usually center on terms, performance, and available remedies (damages vs. equitable relief).\n"
        "- Written communications and amendments often drive outcomes in discovery.\n"
        "- _Illustrative only — not legal advice or guaranteed outcomes._"
    ),
    "employment law": (
        "- Employment disputes may involve timing of complaints, adverse actions, and comparator evidence.\n"
        "- Agency charges (where applicable) and personnel files are common evidence themes.\n"
        "- _Illustrative only — not legal advice or guaranteed outcomes._"
    ),
    "property dispute": (
        "- Property and landlord–tenant issues often depend on lease terms, notices, and local habitability rules.\n"
        "- Escrow, rent timelines, and written notices are frequent focal points.\n"
        "- _Illustrative only — not legal advice or guaranteed outcomes._"
    ),
    "assault": (
        "- Intentional tort matters may involve parallel criminal proceedings and different burdens of proof.\n"
        "- Insurance coverage for intentional acts is often limited; facts drive strategy.\n"
        "- _Illustrative only — not legal advice or guaranteed outcomes._"
    ),
    "family law": (
        "- Custody and support issues often depend on parenting plans, income disclosures, and the child's best-interest standard.\n"
        "- Jurisdiction (where the case may be filed) can turn on residence and prior orders.\n"
        "- _Illustrative only — not legal advice or guaranteed outcomes._"
    ),
    "immigration": (
        "- Immigration outcomes depend on category, deadlines, and agency discretion; relief may be discretionary or mandatory depending on facts.\n"
        "- Documentation of presence, relationships, and hardship themes is often central.\n"
        "- _Illustrative only — not legal advice or guaranteed outcomes._"
    ),
    "dui": (
        "- Impaired-driving cases often involve testing procedures, stop legality, and prior offenses affecting range of outcomes.\n"
        "- Administrative license actions may run on separate timelines from criminal proceedings.\n"
        "- _Illustrative only — not legal advice or guaranteed outcomes._"
    ),
    "criminal defense": (
        "- Criminal matters turn on elements of offenses, evidence admissibility, and procedural protections.\n"
        "- Plea structures and sentencing inputs vary widely by jurisdiction and record.\n"
        "- _Illustrative only — not legal advice or guaranteed outcomes._"
    ),
    "bankruptcy": (
        "- Bankruptcy options depend on income, assets, exemptions, and prior filings.\n"
        "- Automatic stay and creditor treatment follow chapter-specific rules.\n"
        "- _Illustrative only — not legal advice or guaranteed outcomes._"
    ),
    "employment law": (
        "- Employment claims often hinge on timing of protected activity, adverse actions, and comparator evidence.\n"
        "- Agency charge or notice requirements may apply before suit.\n"
        "- _Illustrative only — not legal advice or guaranteed outcomes._"
    ),
}

_DEFAULT_RESEARCH = (
    "- Civil intake patterns depend heavily on verified dates, locations, and documentary evidence.\n"
    "- Counsel should validate any limitations periods and insurance notice requirements early.\n"
    "- _Illustrative only — not legal advice or guaranteed outcomes._"
)


async def run_researcher(state: ConversationalState) -> ConversationalState:
    await asyncio.sleep(0)
    state = {**empty_conversational_state(), **dict(state)}
    state["logs"].append(agent_log("RESEARCHER", "Researching illustrative case themes..."))
    facts = state.get("extracted_facts", {})
    incident = str(facts.get("incident_type", "")).lower().strip()
    loc = str(facts.get("location", "")).strip()
    dt = str(facts.get("date", "")).strip()
    inj = str(facts.get("injuries", "")).strip()

    missing_core = sum(1 for x in (loc, dt) if not x)
    filled = sum(1 for x in (loc, dt, str(facts.get("incident_type", "")).strip(), inj) if x)

    if incident in {"car accident", "workplace injury", "slip and fall"} and missing_core == 0 and inj:
        plausibility = "high"
        reasoning = (
            f"Incident type is concrete ({incident}); core logistics present (location/date); "
            f"injury signal present. Coherence score ~{filled}/4 fields."
        )
    elif missing_core >= 2 or not incident:
        plausibility = "low"
        reasoning = (
            "Several core facts missing or incident type unclear; narrative coherence is weak for triage."
        )
    else:
        plausibility = "medium"
        reasoning = (
            f"Mixed completeness: {filled}/4 key fields filled; plausibility set to {plausibility} pending details."
        )

    state["plausibility"] = plausibility
    state["researcher_reasoning"] = reasoning
    state["logs"].append(agent_log("RESEARCHER", reasoning))
    state["logs"].append(agent_log("RESEARCHER", f"Incident plausibility: {plausibility}"))

    # Illustrative case themes for brief (LLM when available)
    case_summary = ""
    if get_client():
        try:
            user_block = json.dumps(
                {
                    "extracted_facts": facts,
                    "plausibility": plausibility,
                    "researcher_reasoning": reasoning,
                },
                ensure_ascii=False,
            )
            raw = await chat_text(system=CASE_RESEARCH_SYSTEM, user=user_block)
            case_summary = (raw or "").strip()
            if len(case_summary) > 4000:
                case_summary = case_summary[:3999] + "…"
            state["logs"].append(agent_log("RESEARCHER", "Generated illustrative case themes (LLM)"))
        except Exception as exc:
            case_summary = _HEURISTIC_BY_INCIDENT.get(incident, _DEFAULT_RESEARCH)
            state["logs"].append(agent_log("RESEARCHER", f"LLM research fallback ({exc!r})"))
    else:
        case_summary = _HEURISTIC_BY_INCIDENT.get(incident, _DEFAULT_RESEARCH)

    state["case_research_summary"] = case_summary
    return state
