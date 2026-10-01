"""Configuration Validation and Role Isolation for Stage 41 (Section 8, 9, 18, 19).

Validates:
- Role isolation: adapter is loaded strictly for its declared role.
- Base model invariance: all role adapters must match gemma-4-31b-it-qat-w4a16-ct.
- Conflict detection:
  - Role mismatch (e.g. review adapter assigned to localization role).
  - Duplicate assignments or undefined roles.
  - Unvalidated adapter assignment.
"""

from __future__ import annotations

from typing import List, Tuple

from local.multi_adapter.errors import (
    BaseModelMismatchError,
    RoleConflictError,
    UnvalidatedAdapterError,
)
from local.multi_adapter.models import (
    AdapterRole,
    AdapterStatus,
    BASE_MODEL_IDENTIFIER,
    MultiAdapterCandidateConfig,
    RoleAdapterAssignment,
)


class MultiAdapterConfigValidator:
    """Audits multi-adapter configurations for structural integrity and role isolation."""

    @classmethod
    def validate_candidate_config(cls, candidate: MultiAdapterCandidateConfig) -> Tuple[bool, List[str]]:
        """Audits candidate configuration against all isolation and compatibility rules.

        Returns (is_valid, list_of_violations).
        """
        violations: List[str] = []

        # 1. Base model validation
        if candidate.base_model != BASE_MODEL_IDENTIFIER:
            violations.append(
                f"Candidate base model '{candidate.base_model}' != expected '{BASE_MODEL_IDENTIFIER}'"
            )

        # 2. Audit each assigned role
        valid_role_names = {r.value for r in AdapterRole}

        for role_name, assignment_data in candidate.roles.items():
            if role_name not in valid_role_names:
                violations.append(f"Unsupported agent role '{role_name}' in configuration.")
                continue

            if assignment_data is None:
                continue  # Role unassigned, valid

            # Role assigned: inspect fields
            assigned_role = assignment_data.get("role")
            if assigned_role != role_name:
                violations.append(
                    f"Role mismatch: slot '{role_name}' contains adapter declared for role '{assigned_role}'."
                )

            # Check allowed agent roles
            allowed_roles = assignment_data.get("allowed_agent_roles", [])
            if role_name not in allowed_roles:
                violations.append(
                    f"Isolation violation: adapter does not permit assignment to role '{role_name}' (allowed: {allowed_roles})."
                )

            # Check base model of adapter
            adapter_model = assignment_data.get("base_model", "")
            if adapter_model and adapter_model != BASE_MODEL_IDENTIFIER:
                violations.append(
                    f"Adapter base model '{adapter_model}' is incompatible with candidate '{BASE_MODEL_IDENTIFIER}'."
                )

            # Check status of adapter
            status = assignment_data.get("status")
            if status != AdapterStatus.VALIDATED.value:
                violations.append(
                    f"Role '{role_name}' references unvalidated adapter with status '{status}' (must be VALIDATED)."
                )

        return (len(violations) == 0, violations)

    @classmethod
    def validate_role_assignment(cls, assignment: RoleAdapterAssignment) -> Tuple[bool, List[str]]:
        """Validates a single RoleAdapterAssignment."""
        violations: List[str] = []

        if assignment.base_model != BASE_MODEL_IDENTIFIER:
            violations.append(
                f"Adapter base model '{assignment.base_model}' != expected '{BASE_MODEL_IDENTIFIER}'"
            )

        if assignment.role not in assignment.allowed_agent_roles:
            violations.append(
                f"Target role '{assignment.role.value}' not in allowed roles: {[r.value for r in assignment.allowed_agent_roles]}"
            )

        if assignment.status != AdapterStatus.VALIDATED:
            violations.append(f"Adapter status is '{assignment.status.value}', expected VALIDATED.")

        return (len(violations) == 0, violations)
