"""
Planning and Tool Use System - Phase 2

Implements:
- Task decomposition into actionable steps
- Tool registry and adapters
- Plan execution with error recovery
- Progress tracking and replanning
"""

from typing import (
    List, Dict, Any, Optional, Callable, TypeVar
)
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
import asyncio


T = TypeVar('T')


class PlanStatus(Enum):
    """Status of a plan or step."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class StepType(Enum):
    """Types of plan steps."""
    TOOL = "tool"  # Execute a tool
    REASONING = "reasoning"  # Perform reasoning
    DECISION = "decision"  # Make a decision
    PARALLEL = "parallel"  # Execute multiple steps in parallel
    SEQUENTIAL = "sequential"  # Execute steps in sequence
    CONDITIONAL = "conditional"  # Conditional execution
    LOOP = "loop"  # Repeated execution


@dataclass
class ToolResult:
    """Result from a tool execution."""
    success: bool
    data: Any
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanStep:
    """A single step in a plan."""
    id: str
    name: str
    description: str
    step_type: StepType
    tool_name: Optional[str] = None
    tool_args: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)  # Step IDs
    preconditions: List[str] = field(default_factory=list)  # State items required
    effects: List[str] = field(default_factory=list)  # State items produced
    status: PlanStatus = PlanStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: float = 30.0
    priority: float = 0.5
    
    def is_ready(self, completed_steps: set) -> bool:
        """Check if all dependencies are satisfied."""
        return all(dep in completed_steps for dep in self.dependencies)


@dataclass
class Plan:
    """A complete execution plan."""
    id: str
    goal: str
    steps: List[PlanStep]
    status: PlanStatus = PlanStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def progress(self) -> float:
        """Calculate plan completion progress."""
        if not self.steps:
            return 0.0
        completed = sum(1 for s in self.steps if s.status == PlanStatus.COMPLETED)
        return completed / len(self.steps)
    
    @property
    def is_complete(self) -> bool:
        """Check if plan is complete."""
        return all(
            s.status in (PlanStatus.COMPLETED, PlanStatus.SKIPPED)
            for s in self.steps
        )
    
    def get_next_steps(self) -> List[PlanStep]:
        """Get steps that are ready to execute."""
        completed = {s.id for s in self.steps if s.status == PlanStatus.COMPLETED}
        ready = [
            s for s in self.steps
            if s.status == PlanStatus.PENDING and s.is_ready(completed)
        ]
        return sorted(ready, key=lambda s: s.priority, reverse=True)


class Tool(ABC):
    """Abstract base class for tools."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name for identification."""
        ...
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description."""
        ...
    
    @property
    def parameters(self) -> Dict[str, Any]:
        """JSON schema for parameters."""
        return {}
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given arguments."""
        ...
    
    def validate_args(self, args: Dict[str, Any]) -> Optional[str]:
        """Validate arguments. Returns error message if invalid."""
        # Basic validation - override for specific tools
        return None


class ToolRegistry:
    """Registry for available tools."""
    
    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        self.aliases: Dict[str, str] = {}  # alias -> tool name
        self.usage_stats: Dict[str, Dict[str, Any]] = {}
    
    def register(self, tool: Tool, aliases: Optional[List[str]] = None) -> None:
        """Register a tool."""
        self.tools[tool.name] = tool
        self.usage_stats[tool.name] = {
            "calls": 0,
            "successes": 0,
            "failures": 0,
            "total_time_ms": 0.0
        }
        
        if aliases:
            for alias in aliases:
                self.aliases[alias] = tool.name
    
    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name or alias."""
        if name in self.tools:
            return self.tools[name]
        if name in self.aliases:
            return self.tools[self.aliases[name]]
        return None
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """List all available tools."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters
            }
            for tool in self.tools.values()
        ]
    
    def record_usage(
        self, 
        tool_name: str, 
        success: bool, 
        execution_time_ms: float
    ) -> None:
        """Record tool usage for statistics."""
        if tool_name in self.usage_stats:
            stats = self.usage_stats[tool_name]
            stats["calls"] += 1
            stats["total_time_ms"] += execution_time_ms
            if success:
                stats["successes"] += 1
            else:
                stats["failures"] += 1


