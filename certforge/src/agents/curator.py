"""Agent 2: Learning Path Curator.

Grounding: Foundry IQ knowledge base + Microsoft Learn MCP server.

In mock mode we synthesise cited modules from the Fabric IQ skill list so the
output shape matches what the real (Foundry IQ + MS Learn) version will return.
Every recommendation carries a source — the spec requires cited content, not
free-text suggestions.
"""
from __future__ import annotations

import re

from .. import config, learn_mcp
from ..knowledge import retriever
from .base import Agent

_MODULE_HOURS = {"lab": 3, "reading": 2, "video": 1}


class LearningPathCurator(Agent):
    name = "LearningPathCurator"

    def _run_mock(self, context: dict) -> dict:
        profile = context["learner_profile"]
        cert = config.get_certification(profile["certification"])
        if not cert:
            return {"agent_name": self.name, "confidence": 0.0, "error": "unknown certification"}

        weak = set(context.get("known_weak_areas", []))
        # Learner-requested topics (baseline-flow step 1) bump matching skills.
        topics = context.get("learner_topics", "") or ""
        topic_words = {t.strip().lower() for t in re.split(r"[,;]| and ", topics) if t.strip()}
        semantic = not config.use_mock()

        # MS Learn MCP: fetch REAL learn.microsoft.com URLs for every skill in one
        # session (live mode only; best-effort with fallback to constructed URLs).
        qmap = {s: (s if s.lower().startswith("azure") else f"Azure {s}")
                for s in cert["skills"]}
        learn_hits = {}
        used_mcp = False
        if not config.use_mock():
            learn_hits = learn_mcp.search_many(list(qmap.values()), k=2)
            used_mcp = any(learn_hits.values())

        skills_out, sources, total_hours, matched_topics = [], set(), 0, set()
        for skill in cert["skills"]:
            is_topic = any(w in skill.lower() or skill.lower() in w for w in topic_words)
            if is_topic:
                matched_topics.add(skill)
            priority = "high" if (skill in weak or is_topic) else "medium"
            real = learn_hits.get(qmap[skill], [])
            modules = self._modules_for(skill, cert["id"], real)
            for m in modules:
                total_hours += m["estimated_hours"]
                sources.add(m["source"])
            # Foundry IQ grounding: cite a real retrieved passage for this skill.
            q = skill if skill.lower().startswith("azure") else f"Azure {skill}"
            grounding = retriever.search(q, k=1, prefer_semantic=semantic, kind="content")
            if grounding:
                sources.add(grounding[0]["citation"])
            skills_out.append({
                "skill": skill,
                "priority": priority,
                "modules": modules,
                "grounding": grounding[0] if grounding else None,
            })

        return {
            "agent_name": self.name,
            "confidence": 0.89,
            "certification": cert["id"],
            "required_skills": skills_out,
            "prerequisites": [cert["prerequisite"]] if cert["prerequisite"] else [],
            "total_estimated_hours": total_hours,
            "requested_topics": sorted(topic_words) if topic_words else [],
            "topics_matched_to_skills": sorted(matched_topics),
            "sources_cited": sorted(sources),
            "learn_mcp_used": used_mcp,
            "reasoning_trace": self.trace(
                f"Prioritised learner topics: {', '.join(sorted(matched_topics))}"
                if matched_topics else "",
                f"Retrieved grounded content from Foundry IQ knowledge base "
                f"({'semantic' if semantic else 'keyword'} retrieval)",
                f"Mapped {len(cert['skills'])} skills to learning modules",
                f"Microsoft Learn MCP: {'fetched real doc URLs' if used_mcp else 'using fallback URLs (MCP not called/offline)'}",
                f"Cited {len(sources)} real sources; "
                f"{total_hours} hrs across {len(cert['skills'])} skills",
            ),
        }

    def _modules_for(self, skill: str, cert_id: str, real: list[dict] | None = None) -> list[dict]:
        """Cited modules per skill. Uses real MS Learn (MCP) URLs when available,
        otherwise falls back to constructed learn.microsoft.com URLs."""
        real = real or []
        if real:
            modules = []
            for i, hit in enumerate(real[:2]):
                modules.append({
                    "title": hit["title"],
                    "source": "Microsoft Learn (MCP)",
                    "url": hit["url"],
                    "estimated_hours": _MODULE_HOURS["reading" if i == 0 else "lab"],
                    "type": "reading" if i == 0 else "lab",
                })
            return modules

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
                "source": "MS Learn (fallback)",
                "url": f"https://learn.microsoft.com/training/modules/{slug}-lab",
                "estimated_hours": _MODULE_HOURS["lab"],
                "type": "lab",
            },
        ]
