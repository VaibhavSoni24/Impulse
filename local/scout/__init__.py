"""Scout Agent module (Stage 21 / Candidates E_S1 and E_S2).

Exports models, triggers, and controller for read-only localization specialist.
"""

from local.scout.controller import ScoutControllerV1
from local.scout.models import ScoutPolicy, ScoutResult, ScoutStatus
from local.scout.trigger import ScoutTriggerContext, evaluate_scout_trigger, is_localization_uncertain

__all__ = [
    "ScoutControllerV1",
    "ScoutPolicy",
    "ScoutResult",
    "ScoutStatus",
    "ScoutTriggerContext",
    "evaluate_scout_trigger",
    "is_localization_uncertain",
]
