"""Debugger agent package for IMPULSE (Stage 22).

Provides:
- DebuggerStatus, DebuggerPolicy, DebuggerResult (models.py)
- DebuggerTriggerContext, is_difficult_failure, evaluate_debugger_trigger (trigger.py)
- DebuggerControllerV1 (controller.py)
"""

from local.debugger.controller import DebuggerControllerV1
from local.debugger.models import DebuggerPolicy, DebuggerResult, DebuggerStatus
from local.debugger.trigger import (
    DebuggerTriggerContext,
    evaluate_debugger_trigger,
    is_difficult_failure,
)

__all__ = [
    "DebuggerControllerV1",
    "DebuggerPolicy",
    "DebuggerResult",
    "DebuggerStatus",
    "DebuggerTriggerContext",
    "evaluate_debugger_trigger",
    "is_difficult_failure",
]
