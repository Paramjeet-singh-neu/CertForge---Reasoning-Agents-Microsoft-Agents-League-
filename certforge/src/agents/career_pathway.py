"""Career Pathway Agent (capability layer 3).

Fires only when the Critic verdict is READY. Reads the Fabric IQ semantic model
to find the next certification in the learner's career path and previews a plan.
"""
from __future__ import annotations

from .. import config
from .base import Agent


class CareerPathwayAgent(Agent):
    name = "CareerPathwayAgent"

    def _run_mock(self, context: dict) -> dict:
        profile = context["learner_profile"]
        current = config.get_certification(profile["certification"])
        next_id = current.get("next_cert") if current else None
        next_cert = config.get_certification(next_id) if next_id else None

        weekly = profile.get("available_hours_per_week", 4)
        if next_cert:
            est_weeks = max(1, -(-next_cert["recommended_hours"] // weekly))
            pathway = {
                "completed": profile["certification"],
                "next": next_cert["id"],
                "next_name": next_cert["name"],
                "estimated_hours": next_cert["recommended_hours"],
                "estimated_weeks": est_weeks,
                "message": (
                    f"You're ready for {profile['certification']}. Next: {next_cert['id']} "
                    f"({next_cert['name']}). Estimated {next_cert['recommended_hours']} hrs over "
                    f"~{est_weeks} weeks at {weekly} hrs/week."
                ),
            }
        else:
            pathway = {
                "completed": profile["certification"],
                "next": None,
                "message": f"{profile['certification']} is the top of this track. Well done!",
            }

        return {
            "agent_name": self.name,
            "pathway": pathway,
            "career_timeline": profile.get("career_path", [profile["certification"]]),
            "reasoning_trace": self.trace(
                f"Queried Fabric IQ for next cert after {profile['certification']}",
                f"Next step: {pathway.get('next') or 'none (track complete)'}",
            ),
        }
