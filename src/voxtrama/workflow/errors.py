"""Errors raised when a workflow definition fails validation."""

from __future__ import annotations


class WorkflowError(Exception):
    """Base class for every error a workflow definition can raise."""


class WorkflowValidationError(WorkflowError):
    """Raised when the YAML does not match the Workflow schema."""


class SkillNotFoundError(WorkflowError):
    """Raised when a step references a skill, or skill version, that does not exist."""


class UnknownStepError(WorkflowError):
    """Raised when a step points at a step id that is not in the workflow."""


class CyclicDependencyError(WorkflowError):
    """Raised when steps' depends_on edges form a cycle."""
