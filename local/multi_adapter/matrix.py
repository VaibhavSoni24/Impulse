"""Multi-Adapter Experiment Matrix Generator (Section 12, 13, 14).

Constructs the canonical 8-member experiment matrix:
- MA0: All agents no adapter (frozen baseline control)
- MA1: Root adapter only (single-adapter control)
- MA2: Scout adapter only
- MA3: Reviewer adapter only
- MA4: Root + Scout adapters
- MA5: Root + Reviewer adapters
- MA6: Scout + Reviewer adapters
- MA7: Root + Scout + Reviewer adapters
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from local.multi_adapter.models import (
    AdapterRole,
    BASE_MODEL_IDENTIFIER,
    FROZEN_ROOT_PROMPT_HASH,
    MultiAdapterCandidateConfig,
    MultiAdapterExecutionStatus,
    RoleAdapterAssignment,
)


class MultiAdapterMatrixGenerator:
    """Constructs the canonical multi-adapter experiment matrix."""

    @classmethod
    def generate_matrix(
        cls,
        root_adapter: Optional[RoleAdapterAssignment] = None,
        scout_adapter: Optional[RoleAdapterAssignment] = None,
        reviewer_adapter: Optional[RoleAdapterAssignment] = None,
        benchmark_split: str = "dev",
    ) -> Dict[str, MultiAdapterCandidateConfig]:
        """Builds all 8 candidate configurations in the experiment matrix.

        If adapters are not provided, roles default to None (UNAVAILABLE).
        """
        def make_roles(r: bool, s: bool, rev: bool) -> Dict[str, Optional[Dict[str, Any]]]:
            return {
                AdapterRole.ROOT.value: root_adapter.to_dict() if r and root_adapter else None,
                AdapterRole.SCOUT.value: scout_adapter.to_dict() if s and scout_adapter else None,
                AdapterRole.REVIEWER.value: reviewer_adapter.to_dict() if rev and reviewer_adapter else None,
            }

        matrix_specs = [
            ("MA0", "All agents no adapter (baseline control)", False, False, False),
            ("MA1", "Root adapter only (single-adapter control)", True, False, False),
            ("MA2", "Scout adapter only (localization specialist)", False, True, False),
            ("MA3", "Reviewer adapter only (review specialist)", False, False, True),
            ("MA4", "Root + Scout adapters (coding + localization)", True, True, False),
            ("MA5", "Root + Reviewer adapters (coding + review)", True, False, True),
            ("MA6", "Scout + Reviewer adapters (specialists only)", False, True, True),
            ("MA7", "Root + Scout + Reviewer adapters (full specialization)", True, True, True),
        ]

        matrix: Dict[str, MultiAdapterCandidateConfig] = {}
        for cid, desc, r_flag, s_flag, rev_flag in matrix_specs:
            roles = make_roles(r_flag, s_flag, rev_flag)
            # Determine if candidate has required adapters or is blocked
            needed_adapters = (r_flag and not root_adapter) or (s_flag and not scout_adapter) or (rev_flag and not reviewer_adapter)
            if cid == "MA0":
                status = MultiAdapterExecutionStatus.NOT_RUN
                status_reason = "Ready baseline control; no adapter required."
            elif needed_adapters:
                status = MultiAdapterExecutionStatus.BLOCKED
                status_reason = "Blocked: required role adapter is unavailable."
            else:
                status = MultiAdapterExecutionStatus.NOT_RUN
                status_reason = "Configured and awaiting prerequisite validation."

            candidate = MultiAdapterCandidateConfig(
                candidate_id=cid,
                description=desc,
                base_model=BASE_MODEL_IDENTIFIER,
                roles=roles,
                status=status,
                prompt_hash=FROZEN_ROOT_PROMPT_HASH,
                retrieval_version="R0",
                testing_version="T0",
                recovery_version="REC0",
                topology="root_only" if not (s_flag or rev_flag) else "specialist_mesh",
                benchmark_split=benchmark_split,
                status_reason=status_reason,
            )
            matrix[cid] = candidate

        return matrix