# Built-in Tools

class LogicValidationTool(Tool):
    """Tool for validating logical arguments."""
    
    @property
    def name(self) -> str:
        return "validate_logic"
    
    @property
    def description(self) -> str:
        return "Validate the logical structure of an argument"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "premises": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of premise statements"
                },
                "conclusion": {
                    "type": "string",
                    "description": "The conclusion to validate"
                }
            },
            "required": ["premises", "conclusion"]
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        premises = kwargs.get("premises", [])
        conclusion = kwargs.get("conclusion", "")
        
        # Simple validation logic
        is_valid = len(premises) >= 1 and len(conclusion) > 0
        
        return ToolResult(
            success=True,
            data={
                "valid": is_valid,
                "premise_count": len(premises),
                "analysis": "Basic structural validation complete"
            }
        )


class FactCheckTool(Tool):
    """Tool for checking facts against knowledge base."""
    
    def __init__(self, knowledge_base: Optional[Dict[str, Any]] = None):
        self.kb = knowledge_base or {}
    
    @property
    def name(self) -> str:
        return "check_fact"
    
    @property
    def description(self) -> str:
        return "Check a factual claim against the knowledge base"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "claim": {
                    "type": "string",
                    "description": "The claim to verify"
                },
                "domain": {
                    "type": "string",
                    "description": "Optional domain to search within"
                }
            },
            "required": ["claim"]
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        claim = kwargs.get("claim", "")
        domain = kwargs.get("domain")
        
        # Placeholder - would search actual KB
        return ToolResult(
            success=True,
            data={
                "found": False,
                "confidence": 0.0,
                "sources": [],
                "claim_searched": claim,
                "domain": domain,
                "note": "Knowledge base search placeholder"
            }
        )


class CalculationTool(Tool):
    """Tool for safe mathematical calculations."""
    
    @property
    def name(self) -> str:
        return "calculate"
    
    @property
    def description(self) -> str:
        return "Perform safe mathematical calculations"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression to evaluate"
                }
            },
            "required": ["expression"]
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        expression = kwargs.get("expression", "")
        
        # Safe evaluation with limited operations
        allowed_chars = set("0123456789+-*/.() ")
        if not all(c in allowed_chars for c in expression):
            return ToolResult(
                success=False,
                data=None,
                error="Expression contains disallowed characters"
            )
        
        try:
            result = eval(expression, {"__builtins__": {}}, {})
            return ToolResult(
                success=True,
                data={"result": result, "expression": expression}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"Calculation error: {str(e)}"
            )


