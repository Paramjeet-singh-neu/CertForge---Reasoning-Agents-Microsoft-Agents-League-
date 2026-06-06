"""Career Pathway Agent (capability layer 3).

Fires only when the Critic verdict is READY. Reads the Fabric IQ semantic model
to find the next certification in the learner's career path and previews a plan.
"""
from __future__ import annotations

from .. import config, fabric_iq
from .base import Agent


class CareerPathwayAgent(Agent):
    name = "CareerPathwayAgent"

    def _run_mock(self, context: dict) -> dict:
        profile = context["learner_profile"]
        completed = profile["certification"]
        # Fabric IQ ontology: next cert + the prerequisite RULE.
        next_id = fabric_iq.next_cert(completed)
        next_cert = config.get_certification(next_id) if next_id else None
        # The learner has just completed `completed`, so the next cert's
        # prerequisite is satisfied iff it requires `completed` (or nothing).
        prereq_ok = next_cert is None or fabric_iq.prerequisite_satisfied(
            next_id, [completed])

        weekly = profile.get("available_hours_per_week", 4)
        if next_cert and prereq_ok:
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
                f"Queried Fabric IQ ontology for next cert after {completed}",
                f"Applied prerequisite rule: {next_id or 'n/a'} prerequisite satisfied = {prereq_ok}",
                f"Next step: {pathway.get('next') or 'none (track complete)'}",
            ),
        }
