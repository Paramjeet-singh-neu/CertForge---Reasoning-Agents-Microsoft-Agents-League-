"""Fabric IQ layer — the semantic foundation (ontology) for CertForge.

Fabric IQ is Microsoft's semantic layer: an Ontology connecting people, roles,
processes, and rules into unified business entities and relationships so agents
reason with shared meaning. We model that ontology in `data/semantic_model.json`
(entities, relationships, and business rules) and expose it here as a named layer
— mirroring `work_iq.py` and `foundry_iq.py`.

Entities: Learner, Role, Certification, Skill, SkillGap, ReadinessScore,
StudyPlan, Team. Rules: readiness, prerequisite, role alignment, capacity.

Production note: the same interface maps to a managed Fabric IQ Ontology item in
Microsoft Fabric (graph-backed). We use the JSON semantic model because Fabric
requires a Fabric/Power-BI tenant capacity unavailable here.
"""
from __future__ import annotations

from . import config


# --- entity accessors ------------------------------------------------------
def certification(cert_id: str) -> dict | None:
    return config.get_certification(cert_id)


def role(role_name: str) -> dict | None:
    return config.get_role(role_name)


def skills_for(cert_id: str) -> list[str]:
    c = certification(cert_id)
    return c["skills"] if c else []


def pass_threshold(cert_id: str) -> int:
    c = certification(cert_id)
    return c["pass_threshold"] if c else 75


def prerequisite(cert_id: str) -> str | None:
    c = certification(cert_id)
    return c.get("prerequisite") if c else None


def next_cert(cert_id: str) -> str | None:
    c = certification(cert_id)
    return c.get("next_cert") if c else None


def primary_cert_for_role(role_name: str) -> str | None:
    r = role(role_name)
    return r.get("primary_cert") if r else None


# --- business rules (from the ontology) ------------------------------------
def _rule(rule_id: str) -> dict:
    for r in config.semantic_model().get("ontology", {}).get("rules", []):
        if r["id"] == rule_id:
            return r
    return {}


def skill_gaps(cert_id: str, skill_scores: list[dict]) -> list[str]:
    """SkillGap entity: skills scoring below the cert's pass threshold."""
    thr = pass_threshold(cert_id)
    return [s["skill"] for s in skill_scores if s.get("score", 0) < thr]


def is_ready(cert_id: str, overall_score: float, skill_scores: list[dict]) -> bool:
    """Apply the 'readiness' rule: score >= threshold AND no skill below the floor."""
    rule = _rule("readiness")
    floor = rule.get("min_skill_score", 65)
    if overall_score < pass_threshold(cert_id):
        return False
    return all(s.get("score", 0) >= floor for s in skill_scores)


def prerequisite_satisfied(cert_id: str, completed_certs: list[str]) -> bool:
    """Apply the 'prerequisite' rule before recommending a certification."""
    pre = prerequisite(cert_id)
    return pre is None or pre in (completed_certs or [])


# --- ontology introspection (for UI / explainability) ----------------------
def ontology() -> dict:
    """Return the entities, relationships, and rules — for display/explainability."""
    return config.semantic_model().get("ontology", {})
