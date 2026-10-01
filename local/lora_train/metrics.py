"""Metrics Tracking and Telemetry Subsystem for Stage 39 LoRA Training (Section 21).

Records real training metrics:
- Training loss and validation loss
- Steps completed, total steps, and epochs
- Learning rate and effective batch size
- Wall-clock runtime and step throughput
- Peak GPU memory (if available)

Enforces empirical recording:
- When a run is blocked or unexecuted, metrics are marked NOT_RUN / UNAVAILABLE.
- Zero fabrication of scores or loss values.
"""

from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any, Dict, Optional

from local.lora_train.models import TrainingMetrics, TrainingStatus


class MetricsTracker:
    """Tracks training steps, loss values, and timing telemetry."""

    def __init__(self) -> None:
        self.metrics = TrainingMetrics()
        self._start_time: Optional[float] = None

    def start(self) -> None:
        """Starts the execution stopwatch."""
        self._start_time = time.monotonic()

    def record_step(
        self, step: int, total_steps: int, loss: float, lr: float, epoch: float
    ) -> None:
        """Records telemetry for a single training step."""
        self.metrics.steps_completed = step
        self.metrics.total_steps = total_steps
        self.metrics.training_loss = round(loss, 6)
        self.metrics.learning_rate = lr
        self.metrics.epochs_completed = round(epoch, 4)

        if self._start_time is not None:
            elapsed = time.monotonic() - self._start_time
            self.metrics.runtime_ms = round(elapsed * 1000, 2)
            if elapsed > 0:
                self.metrics.throughput_examples_sec = round(step / elapsed, 2)

    def finish(self, status: str = TrainingStatus.TRAINING_COMPLETED.value) -> TrainingMetrics:
        """Concludes metric recording and sets the final execution status."""
        self.metrics.status = status
        if self._start_time is not None and self.metrics.runtime_ms == 0.0:
            self.metrics.runtime_ms = round((time.monotonic() - self._start_time) * 1000, 2)
        return self.metrics

    def save_metrics(self, output_path: Path) -> None:
        """Writes metrics.json to the output directory."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.metrics.to_dict(), f, indent=2, sort_keys=True)


def get_blocked_metrics() -> TrainingMetrics:
    """Returns a deterministic unexecuted metrics object for blocked runs."""
    return TrainingMetrics(status=TrainingStatus.NOT_RUN.value)
