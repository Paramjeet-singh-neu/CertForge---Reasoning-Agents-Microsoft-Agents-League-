"""Agent 2: Learning Path Curator.

Grounding: Foundry IQ knowledge base + Microsoft Learn MCP server.

In mock mode we synthesise cited modules from the Fabric IQ skill list so the
output shape matches what the real (Foundry IQ + MS Learn) version will return.
Every recommendation carries a source — the spec requires cited content, not
free-text suggestions.
"""
from __future__ import annotations

from .. import config
from .base import Agent

# Synthetic stand-in for what the Microsoft Learn MCP server would return.
# In Azure mode this is replaced by a real MCP tool call.
_MODULE_HOURS = {"lab": 3, "reading": 2, "video": 1}


class LearningPathCurator(Agent):
    name = "LearningPathCurator"

    def _run_mock(self, context: dict) -> dict:
        profile = context["learner_profile"]
        cert = config.get_certification(profile["certification"])
        if not cert:
            return {"agent_name": self.name, "confidence": 0.0, "error": "unknown certification"}

        weak = set(context.get("known_weak_areas", []))
        skills_out, sources, total_hours = [], set(), 0
        for skill in cert["skills"]:
            priority = "high" if skill in weak else "medium"
            modules = self._modules_for(skill, cert["id"])
            for m in modules:
                total_hours += m["estimated_hours"]
                sources.add(m["source"])
            skills_out.append({"skill": skill, "priority": priority, "modules": modules})

        return {
            "agent_name": self.name,
            "confidence": 0.89,
            "certification": cert["id"],
            "required_skills": skills_out,
            "prerequisites": [cert["prerequisite"]] if cert["prerequisite"] else [],
            "total_estimated_hours": total_hours,
            "sources_cited": sorted(sources),
            "reasoning_trace": self.trace(
                f"Queried Foundry IQ for {cert['id']} skill requirements",
                f"Mapped {len(cert['skills'])} skills to learning modules",
                f"Pulled module metadata from Microsoft Learn (MCP)",
                f"Total estimated effort: {total_hours} hrs across {len(cert['skills'])} skills",
            ),
        }

    def _modules_for(self, skill: str, cert_id: str) -> list[dict]:
        """Two cited modules per skill (a reading + a hands-on lab)."""
        slug = skill.lower().replace(" ", "-")
        return [
            {
                "title": f"{skill} fundamentals for {cert_id}",
                "source": "Foundry IQ / MS Learn",
                "url": f"https://learn.microsoft.com/training/modules/{slug}-{cert_id.lower()}",
                "estimated_hours": _MODULE_HOURS["reading"],
                "type": "reading",
            },
            {
                "title": f"{skill} hands-on lab",
                "source": "MS Learn MCP",
                "url": f"https://learn.microsoft.com/training/modules/{slug}-lab",
                "estimated_hours": _MODULE_HOURS["lab"],
                "type": "lab",
            },
        ]
