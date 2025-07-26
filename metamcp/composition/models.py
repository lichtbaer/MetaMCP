"""
Workflow Models

This module defines the data models for workflow composition and orchestration.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class WorkflowStatus(str, Enum):
    """Workflow execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    """Step execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class StepType(str, Enum):
    """Step types for workflow composition."""

    TOOL_CALL = "tool_call"
    CONDITION = "condition"
    PARALLEL = "parallel"
    LOOP = "loop"
    DELAY = "delay"
    HTTP_REQUEST = "http_request"


class ConditionOperator(str, Enum):
    """Condition operators for workflow branching."""

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"


@dataclass
class WorkflowStep:
    """A step in a workflow."""

    id: str
    name: str
    step_type: StepType
    config: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    condition: dict[str, Any] | None = None
    retry_config: dict[str, Any] | None = None
    timeout: int | None = None
    parallel: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowState:
    """State of a workflow execution."""

    workflow_id: str
    status: WorkflowStatus
    current_step: str | None = None
    step_results: dict[str, Any] = field(default_factory=dict)
    step_statuses: dict[str, StepStatus] = field(default_factory=dict)
    variables: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class WorkflowDefinition(BaseModel):
    """Definition of a workflow."""

    id: str = Field(..., description="Unique workflow identifier")
    name: str = Field(..., description="Human-readable workflow name")
    description: str | None = Field(None, description="Workflow description")
    version: str = Field("1.0.0", description="Workflow version")

    # Workflow structure
    steps: list[WorkflowStep] = Field(..., description="Workflow steps")
    entry_point: str = Field(..., description="Entry point step ID")

    # Configuration
    timeout: int | None = Field(None, description="Overall workflow timeout in seconds")
    retry_config: dict[str, Any] | None = Field(
        None, description="Global retry configuration"
    )
    parallel_execution: bool = Field(
        False, description="Enable parallel step execution"
    )

    # Metadata
    tags: list[str] = Field(default_factory=list, description="Workflow tags")
    categories: list[str] = Field(
        default_factory=list, description="Workflow categories"
    )
    author: str | None = Field(None, description="Workflow author")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Security
    required_permissions: list[str] = Field(
        default_factory=list, description="Required permissions"
    )
    security_level: str = Field("medium", description="Security level")

    model_config = {"arbitrary_types_allowed": True}


class WorkflowExecutionRequest(BaseModel):
    """Request to execute a workflow."""

    workflow_id: str = Field(..., description="Workflow to execute")
    input_data: dict[str, Any] = Field(default_factory=dict, description="Input data")
    variables: dict[str, Any] = Field(
        default_factory=dict, description="Workflow variables"
    )
    user_id: str | None = Field(None, description="User executing the workflow")
    timeout: int | None = Field(None, description="Execution timeout")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class WorkflowExecutionResult(BaseModel):
    """Result of workflow execution."""

    execution_id: str = Field(..., description="Unique execution identifier")
    workflow_id: str = Field(..., description="Executed workflow ID")
    status: WorkflowStatus = Field(..., description="Execution status")
    result: dict[str, Any] | None = Field(None, description="Execution result")
    error: str | None = Field(None, description="Error message if failed")
    step_results: dict[str, Any] = Field(
        default_factory=dict, description="Individual step results"
    )
    execution_time: float | None = Field(
        None, description="Total execution time in seconds"
    )
    started_at: datetime = Field(..., description="Execution start time")
    completed_at: datetime | None = Field(None, description="Execution completion time")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class StepExecutionResult(BaseModel):
    """Result of a single step execution."""

    step_id: str = Field(..., description="Step identifier")
    status: StepStatus = Field(..., description="Step status")
    result: Any | None = Field(None, description="Step result")
    error: str | None = Field(None, description="Error message if failed")
    execution_time: float = Field(..., description="Step execution time in seconds")
    started_at: datetime = Field(..., description="Step start time")
    completed_at: datetime = Field(..., description="Step completion time")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class Condition(BaseModel):
    """Condition for workflow branching."""

    operator: ConditionOperator = Field(..., description="Condition operator")
    left_operand: str | Any = Field(..., description="Left operand (variable or value)")
    right_operand: str | Any | None = Field(None, description="Right operand")
    variable_path: str | None = Field(
        None, description="Path to variable in workflow state"
    )


class RetryConfig(BaseModel):
    """Configuration for retry behavior."""

    max_attempts: int = Field(3, description="Maximum retry attempts")
    initial_delay: float = Field(1.0, description="Initial delay in seconds")
    max_delay: float = Field(60.0, description="Maximum delay in seconds")
    backoff_factor: float = Field(2.0, description="Exponential backoff factor")
    retry_on_exceptions: list[str] = Field(
        default_factory=list, description="Exception types to retry on"
    )
