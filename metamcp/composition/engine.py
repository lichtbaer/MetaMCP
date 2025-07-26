"""
Workflow Engine

This module provides the core workflow execution engine for orchestrating
complex tool compositions and workflows.
"""

import asyncio
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from ..exceptions import WorkflowExecutionError
from ..utils.logging import get_logger
from .models import (
    ConditionOperator,
    StepStatus,
    StepType,
    WorkflowDefinition,
    WorkflowExecutionRequest,
    WorkflowExecutionResult,
    WorkflowState,
    WorkflowStatus,
    WorkflowStep,
)

logger = get_logger(__name__)


class WorkflowEngine:
    """
    Core workflow execution engine.

    This class handles the execution of workflows, including step orchestration,
    conditional logic, parallel execution, and error handling.
    """

    def __init__(self):
        """Initialize the workflow engine."""
        self.workflows: dict[str, WorkflowDefinition] = {}
        self.executions: dict[str, WorkflowState] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the workflow engine."""
        if self._initialized:
            return

        try:
            logger.info("Initializing Workflow Engine...")
            self._initialized = True
            logger.info("Workflow Engine initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Workflow Engine: {e}")
            raise WorkflowExecutionError(f"Initialization failed: {str(e)}")

    async def register_workflow(self, workflow: WorkflowDefinition) -> None:
        """
        Register a workflow definition.

        Args:
            workflow: Workflow definition to register
        """
        try:
            # Validate workflow
            self._validate_workflow(workflow)

            # Store workflow
            self.workflows[workflow.id] = workflow

            logger.info(f"Registered workflow: {workflow.id}")

        except Exception as e:
            logger.error(f"Failed to register workflow {workflow.id}: {e}")
            raise WorkflowExecutionError(f"Workflow registration failed: {str(e)}")

    async def execute_workflow(
        self, request: WorkflowExecutionRequest, tool_executor: callable
    ) -> WorkflowExecutionResult:
        """
        Execute a workflow.

        Args:
            request: Workflow execution request
            tool_executor: Function to execute tools

        Returns:
            Workflow execution result
        """
        execution_id = str(uuid.uuid4())
        start_time = time.time()

        try:
            # Get workflow definition
            workflow = self.workflows.get(request.workflow_id)
            if not workflow:
                raise WorkflowExecutionError(
                    f"Workflow not found: {request.workflow_id}"
                )

            # Initialize execution state
            state = WorkflowState(
                workflow_id=request.workflow_id,
                status=WorkflowStatus.RUNNING,
                variables=request.variables.copy(),
                started_at=datetime.now(UTC),
            )
            self.executions[execution_id] = state

            logger.info(f"Starting workflow execution: {execution_id}")

            # Execute workflow
            result = await self._execute_workflow_internal(
                workflow, state, request, tool_executor
            )

            # Calculate execution time
            execution_time = time.time() - start_time

            # Create result
            execution_result = WorkflowExecutionResult(
                execution_id=execution_id,
                workflow_id=request.workflow_id,
                status=state.status,
                result=result,
                step_results=state.step_results,
                execution_time=execution_time,
                started_at=state.started_at,
                completed_at=datetime.now(UTC),
                metadata=state.metadata,
            )

            logger.info(f"Workflow execution completed: {execution_id}")

            return execution_result

        except Exception as e:
            # Update state with error
            if execution_id in self.executions:
                state = self.executions[execution_id]
                state.status = WorkflowStatus.FAILED
                state.error = str(e)
                state.completed_at = datetime.now(UTC)

            logger.error(f"Workflow execution failed: {e}")
            raise WorkflowExecutionError(f"Workflow execution failed: {str(e)}")

    async def _execute_workflow_internal(
        self,
        workflow: WorkflowDefinition,
        state: WorkflowState,
        request: WorkflowExecutionRequest,
        tool_executor: callable,
    ) -> dict[str, Any]:
        """Internal workflow execution implementation."""
        try:
            # Initialize step statuses
            for step in workflow.steps:
                state.step_statuses[step.id] = StepStatus.PENDING

            # Execute workflow steps
            result = await self._execute_steps(workflow, state, request, tool_executor)

            # Update final status
            if state.error:
                state.status = WorkflowStatus.FAILED
            else:
                state.status = WorkflowStatus.COMPLETED

            return result

        except Exception as e:
            state.error = str(e)
            state.status = WorkflowStatus.FAILED
            raise

    async def _execute_steps(
        self,
        workflow: WorkflowDefinition,
        state: WorkflowState,
        request: WorkflowExecutionRequest,
        tool_executor: callable,
    ) -> dict[str, Any]:
        """Execute workflow steps."""
        # Create step dependency graph
        step_graph = self._build_step_graph(workflow.steps)

        # Execute steps in dependency order
        executed_steps = set()
        final_result = {}

        while len(executed_steps) < len(workflow.steps):
            # Find ready steps
            ready_steps = self._get_ready_steps(
                workflow.steps, step_graph, executed_steps, state
            )

            if not ready_steps:
                # Check for circular dependencies or deadlock
                remaining_steps = {step.id for step in workflow.steps} - executed_steps
                if remaining_steps:
                    raise WorkflowExecutionError(
                        f"Circular dependency detected: {remaining_steps}"
                    )
                break

            # Execute ready steps
            if workflow.parallel_execution:
                # Parallel execution
                tasks = []
                for step in ready_steps:
                    task = self._execute_step(step, state, request, tool_executor)
                    tasks.append(task)

                results = await asyncio.gather(*tasks, return_exceptions=True)

                for step, result in zip(ready_steps, results, strict=False):
                    if isinstance(result, Exception):
                        state.step_statuses[step.id] = StepStatus.FAILED
                        state.error = str(result)
                        raise WorkflowExecutionError(f"Step {step.id} failed: {result}")
                    else:
                        executed_steps.add(step.id)
                        state.step_results[step.id] = result
                        final_result[step.id] = result
            else:
                # Sequential execution
                for step in ready_steps:
                    try:
                        result = await self._execute_step(
                            step, state, request, tool_executor
                        )
                        executed_steps.add(step.id)
                        state.step_results[step.id] = result
                        final_result[step.id] = result
                    except Exception as e:
                        state.step_statuses[step.id] = StepStatus.FAILED
                        state.error = str(e)
                        raise WorkflowExecutionError(f"Step {step.id} failed: {e}")

        return final_result

    async def _execute_step(
        self,
        step: WorkflowStep,
        state: WorkflowState,
        request: WorkflowExecutionRequest,
        tool_executor: callable,
    ) -> Any:
        """Execute a single workflow step."""
        start_time = time.time()
        state.current_step = step.id
        state.step_statuses[step.id] = StepStatus.RUNNING

        try:
            logger.info(f"Executing step: {step.id}")

            # Check conditions
            if step.condition and not self._evaluate_condition(step.condition, state):
                state.step_statuses[step.id] = StepStatus.SKIPPED
                logger.info(f"Step {step.id} skipped due to condition")
                return None

            # Execute step based on type
            if step.step_type == StepType.TOOL_CALL:
                result = await self._execute_tool_step(step, state, tool_executor)
            elif step.step_type == StepType.CONDITION:
                result = await self._execute_condition_step(step, state)
            elif step.step_type == StepType.PARALLEL:
                result = await self._execute_parallel_step(
                    step, state, request, tool_executor
                )
            elif step.step_type == StepType.LOOP:
                result = await self._execute_loop_step(
                    step, state, request, tool_executor
                )
            elif step.step_type == StepType.DELAY:
                result = await self._execute_delay_step(step)
            elif step.step_type == StepType.HTTP_REQUEST:
                result = await self._execute_http_step(step, state)
            else:
                raise WorkflowExecutionError(f"Unsupported step type: {step.step_type}")

            # Update step status
            state.step_statuses[step.id] = StepStatus.COMPLETED

            execution_time = time.time() - start_time
            logger.info(f"Step {step.id} completed in {execution_time:.2f}s")

            return result

        except Exception as e:
            state.step_statuses[step.id] = StepStatus.FAILED
            logger.error(f"Step {step.id} failed: {e}")
            raise

    async def _execute_tool_step(
        self, step: WorkflowStep, state: WorkflowState, tool_executor: callable
    ) -> Any:
        """Execute a tool call step."""
        tool_name = step.config.get("tool_name")
        if not tool_name:
            raise WorkflowExecutionError(f"Tool name not specified for step {step.id}")

        # Prepare arguments with variable substitution
        arguments = self._substitute_variables(step.config.get("arguments", {}), state)

        # Execute tool with retry logic
        retry_config = step.retry_config or {}
        max_attempts = retry_config.get("max_attempts", 1)

        for attempt in range(max_attempts):
            try:
                result = await tool_executor(tool_name, arguments)
                return result
            except Exception:
                if attempt == max_attempts - 1:
                    raise

                # Wait before retry
                delay = retry_config.get("initial_delay", 1.0) * (2**attempt)
                await asyncio.sleep(delay)

    async def _execute_condition_step(
        self, step: WorkflowStep, state: WorkflowState
    ) -> bool:
        """Execute a condition step."""
        condition = step.config.get("condition")
        if not condition:
            raise WorkflowExecutionError(f"Condition not specified for step {step.id}")

        result = self._evaluate_condition(condition, state)
        return result

    async def _execute_parallel_step(
        self,
        step: WorkflowStep,
        state: WorkflowState,
        request: WorkflowExecutionRequest,
        tool_executor: callable,
    ) -> list[Any]:
        """Execute a parallel step."""
        sub_steps = step.config.get("steps", [])
        if not sub_steps:
            raise WorkflowExecutionError(
                f"No sub-steps specified for parallel step {step.id}"
            )

        # Create tasks for sub-steps
        tasks = []
        for sub_step_config in sub_steps:
            sub_step = WorkflowStep(
                id=f"{step.id}_sub_{len(tasks)}",
                name=sub_step_config.get("name", "sub_step"),
                step_type=StepType(sub_step_config.get("type", "tool_call")),
                config=sub_step_config.get("config", {}),
                metadata=sub_step_config.get("metadata", {}),
            )
            task = self._execute_step(sub_step, state, request, tool_executor)
            tasks.append(task)

        # Execute sub-steps in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check for errors
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                raise WorkflowExecutionError(f"Parallel sub-step {i} failed: {result}")

        return results

    async def _execute_loop_step(
        self,
        step: WorkflowStep,
        state: WorkflowState,
        request: WorkflowExecutionRequest,
        tool_executor: callable,
    ) -> list[Any]:
        """Execute a loop step."""
        loop_config = step.config.get("loop", {})
        items = loop_config.get("items", [])
        max_iterations = loop_config.get("max_iterations", 100)

        results = []
        for i, item in enumerate(items[:max_iterations]):
            # Set loop variable
            state.variables["loop_item"] = item
            state.variables["loop_index"] = i

            # Execute loop body
            body_step = WorkflowStep(
                id=f"{step.id}_body_{i}",
                name=f"Loop body {i}",
                step_type=StepType.TOOL_CALL,
                config=step.config.get("body", {}),
            )

            try:
                result = await self._execute_step(
                    body_step, state, request, tool_executor
                )
                results.append(result)
            except Exception as e:
                if loop_config.get("continue_on_error", False):
                    logger.warning(f"Loop iteration {i} failed: {e}")
                    continue
                else:
                    raise

        return results

    async def _execute_delay_step(self, step: WorkflowStep) -> None:
        """Execute a delay step."""
        delay_seconds = step.config.get("delay_seconds", 1.0)
        await asyncio.sleep(delay_seconds)

    async def _execute_http_step(self, step: WorkflowStep, state: WorkflowState) -> Any:
        """Execute an HTTP request step."""
        import httpx

        url = step.config.get("url")
        method = step.config.get("method", "GET")
        headers = step.config.get("headers", {})
        data = self._substitute_variables(step.config.get("data", {}), state)

        async with httpx.AsyncClient() as client:
            response = await client.request(method, url, headers=headers, json=data)
            response.raise_for_status()
            return response.json()

    def _evaluate_condition(
        self, condition: dict[str, Any], state: WorkflowState
    ) -> bool:
        """Evaluate a condition."""
        operator = condition.get("operator")
        left_operand = condition.get("left_operand")
        right_operand = condition.get("right_operand")

        # Get actual values
        left_value = self._get_variable_value(left_operand, state)
        right_value = (
            self._get_variable_value(right_operand, state) if right_operand else None
        )

        # Evaluate condition
        if operator == ConditionOperator.EQUALS:
            return left_value == right_value
        elif operator == ConditionOperator.NOT_EQUALS:
            return left_value != right_value
        elif operator == ConditionOperator.GREATER_THAN:
            return left_value > right_value
        elif operator == ConditionOperator.LESS_THAN:
            return left_value < right_value
        elif operator == ConditionOperator.CONTAINS:
            return right_value in left_value
        elif operator == ConditionOperator.NOT_CONTAINS:
            return right_value not in left_value
        elif operator == ConditionOperator.EXISTS:
            return left_value is not None
        elif operator == ConditionOperator.NOT_EXISTS:
            return left_value is None
        else:
            raise WorkflowExecutionError(f"Unsupported condition operator: {operator}")

    def _get_variable_value(self, variable_path: str, state: WorkflowState) -> Any:
        """Get variable value from workflow state."""
        if not variable_path.startswith("$"):
            return variable_path

        # Remove $ prefix
        path = variable_path[1:]

        # Navigate through variables
        value = state.variables
        for part in path.split("."):
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None

        return value

    def _substitute_variables(self, data: Any, state: WorkflowState) -> Any:
        """Substitute variables in data structure."""
        if isinstance(data, str):
            if data.startswith("$"):
                return self._get_variable_value(data, state)
            return data
        elif isinstance(data, dict):
            return {k: self._substitute_variables(v, state) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._substitute_variables(item, state) for item in data]
        else:
            return data

    def _build_step_graph(self, steps: list[WorkflowStep]) -> dict[str, list[str]]:
        """Build dependency graph for steps."""
        graph = {}
        for step in steps:
            graph[step.id] = step.depends_on
        return graph

    def _get_ready_steps(
        self,
        steps: list[WorkflowStep],
        graph: dict[str, list[str]],
        executed_steps: set,
        state: WorkflowState,
    ) -> list[WorkflowStep]:
        """Get steps that are ready to execute."""
        ready_steps = []

        for step in steps:
            if step.id in executed_steps:
                continue

            # Check dependencies
            dependencies = graph.get(step.id, [])
            if all(dep in executed_steps for dep in dependencies):
                ready_steps.append(step)

        return ready_steps

    def _validate_workflow(self, workflow: WorkflowDefinition) -> None:
        """Validate workflow definition."""
        # Check for duplicate step IDs
        step_ids = [step.id for step in workflow.steps]
        if len(step_ids) != len(set(step_ids)):
            raise WorkflowExecutionError("Duplicate step IDs found")

        # Check entry point exists
        if workflow.entry_point not in step_ids:
            raise WorkflowExecutionError(
                f"Entry point {workflow.entry_point} not found"
            )

        # Check for circular dependencies
        graph = self._build_step_graph(workflow.steps)
        if self._has_circular_dependencies(graph):
            raise WorkflowExecutionError("Circular dependencies detected")

    def _has_circular_dependencies(self, graph: dict[str, list[str]]) -> bool:
        """Check for circular dependencies using DFS."""
        visited = set()
        rec_stack = set()

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for node in graph:
            if node not in visited:
                if dfs(node):
                    return True

        return False
