"""Deduplication and last-observation tracking for Safe Context Compaction (Stage 25).

Provides:
- FactObservationTracker: Tracks repeated repository facts, status, and deltas
- HypothesisTracker: Tracks hypothesis lifecycle (ACTIVE, SUPERSEDED, CONTRADICTED, RESOLVED)
- ObservationDeduplicator: Deduplicates identical observations with exact counters
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from local.context_compaction.fingerprints import sanitize_text
from local.context_compaction.models import (
    CompactionAction,
    CompactObservation,
    FactObservationSummary,
    HypothesisRecord,
    HypothesisStatus,
    ObservationType,
)


class FactObservationTracker:
    """Tracks repository architectural and environmental facts across turns.
    
    Exposes observation counts and changes since previous observation, avoiding
    repeated redundant fact dumps while preserving change history.
    """

    def __init__(self) -> None:
        self._facts: dict[str, FactObservationSummary] = {}
        self._history: dict[str, list[str]] = {}

    def record_fact(
        self,
        category: str,
        fact_key: str,
        value: str,
    ) -> tuple[FactObservationSummary, bool]:
        """Records an observation of a repository fact.
        
        Returns:
            (FactObservationSummary, is_new_or_changed: bool)
        """
        clean_key = sanitize_text(fact_key).strip().lower()
        clean_val = sanitize_text(value).strip()
        composite_key = f"{category.strip().lower()}:{clean_key}"

        now_iso = datetime.now(timezone.utc).isoformat()

        if composite_key not in self._facts:
            summary = FactObservationSummary(
                fact_key=composite_key,
                category=category,
                latest_value=clean_val,
                observation_count=1,
                first_observed_at=now_iso,
                last_observed_at=now_iso,
                changed_since_previous=False,
            )
            self._facts[composite_key] = summary
            self._history[composite_key] = [clean_val]
            return summary, True

        summary = self._facts[composite_key]
        summary.observation_count += 1
        summary.last_observed_at = now_iso

        if summary.latest_value == clean_val:
            summary.changed_since_previous = False
            return summary, False
        else:
            summary.changed_since_previous = True
            summary.latest_value = clean_val
            self._history[composite_key].append(clean_val)
            return summary, True

    def get_fact(self, composite_key: str) -> FactObservationSummary | None:
        """Retrieves a tracked fact summary by composite key."""
        return self._facts.get(composite_key.lower())

    def list_facts(self) -> list[FactObservationSummary]:
        """Returns all tracked fact summaries."""
        return list(self._facts.values())

    def get_history(self, composite_key: str) -> list[str]:
        """Returns value history for a given fact."""
        return list(self._history.get(composite_key.lower(), []))


class HypothesisTracker:
    """Manages root-cause hypothesis lifecycle and evidence tracking.
    
    Hard safety requirement:
    Never silently deletes or overwrites hypotheses. Preserves transition reasons
    and supporting/contradicting evidence for causal reasoning.
    """

    def __init__(self) -> None:
        self._hypotheses: dict[str, HypothesisRecord] = {}
        self._active_id: str | None = None

    def create_hypothesis(
        self,
        hypothesis_id: str,
        statement: str,
        supporting_evidence: list[str] | None = None,
    ) -> HypothesisRecord:
        """Registers a new active hypothesis."""
        clean_id = hypothesis_id.strip()
        clean_stmt = sanitize_text(statement).strip()

        rec = HypothesisRecord(
            hypothesis_id=clean_id,
            statement=clean_stmt,
            status=HypothesisStatus.ACTIVE,
            supporting_evidence=list(supporting_evidence or []),
        )
        self._hypotheses[clean_id] = rec
        self._active_id = clean_id
        return rec

    def supersede(
        self,
        hypothesis_id: str,
        superseded_by_id: str,
        reason: str = "",
    ) -> HypothesisRecord:
        """Marks a hypothesis as superseded by a refined or alternative hypothesis."""
        if hypothesis_id not in self._hypotheses:
            raise KeyError(f"Hypothesis {hypothesis_id} not found.")

        rec = self._hypotheses[hypothesis_id]
        rec.status = HypothesisStatus.SUPERSEDED
        rec.updated_at = datetime.now(timezone.utc).isoformat()
        rec.transition_reason = f"Superseded by {superseded_by_id}: {reason}".strip()

        if self._active_id == hypothesis_id:
            self._active_id = superseded_by_id
        return rec

    def contradict(
        self,
        hypothesis_id: str,
        contradicting_evidence: str,
        reason: str = "",
    ) -> HypothesisRecord:
        """Marks a hypothesis as contradicted by new empirical evidence."""
        if hypothesis_id not in self._hypotheses:
            raise KeyError(f"Hypothesis {hypothesis_id} not found.")

        rec = self._hypotheses[hypothesis_id]
        rec.status = HypothesisStatus.CONTRADICTED
        rec.updated_at = datetime.now(timezone.utc).isoformat()
        clean_ev = sanitize_text(contradicting_evidence).strip()
        rec.contradicting_evidence.append(clean_ev)
        rec.transition_reason = reason or f"Contradicted by evidence: {clean_ev[:100]}"

        if self._active_id == hypothesis_id:
            self._active_id = None
        return rec

    def resolve(
        self,
        hypothesis_id: str,
        resolving_evidence: str,
        reason: str = "",
    ) -> HypothesisRecord:
        """Marks a hypothesis as verified and resolved."""
        if hypothesis_id not in self._hypotheses:
            raise KeyError(f"Hypothesis {hypothesis_id} not found.")

        rec = self._hypotheses[hypothesis_id]
        rec.status = HypothesisStatus.RESOLVED
        rec.updated_at = datetime.now(timezone.utc).isoformat()
        clean_ev = sanitize_text(resolving_evidence).strip()
        rec.supporting_evidence.append(clean_ev)
        rec.transition_reason = reason or "Resolved and verified by tests"
        return rec

    def get_active(self) -> HypothesisRecord | None:
        """Returns the currently active hypothesis, if any."""
        if self._active_id and self._active_id in self._hypotheses:
            rec = self._hypotheses[self._active_id]
            if rec.status == HypothesisStatus.ACTIVE:
                return rec
        return None

    def get(self, hypothesis_id: str) -> HypothesisRecord | None:
        """Retrieves a specific hypothesis by ID."""
        return self._hypotheses.get(hypothesis_id)

    def list_all(self) -> list[HypothesisRecord]:
        """Returns all hypotheses in chronological registration order."""
        return list(self._hypotheses.values())


class ObservationDeduplicator:
    """Deduplicates repeated observations using deterministic fingerprints.
    
    Exact duplicate observations increment repetition counters rather than
    multiplying context size, while distinct or changed observations are kept intact.
    """

    def __init__(self) -> None:
        self._observations: list[CompactObservation] = []
        # Map: fingerprint -> index in self._observations
        self._index: dict[str, int] = {}

    @staticmethod
    def compute_observation_fingerprint(
        obs_type: ObservationType,
        source: str,
        content: str,
    ) -> str:
        """Computes deterministic fingerprint based on type, source, and exact content."""
        clean_src = source.strip().lower()
        key_str = f"{obs_type.value}|{clean_src}|{content}"
        return hashlib.sha256(key_str.encode("utf-8")).hexdigest()

    def record_observation(
        self,
        obs_type: ObservationType,
        action: CompactionAction,
        source: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[CompactObservation, bool]:
        """Records an observation.
        
        If exact duplicate: increments counter on canonical record.
        If new: creates and stores new CompactObservation.
        
        Returns:
            (CompactObservation, is_new: bool)
        """
        clean_content = sanitize_text(content)
        fp = self.compute_observation_fingerprint(obs_type, source, clean_content)
        now_iso = datetime.now(timezone.utc).isoformat()

        if fp in self._index:
            idx = self._index[fp]
            canonical = self._observations[idx]
            canonical.repetition_count += 1
            canonical.last_observed_at = now_iso
            return canonical, False

        # Create new compact observation
        preview = clean_content[:300] + ("..." if len(clean_content) > 300 else "")
        summary = f"[{obs_type.value} from {source}] (len={len(clean_content)})"

        obs = CompactObservation(
            observation_type=obs_type,
            action=action,
            fingerprint=fp,
            source=source,
            raw_content_preview=preview,
            compacted_summary=summary,
            repetition_count=1,
            first_observed_at=now_iso,
            last_observed_at=now_iso,
            is_canonical=True,
            metadata=dict(metadata or {}),
        )
        self._observations.append(obs)
        self._index[fp] = len(self._observations) - 1
        return obs, True

    def list_observations(self) -> list[CompactObservation]:
        """Returns all deduplicated observations."""
        return list(self._observations)

    def total_raw_count(self) -> int:
        """Returns total count of raw observations received (including duplicates)."""
        return sum(o.repetition_count for o in self._observations)

    def unique_count(self) -> int:
        """Returns count of distinct unique observations."""
        return len(self._observations)

    def duplicate_count(self) -> int:
        """Returns number of collapsed duplicate observations."""
        return self.total_raw_count() - self.unique_count()
