"""Custom exceptions for Stage 39 LoRA Training subsystem.

Defines strict gate and safety exceptions:
- DataGateBlockedError: Raised when training data is missing, empty, or unverified.
- HardwareGateBlockedError: Raised when hardware or software stack is incompatible.
- InvarianceViolationError: Raised when training configuration mutates frozen baseline dimensions.
- FixtureSafetyError: Raised when synthetic fixtures attempt to enter real training pipeline.
- UnresolvedHyperparameterError: Raised when mandatory hyperparameters are unselected or invalid.
"""

from __future__ import annotations


class LoRATrainingError(Exception):
    """Base exception for all LoRA training subsystem errors."""


class DataGateBlockedError(LoRATrainingError):
    """Raised when data gate prohibits training execution."""

    def __init__(self, reason: str, details: dict | None = None) -> None:
        super().__init__(f"Data Gate Blocked: {reason}")
        self.reason = reason
        self.details = details or {}


class HardwareGateBlockedError(LoRATrainingError):
    """Raised when hardware requirements are not satisfied."""

    def __init__(self, reason: str, classification: str) -> None:
        super().__init__(f"Hardware Gate Blocked [{classification}]: {reason}")
        self.reason = reason
        self.classification = classification


class InvarianceViolationError(LoRATrainingError):
    """Raised when a candidate configuration violates frozen baseline invariance."""

    def __init__(self, violations: list[str]) -> None:
        super().__init__(f"Invariance Violation Detected: {'; '.join(violations)}")
        self.violations = violations


class FixtureSafetyError(LoRATrainingError):
    """Raised when fixture data attempts to enter actual training or weight generation."""

    def __init__(self, message: str) -> None:
        super().__init__(f"Fixture Safety Violation: {message}")


class UnresolvedHyperparameterError(LoRATrainingError):
    """Raised when required training hyperparameters are missing or unselected."""

    def __init__(self, unselected_fields: list[str]) -> None:
        super().__init__(f"Unresolved Hyperparameters: {', '.join(unselected_fields)}")
        self.unselected_fields = unselected_fields