class Planner:
    """
    Task decomposition and planning system.
    """
    
    def __init__(self):
        self.plans: Dict[str, Plan] = {}
        self.decomposition_strategies: Dict[str, Callable] = {}
        
        # Register default strategies
        self._register_default_strategies()
    
    def _register_default_strategies(self):
        """Register default decomposition strategies."""
        self.decomposition_strategies["linear"] = self._linear_decomposition
        self.decomposition_strategies["hierarchical"] = self._hierarchical_decomposition
        self.decomposition_strategies["parallel"] = self._parallel_decomposition

    def _score_step(self, step: PlanStep, context: Dict[str, Any]) -> float:
        """
        Score a step for prioritization.

        Heuristic: earlier dependencies score higher; reasoning before tools;
        honor any provided context priorities.
        """
        base = 0.5
        if step.step_type == StepType.REASONING:
            base += 0.1
        if step.step_type == StepType.TOOL:
            base += 0.05
        if step.preconditions:
            base -= 0.05  # gated

        # Custom priority hints from context
        hint = context.get("priorities", {}).get(step.name)
        if hint is not None:
            base = float(hint)

        return max(0.0, min(1.0, base))
    
    def create_plan(
        self,
        goal: str,
        strategy: str = "linear",
        context: Optional[Dict[str, Any]] = None
    ) -> Plan:
        """Create a plan for achieving a goal."""
        import hashlib
        plan_id = hashlib.sha256(
            f"{goal}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]
        
        # Use decomposition strategy
        decomposer = self.decomposition_strategies.get(strategy, self._linear_decomposition)
        steps = decomposer(goal, context or {})

        # Score steps (higher priority first)
        for step in steps:
            step.priority = self._score_step(step, context or {})

        plan = Plan(
            id=plan_id,
            goal=goal,
            steps=steps,
            context=context or {}
        )
        
        self.plans[plan_id] = plan
        return plan
    
    def _linear_decomposition(
        self, 
        goal: str, 
        context: Dict[str, Any]
    ) -> List[PlanStep]:
        """Decompose goal into linear sequence of steps."""
        # This is a template - would be enhanced with LLM
        return [
            PlanStep(
                id="step_1",
                name="Understand",
                description=f"Understand the goal: {goal}",
                step_type=StepType.REASONING,
                effects=["goal_understood"]
            ),
            PlanStep(
                id="step_2",
                name="Analyze",
                description="Analyze requirements and constraints",
                step_type=StepType.REASONING,
                dependencies=["step_1"],
                preconditions=["goal_understood"],
                effects=["requirements_analyzed"]
            ),
            PlanStep(
                id="step_3",
                name="Execute",
                description="Execute the main task",
                step_type=StepType.TOOL,
                dependencies=["step_2"],
                preconditions=["requirements_analyzed"],
                effects=["task_executed"]
            ),
            PlanStep(
                id="step_4",
                name="Verify",
                description="Verify the result",
                step_type=StepType.REASONING,
                dependencies=["step_3"],
                preconditions=["task_executed"]
            )
        ]
    
    def _hierarchical_decomposition(
        self, 
        goal: str, 
        context: Dict[str, Any]
    ) -> List[PlanStep]:
        """Decompose goal into hierarchical subtasks."""
        # Placeholder for more complex decomposition
        return self._linear_decomposition(goal, context)
    
    def _parallel_decomposition(
        self, 
        goal: str, 
        context: Dict[str, Any]
    ) -> List[PlanStep]:
        """Decompose goal into parallelizable steps."""
        return [
            PlanStep(
                id="step_1",
                name="Setup",
                description="Initialize parallel execution",
                step_type=StepType.REASONING,
                effects=["parallel_ready"]
            ),
            PlanStep(
                id="step_2a",
                name="Branch A",
                description="Execute branch A",
                step_type=StepType.TOOL,
                dependencies=["step_1"],
                preconditions=["parallel_ready"],
                effects=["branch_a_done"]
            ),
            PlanStep(
                id="step_2b",
                name="Branch B",
                description="Execute branch B",
                step_type=StepType.TOOL,
                dependencies=["step_1"],
                preconditions=["parallel_ready"],
                effects=["branch_b_done"]
            ),
            PlanStep(
                id="step_3",
                name="Merge",
                description="Merge parallel results",
                step_type=StepType.REASONING,
                dependencies=["step_2a", "step_2b"],
                preconditions=["branch_a_done", "branch_b_done"]
            )
        ]
    
    def replan(
        self,
        plan: Plan,
        failed_step: PlanStep,
        error: str
    ) -> Plan:
        """Create a new plan after a failure."""
        # Mark failed step
        failed_step.status = PlanStatus.FAILED
        failed_step.error = error
        
        # Create recovery steps
        recovery_step = PlanStep(
            id=f"recovery_{failed_step.id}",
            name=f"Recover from {failed_step.name}",
            description=f"Alternative approach after failure: {error}",
            step_type=StepType.REASONING,
            dependencies=[s.id for s in plan.steps if s.status == PlanStatus.COMPLETED]
        )
        
        # Create new plan with recovery
        new_steps = [
            s for s in plan.steps 
            if s.status == PlanStatus.COMPLETED
        ]
        new_steps.append(recovery_step)
        
        # Add remaining steps with updated dependencies
        for step in plan.steps:
            if step.status == PlanStatus.PENDING and step.id != failed_step.id:
                step.dependencies = [
                    d if d != failed_step.id else recovery_step.id
                    for d in step.dependencies
                ]
                new_steps.append(step)
        
        return Plan(
            id=f"{plan.id}_recovery",
            goal=plan.goal,
            steps=new_steps,
            context={**plan.context, "recovery_from": plan.id}
        )


class PlanExecutor:
    """
    Executes plans using registered tools.
    """
    
    def __init__(
        self,
        tool_registry: ToolRegistry,
        planner: Planner,
        max_concurrent: int = 3
    ):
        self.tools = tool_registry
        self.planner = planner
        self.max_concurrent = max_concurrent
        self.execution_history: List[Dict[str, Any]] = []
        self.warnings: List[str] = []
        self.state: set[str] = set()
    
    async def execute_plan(
        self,
        plan: Plan,
        on_step_complete: Optional[Callable[[PlanStep], None]] = None
    ) -> Dict[str, Any]:
        """Execute a plan to completion."""
        plan.status = PlanStatus.IN_PROGRESS
        start_time = datetime.now()
        self.warnings = []
        # initialize state from plan context if provided
        self.state = set(plan.context.get("state", set()))

        # Evidence gate: if plan requires verification and context is unverified, block
        if plan.context.get("require_verified") and not plan.context.get("verified", True):
            plan.status = PlanStatus.BLOCKED
            msg = "Plan blocked: upstream reasoning unverified."
            self.warnings.append(msg)
            return {
                "success": False,
                "error": msg,
                "completed": 0.0,
                "warnings": self.warnings
            }
        
        while not plan.is_complete:
            ready_steps = plan.get_next_steps()
            
            if not ready_steps:
                # Check for blocked plan
                pending = [s for s in plan.steps if s.status == PlanStatus.PENDING]
                if pending:
                    plan.status = PlanStatus.BLOCKED
                    return {
                        "success": False,
                        "error": "Plan blocked - no steps can execute",
                        "completed": plan.progress
                    }
                break

            # filter by preconditions
            runnable = [s for s in ready_steps if self._preconditions_met(s)]
            if not runnable:
                plan.status = PlanStatus.BLOCKED
                self.warnings.append("No steps runnable; preconditions unmet.")
                return {
                    "success": False,
                    "error": "Plan blocked - preconditions unmet",
                    "completed": plan.progress,
                    "warnings": self.warnings
                }
            
            # Execute ready steps (up to max_concurrent)
            batch = runnable[:self.max_concurrent]
            results = await asyncio.gather(*[
                self._execute_step(step) for step in batch
            ], return_exceptions=True)
            
            # Process results
            for step, result in zip(batch, results):
                if isinstance(result, Exception):
                    step.status = PlanStatus.FAILED
                    step.error = str(result)
                    self.warnings.append(f"{step.name} failed: {step.error}")
                    
                    # Attempt recovery
                    if step.retry_count < step.max_retries:
                        step.retry_count += 1
                        step.status = PlanStatus.PENDING
                    else:
                        # Replan
                        plan = self.planner.replan(plan, step, str(result))
                else:
                    step.status = PlanStatus.COMPLETED
                    step.result = result
                    # update state with effects
                    for effect in step.effects:
                        self.state.add(effect)
                    
                    if on_step_complete:
                        on_step_complete(step)
        
        plan.status = PlanStatus.COMPLETED
        plan.completed_at = datetime.now().isoformat()
        
        elapsed = (datetime.now() - start_time).total_seconds() * 1000
        
        execution_record = {
            "plan_id": plan.id,
            "goal": plan.goal,
            "success": plan.status == PlanStatus.COMPLETED,
            "duration_ms": elapsed,
            "steps_completed": sum(1 for s in plan.steps if s.status == PlanStatus.COMPLETED),
            "total_steps": len(plan.steps),
            "warnings": self.warnings,
            "state": list(self.state)
        }
        self.execution_history.append(execution_record)
        
        return execution_record
    
    async def _execute_step(self, step: PlanStep) -> Any:
        """Execute a single plan step."""
        step.status = PlanStatus.IN_PROGRESS
        start_time = datetime.now()
        
        try:
            if step.step_type == StepType.TOOL:
                # Execute tool
                tool = self.tools.get(step.tool_name or "")
                if not tool:
                    raise ValueError(f"Tool not found: {step.tool_name}")
                
                validation_error = tool.validate_args(step.tool_args)
                if validation_error:
                    raise ValueError(f"Invalid arguments for {tool.name}: {validation_error}")
                
                result = await asyncio.wait_for(
                    tool.execute(**step.tool_args),
                    timeout=step.timeout_seconds
                )
                
                elapsed = (datetime.now() - start_time).total_seconds() * 1000
                self.tools.record_usage(tool.name, result.success, elapsed)
                
                if not result.success:
                    raise RuntimeError(result.error or "Tool execution failed")
                
                return result.data
            
            elif step.step_type == StepType.REASONING:
                # Placeholder for reasoning step
                return {"reasoning": step.description, "status": "complete"}
            
            elif step.step_type == StepType.DECISION:
                # Placeholder for decision step
                return {"decision": "proceed", "confidence": 0.8}
            
            else:
                return {"step_type": step.step_type.value, "status": "complete"}
                
        except asyncio.TimeoutError:
            raise RuntimeError(f"Step timed out after {step.timeout_seconds}s")
        except Exception as e:
            raise RuntimeError(f"Step failed: {str(e)}")

    def _preconditions_met(self, step: PlanStep) -> bool:
        """Check whether plan state satisfies the step's preconditions."""
        if not step.preconditions:
            return True
        return all(p in self.state for p in step.preconditions)


class PlanningSystem:
    """
    Complete planning and tool use system.
    """
    
    def __init__(self):
        self.tool_registry = ToolRegistry()
        self.planner = Planner()
        self.executor = PlanExecutor(self.tool_registry, self.planner)
        
        # Register built-in tools
        self._register_built_in_tools()
    
    def _register_built_in_tools(self):
        """Register built-in tools."""
        self.tool_registry.register(LogicValidationTool(), ["validate", "check_logic"])
        self.tool_registry.register(FactCheckTool(), ["fact_check", "verify"])
        self.tool_registry.register(CalculationTool(), ["calc", "math"])
    
    def register_tool(
        self, 
        tool: Tool, 
        aliases: Optional[List[str]] = None
    ) -> None:
        """Register a custom tool."""
        self.tool_registry.register(tool, aliases)
    
    async def execute_goal(
        self,
        goal: str,
        strategy: str = "linear",
        context: Optional[Dict[str, Any]] = None,
        on_progress: Optional[Callable[[float], None]] = None
    ) -> Dict[str, Any]:
        """Plan and execute a goal."""
        # Create plan
        plan = self.planner.create_plan(goal, strategy, context)
        
        # Execute with progress tracking
        def on_step(step: PlanStep):
            if on_progress:
                on_progress(plan.progress)
        
        result = await self.executor.execute_plan(plan, on_step)
        
        return {
            "plan": {
                "id": plan.id,
                "goal": plan.goal,
                "steps": [
                    {
                        "name": s.name,
                        "status": s.status.value,
                        "result": s.result
                    }
                    for s in plan.steps
                ]
            },
            "execution": result
        }
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools."""
        return self.tool_registry.list_tools()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get system statistics."""
        return {
            "tool_usage": self.tool_registry.usage_stats,
            "plans_executed": len(self.executor.execution_history),
            "execution_history": self.executor.execution_history[-10:]  # Last 10
        }
