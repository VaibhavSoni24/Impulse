"""Deterministic Candidate Comparison and Dimension Diff Engine (Section 11).

Compares two CandidateManifest instances to identify:
- Exact changed dimensions and unchanged dimensions
- Detailed hash differences across prompt, skills, tools, and configs
- Configuration and sampling setting deltas
- Multi-dimensional experiment warnings
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from local.versioning.models import CandidateManifest, ComparisonResult

# Major experiment dimensions tracked for single-variable control
MAJOR_DIMENSIONS = [
    "root_prompt",
    "retrieval",
    "testing",
    "recovery",
    "topology",
    "skills",
    "tools",
    "base_model",
    "adapter",
    "benchmark",
    "sampling",
    "runtime",
]


class CandidateComparator:
    """Performs deterministic comparison between parent and candidate manifests."""

    @staticmethod
    def compare(parent: Optional[CandidateManifest], candidate: CandidateManifest) -> ComparisonResult:
        """Compares parent manifest with candidate manifest."""
        if parent is None:
            # Baseline candidate has no parent
            return ComparisonResult(
                parent_id=None,
                candidate_id=candidate.candidate_id,
                is_multi_dimension=False,
                changed_dimensions=[candidate.primary_dimension],
                unchanged_dimensions=[],
                hash_changes={},
                configuration_changes={},
                benchmark_changes={},
                adapter_changes={},
                runtime_changes={},
                warnings=["Baseline candidate with no parent comparison."],
            )

        changed_dims: List[str] = []
        unchanged_dims: List[str] = []
        hash_changes: Dict[str, Dict[str, Optional[str]]] = {}
        config_changes: Dict[str, Dict[str, Any]] = {}
        benchmark_changes: Dict[str, Dict[str, Optional[str]]] = {}
        adapter_changes: Dict[str, Dict[str, Optional[str]]] = {}
        runtime_changes: Dict[str, Dict[str, Any]] = {}
        warnings: List[str] = []

        # 1. Root prompt hash
        if parent.root_prompt_hash != candidate.root_prompt_hash:
            changed_dims.append("root_prompt")
            hash_changes["root_prompt"] = {
                "parent": parent.root_prompt_hash,
                "candidate": candidate.root_prompt_hash,
            }
        else:
            unchanged_dims.append("root_prompt")

        # 2. Retrieval version
        if parent.retrieval_version != candidate.retrieval_version:
            changed_dims.append("retrieval")
            config_changes["retrieval_version"] = {
                "parent": parent.retrieval_version,
                "candidate": candidate.retrieval_version,
            }
        else:
            unchanged_dims.append("retrieval")

        # 3. Testing version
        if parent.testing_version != candidate.testing_version:
            changed_dims.append("testing")
            config_changes["testing_version"] = {
                "parent": parent.testing_version,
                "candidate": candidate.testing_version,
            }
        else:
            unchanged_dims.append("testing")

        # 4. Recovery version
        if parent.recovery_version != candidate.recovery_version:
            changed_dims.append("recovery")
            config_changes["recovery_version"] = {
                "parent": parent.recovery_version,
                "candidate": candidate.recovery_version,
            }
        else:
            unchanged_dims.append("recovery")

        # 5. Topology
        if parent.topology != candidate.topology:
            changed_dims.append("topology")
            config_changes["topology"] = {
                "parent": parent.topology,
                "candidate": candidate.topology,
            }
        else:
            unchanged_dims.append("topology")

        # 6. Skills
        if parent.skill_hashes != candidate.skill_hashes:
            changed_dims.append("skills")
            hash_changes["skills"] = {
                "parent_keys": str(sorted(parent.skill_hashes.keys())),
                "candidate_keys": str(sorted(candidate.skill_hashes.keys())),
            }
        else:
            unchanged_dims.append("skills")

        # 7. Tool contracts
        if parent.tool_contract_hashes != candidate.tool_contract_hashes:
            changed_dims.append("tools")
            hash_changes["tools"] = {
                "parent_keys": str(sorted(parent.tool_contract_hashes.keys())),
                "candidate_keys": str(sorted(candidate.tool_contract_hashes.keys())),
            }
        else:
            unchanged_dims.append("tools")

        # 8. Base model
        if parent.base_model != candidate.base_model:
            changed_dims.append("base_model")
            config_changes["base_model"] = {
                "parent": parent.base_model,
                "candidate": candidate.base_model,
            }
        else:
            unchanged_dims.append("base_model")

        # 9. Adapter
        if parent.adapter_id != candidate.adapter_id or parent.adapter_sha256 != candidate.adapter_sha256:
            changed_dims.append("adapter")
            adapter_changes["adapter_id"] = {
                "parent": parent.adapter_id,
                "candidate": candidate.adapter_id,
            }
            adapter_changes["adapter_sha256"] = {
                "parent": parent.adapter_sha256,
                "candidate": candidate.adapter_sha256,
            }
        else:
            unchanged_dims.append("adapter")

        # 10. Benchmark splits
        bench_diff = False
        for b_attr in ["benchmark_manifest_hash", "dev_split_hash", "validation_split_hash", "held_out_split_hash"]:
            p_val = getattr(parent, b_attr, None)
            c_val = getattr(candidate, b_attr, None)
            if p_val != c_val:
                bench_diff = True
                benchmark_changes[b_attr] = {"parent": p_val, "candidate": c_val}
        if bench_diff:
            changed_dims.append("benchmark")
            warnings.append("WARNING: Benchmark split definition changed between parent and candidate.")
        else:
            unchanged_dims.append("benchmark")

        # 11. Sampling
        if parent.sampling_settings != candidate.sampling_settings:
            changed_dims.append("sampling")
            config_changes["sampling_settings"] = {
                "parent": str(parent.sampling_settings),
                "candidate": str(candidate.sampling_settings),
            }
        else:
            unchanged_dims.append("sampling")

        # Check multi-dimension rule
        is_multi = len(changed_dims) > 1
        if is_multi:
            warnings.append(
                f"MULTI_DIMENSION_EXPERIMENT: {len(changed_dims)} dimensions changed simultaneously: {changed_dims}"
            )

        return ComparisonResult(
            parent_id=parent.candidate_id,
            candidate_id=candidate.candidate_id,
            is_multi_dimension=is_multi,
            changed_dimensions=changed_dims,
            unchanged_dimensions=unchanged_dims,
            hash_changes=hash_changes,
            configuration_changes=config_changes,
            benchmark_changes=benchmark_changes,
            adapter_changes=adapter_changes,
            runtime_changes=runtime_changes,
            warnings=warnings,
        )
