"""The workflow engine (AGENT_ORGANIZATION.md §4).

Task -> delegation -> execution -> review -> (revision -> review)* -> approval -> completion.

Bounded everywhere: per-agent iteration limits, a per-task execution budget, a cap on human
revision requests and on retries after escalation. Agents never call each other: the engine
walks the fixed workflow template and wires inputs from upstream outputs. Every action is an
org_executions row and an audit event.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import AuditService
from app.domain.enums import (
    ActorType,
    ApprovalDecision,
    ApprovalLevel,
    ApproverType,
    ExecutionKind,
    ExecutionStatus,
    OrgTaskStatus,
    ReviewerType,
    StepStatus,
    UserRole,
    WorkflowType,
)
from app.models import OrgApproval, OrgExecution, OrgTask, OrgTaskStep, User
from app.org import reviews
from app.org.agents import AGENTS, CHIEF, AgentDefinition
from app.org.handlers import HANDLERS, HandlerResult
from app.org.policy import (
    MAX_EXECUTIONS_PER_TASK,
    MAX_HUMAN_REVISIONS,
    MAX_STEP_RETRIES,
    SUPPORTED_LANGUAGES,
    EscalationCondition,
    OrgError,
)
from app.org.schemas import ChiefInput
from app.org.tools import ToolContext
from app.org.workflows import WORKFLOWS, StepSpec, Workflow
from app.pipeline.context import PipelineContext
from app.services.errors import Conflict, Forbidden, NotFound, Unprocessable

# Execution-log identity for human decisions (they are not agents).
HUMAN_ACTOR = "human_reviewer"

TERMINAL = {
    OrgTaskStatus.COMPLETED,
    OrgTaskStatus.REJECTED,
    OrgTaskStatus.CANCELLED,
    OrgTaskStatus.FAILED,
}
FINISHED_STEPS = {StepStatus.DONE, StepStatus.SKIPPED}


class SelfReviewError(Exception):
    pass


class _Escalate(Exception):
    def __init__(self, condition: EscalationCondition, detail: str) -> None:
        super().__init__(detail)
        self.condition = condition
        self.detail = detail


# --- logging -----------------------------------------------------------------------------


def _log(
    session: Session,
    task: OrgTask,
    *,
    kind: ExecutionKind,
    status: ExecutionStatus,
    agent_key: str,
    step: OrgTaskStep | None = None,
    iteration: int = 0,
    input: dict[str, Any] | None = None,
    output: dict[str, Any] | None = None,
    tool_calls: list[dict] | None = None,
    result: HandlerResult | None = None,
    error: str | None = None,
    started: float | None = None,
    actor: tuple[ActorType, str] | None = None,
) -> OrgExecution:
    now = datetime.now(UTC)
    latency = int((time.monotonic() - started) * 1000) if started else 0
    row = OrgExecution(
        task_id=task.id,
        step_id=step.id if step else None,
        agent_key=agent_key,
        kind=kind,
        status=status,
        iteration=iteration,
        input=input or {},
        output=output,
        tool_calls=tool_calls or [],
        ai_run_id=result.ai_run_ids[-1] if result and result.ai_run_ids else None,
        model=result.model if result else None,
        prompt_tokens=result.prompt_tokens if result else None,
        completion_tokens=result.completion_tokens if result else None,
        latency_ms=latency,
        error=error,
        started_at=now,
        finished_at=now,
    )
    session.add(row)
    if kind in (ExecutionKind.EXECUTION, ExecutionKind.REVISION, ExecutionKind.REVIEW):
        task.executions_used += 1
    session.flush()
    actor_type, actor_id = actor or (ActorType.AGENT, agent_key)
    AuditService(session).record(
        actor_type=actor_type,
        actor_id=actor_id,
        action=f"org.{kind.value.lower()}",
        entity_type="org_task",
        entity_id=task.id,
        payload={
            "execution_id": str(row.id),
            "agent": agent_key,
            "step": step.step_key if step else None,
            "status": status.value,
            "iteration": iteration,
            "ai_run_ids": [str(i) for i in result.ai_run_ids] if result else [],
            "tool_calls": [c["tool"] for c in tool_calls or []],
            "error": error,
        },
    )
    return row


# --- task creation and delegation --------------------------------------------------------


def create_task(
    session: Session, user: User, workflow: WorkflowType, data: dict[str, Any]
) -> OrgTask:
    wf = WORKFLOWS[workflow]
    try:
        parsed = wf.input_schema.model_validate(data)
    except ValidationError as exc:
        raise Unprocessable(f"Invalid input for {workflow.value}: {exc}") from exc
    payload = parsed.model_dump(mode="json")
    if workflow == WorkflowType.NARRATIVE_RESPONSE:
        bad = [lang for lang in payload["languages"] if lang not in SUPPORTED_LANGUAGES]
        if bad:
            raise Unprocessable(
                f"Unsupported languages {bad}; supported: {sorted(SUPPORTED_LANGUAGES)}"
            )
    task = OrgTask(
        workflow=workflow,
        title=wf.title(payload),
        input=payload,
        status=OrgTaskStatus.PENDING,
        approval_level=wf.approval,
        created_by_id=user.id,
    )
    session.add(task)
    session.flush()
    AuditService(session).record(
        actor_type=ActorType.USER,
        actor_id=str(user.id),
        action="org.task_created",
        entity_type="org_task",
        entity_id=task.id,
        payload={"workflow": workflow.value, "input": payload},
    )
    _delegate(session, task, wf)
    return task


def _delegate(session: Session, task: OrgTask, wf: Workflow) -> None:
    """The Chief instantiates the fixed template. No agent can add or reorder steps."""
    plan = []
    for seq, spec in enumerate(wf.steps):
        agent = AGENTS[spec.agent]
        delegated_by = agent.manager or CHIEF
        step = OrgTaskStep(
            task_id=task.id,
            seq=seq,
            step_key=spec.key,
            agent_key=spec.agent,
            delegated_by=delegated_by,
            depends_on=list(spec.depends_on),
            reviewer=spec.reviewer,
            status=StepStatus.PENDING,
        )
        session.add(step)
        session.flush()
        plan.append(
            {
                "step": spec.key,
                "agent": spec.agent,
                "reviewer": spec.reviewer.value,
                "chain": [CHIEF, delegated_by, spec.agent],
            }
        )
        _log(
            session,
            task,
            kind=ExecutionKind.DELEGATION,
            status=ExecutionStatus.SUCCEEDED,
            agent_key=CHIEF,
            step=step,
            input=ChiefInput(
                workflow=wf.type.value, title=task.title, input=task.input
            ).model_dump(),
            output={
                "assigned_to": spec.agent,
                "via_manager": delegated_by,
                "reviewer": spec.reviewer.value,
            },
        )
    task.output = {"delegation_plan": plan}
    session.flush()


# --- running -----------------------------------------------------------------------------


def _steps(session: Session, task: OrgTask) -> list[OrgTaskStep]:
    return list(
        session.scalars(
            select(OrgTaskStep).where(OrgTaskStep.task_id == task.id).order_by(OrgTaskStep.seq)
        )
    )


def _outputs(task: OrgTask, steps: list[OrgTaskStep]) -> dict[str, Any]:
    out: dict[str, Any] = {"_task": task.input}
    for s in steps:
        out[s.step_key] = s.output if s.status == StepStatus.DONE else None
    return out


def run_task(ctx: PipelineContext, task_id: uuid.UUID) -> OrgTask:
    session = ctx.session
    task = session.get(OrgTask, task_id, with_for_update=True)
    if task is None:
        raise NotFound("Task not found.")
    if task.status in TERMINAL or task.status == OrgTaskStatus.AWAITING_APPROVAL:
        return task
    wf = WORKFLOWS[task.workflow]
    task.status = OrgTaskStatus.IN_PROGRESS
    task.escalation_reason = None
    steps = _steps(session, task)
    specs = {s.key: s for s in wf.steps}
    try:
        for step in steps:
            if step.status in FINISHED_STEPS:
                continue
            spec = specs[step.step_key]
            outputs = _outputs(task, steps)
            reason = spec.skip_if(outputs)
            if reason:
                step.status = StepStatus.SKIPPED
                step.output = None
                _log(
                    session,
                    task,
                    kind=ExecutionKind.EXECUTION,
                    status=ExecutionStatus.SKIPPED,
                    agent_key=step.agent_key,
                    step=step,
                    output={"skipped": reason},
                )
                continue
            _run_step(ctx, task, step, spec, outputs)
    except _Escalate as esc:
        _escalate(session, task, step, esc)
        session.commit()
        return task
    _finish(session, task, wf, steps)
    session.commit()
    return task


def _check_budget(task: OrgTask) -> None:
    if task.executions_used >= MAX_EXECUTIONS_PER_TASK:
        raise _Escalate(
            EscalationCondition.TASK_BUDGET,
            f"Task used its {MAX_EXECUTIONS_PER_TASK}-execution budget.",
        )


def _run_step(
    ctx: PipelineContext, task: OrgTask, step: OrgTaskStep, spec: StepSpec, outputs: dict[str, Any]
) -> None:
    session = ctx.session
    agent = AGENTS[step.agent_key]
    while True:
        _check_budget(task)
        if step.iterations >= agent.max_iterations:
            raise _Escalate(
                EscalationCondition.ITERATION_LIMIT,
                f"{agent.name} reached its limit of {agent.max_iterations} "
                "iteration(s) without passing review.",
            )
        step.iterations += 1
        step.status = StepStatus.RUNNING
        session.flush()
        kind = ExecutionKind.EXECUTION if step.iterations == 1 else ExecutionKind.REVISION
        step_input = spec.build_input(outputs)
        tc = ToolContext(session=session, pipeline=ctx, agent=agent)
        started = time.monotonic()
        try:
            inp = agent.input_schema.model_validate(step_input)
            result = HANDLERS[agent.key](tc, inp, outputs, step.feedback)
        except OrgError as exc:
            _log(
                session,
                task,
                kind=kind,
                status=ExecutionStatus.FAILED,
                agent_key=agent.key,
                step=step,
                iteration=step.iterations,
                input=step_input,
                tool_calls=tc.calls,
                error=exc.detail,
                started=started,
            )
            raise _Escalate(exc.condition, exc.detail) from exc
        except ValidationError as exc:
            _log(
                session,
                task,
                kind=kind,
                status=ExecutionStatus.FAILED,
                agent_key=agent.key,
                step=step,
                iteration=step.iterations,
                input=step_input,
                tool_calls=tc.calls,
                error=str(exc)[:2000],
                started=started,
            )
            raise _Escalate(EscalationCondition.INVALID_OUTPUT, str(exc)[:2000]) from exc
        output = result.output.model_dump(mode="json")
        _log(
            session,
            task,
            kind=kind,
            status=ExecutionStatus.SUCCEEDED,
            agent_key=agent.key,
            step=step,
            iteration=step.iterations,
            input=step_input,
            output=output,
            tool_calls=tc.calls,
            result=result,
            started=started,
        )
        step.output = output
        step.status = StepStatus.IN_REVIEW
        session.flush()

        if spec.reviewer != ReviewerType.NONE:
            _check_budget(task)
        verdict, issues, summary = _review(ctx, task, step, spec, agent, step_input, output)
        if verdict == "PASS":
            step.status = StepStatus.DONE
            outputs[step.step_key] = output
            session.flush()
            return
        if verdict == "ESCALATE":
            cond = (
                EscalationCondition.COMPLIANCE_VIOLATION
                if agent.key == "compliance_agent"
                else EscalationCondition.REVIEW_ESCALATED
            )
            raise _Escalate(cond, summary)
        step.feedback = [*step.feedback, {"from": "review", "summary": summary, "issues": issues}]
        session.flush()


def _review(ctx, task, step, spec, agent: AgentDefinition, step_input, output):
    session = ctx.session
    if spec.reviewer == ReviewerType.NONE:
        # The compliance gate reviews itself only in the sense that its result is binding:
        # a failure blocks approval and goes to a human.
        if agent.key == "compliance_agent" and not output["passed"]:
            return (
                "ESCALATE",
                output["violations"],
                f"{len(output['violations'])} compliance violation(s).",
            )
        return ("PASS", [], "Gate passed.")
    if spec.reviewer == ReviewerType.MANAGER:
        reviewer_key = agent.manager or CHIEF
        if reviewer_key == agent.key:
            raise SelfReviewError(agent.key)
        verdict, issues, summary = reviews.review(agent.key, output)
        _log(
            session,
            task,
            kind=ExecutionKind.REVIEW,
            status=ExecutionStatus(verdict),
            agent_key=reviewer_key,
            step=step,
            iteration=step.iterations,
            input={"reviewing": agent.key},
            output={"issues": issues, "summary": summary},
        )
        return verdict, issues, summary
    # CRITIC review (LLM), independent of the executor.
    critic = AGENTS["critic_agent"]
    if critic.key == agent.key:
        raise SelfReviewError(agent.key)
    tc = ToolContext(session=session, pipeline=ctx, agent=critic)
    materials = {"input": step_input}
    for dep in spec.depends_on:
        materials[dep] = _outputs(task, _steps(session, task)).get(dep)
    review_in = ChiefInput(
        workflow=task.workflow.value,
        title=task.title,
        input={"agent": agent.name, "materials": materials, "output": output},
    )
    started = time.monotonic()
    try:
        result = HANDLERS[critic.key](tc, review_in, {}, [])
    except OrgError as exc:
        _log(
            session,
            task,
            kind=ExecutionKind.REVIEW,
            status=ExecutionStatus.FAILED,
            agent_key=critic.key,
            step=step,
            iteration=step.iterations,
            error=exc.detail,
            started=started,
        )
        raise _Escalate(exc.condition, f"Critic failed: {exc.detail}") from exc
    c = result.output
    _log(
        session,
        task,
        kind=ExecutionKind.REVIEW,
        status=ExecutionStatus(c.verdict),
        agent_key=critic.key,
        step=step,
        iteration=step.iterations,
        input={"reviewing": agent.key},
        output=c.model_dump(mode="json"),
        result=result,
        started=started,
    )
    return c.verdict, [i.model_dump() for i in c.issues], c.summary


def _escalate(session: Session, task: OrgTask, step: OrgTaskStep, esc: _Escalate) -> None:
    agent = AGENTS[step.agent_key]
    target = agent.escalation_target(esc.condition)
    step.status = StepStatus.ESCALATED
    step.escalation = {
        "condition": esc.condition.value,
        "target": target.value,
        "manager": agent.manager,
        "detail": esc.detail,
    }
    task.status = OrgTaskStatus.ESCALATED
    task.escalation_reason = f"{agent.name}: {esc.condition.value}: {esc.detail}"[:4000]
    _log(
        session,
        task,
        kind=ExecutionKind.ESCALATION,
        status=ExecutionStatus.ESCALATE,
        agent_key=agent.manager if target.value == "MANAGER" and agent.manager else agent.key,
        step=step,
        iteration=step.iterations,
        output=step.escalation,
    )


def _finish(session: Session, task: OrgTask, wf: Workflow, steps: list[OrgTaskStep]) -> None:
    if any(s.status not in FINISHED_STEPS for s in steps):
        task.status = OrgTaskStatus.FAILED
        task.escalation_reason = "Workflow ended with unfinished steps."
        return
    if wf.approval == ApprovalLevel.HUMAN:
        task.status = OrgTaskStatus.AWAITING_APPROVAL
        _log(
            session,
            task,
            kind=ExecutionKind.APPROVAL,
            status=ExecutionStatus.SUCCEEDED,
            agent_key=CHIEF,
            output={"awaiting": "human approval (REVIEWER+, not the creator)"},
        )
        return
    # Internal work: the Chief approves. It never executed a step of this task.
    executors = {s.agent_key for s in steps if s.status == StepStatus.DONE}
    if CHIEF in executors:
        raise SelfReviewError(CHIEF)
    session.add(
        OrgApproval(
            task_id=task.id,
            approver_type=ApproverType.AGENT,
            approver_agent=CHIEF,
            decision=ApprovalDecision.APPROVED,
            notes="All steps passed review.",
        )
    )
    _log(
        session,
        task,
        kind=ExecutionKind.APPROVAL,
        status=ExecutionStatus.SUCCEEDED,
        agent_key=CHIEF,
        output={"decision": "APPROVED", "level": "MANAGER"},
    )
    _complete(session, task, steps)


def _complete(
    session: Session,
    task: OrgTask,
    steps: list[OrgTaskStep],
    actor: tuple[ActorType, str] | None = None,
) -> None:
    result = {s.step_key: s.output for s in steps if s.status == StepStatus.DONE}
    skipped = {s.step_key: "skipped" for s in steps if s.status == StepStatus.SKIPPED}
    task.output = {**(task.output or {}), "result": result, "skipped": skipped}
    task.status = OrgTaskStatus.COMPLETED
    task.completed_at = datetime.now(UTC)
    _log(
        session,
        task,
        kind=ExecutionKind.COMPLETION,
        status=ExecutionStatus.SUCCEEDED,
        agent_key=CHIEF,
        output={"steps_done": sorted(result), "skipped": sorted(skipped)},
        actor=actor,
    )


# --- human actions -----------------------------------------------------------------------


def _require_reviewer(user: User, task: OrgTask) -> None:
    if user.role not in (UserRole.REVIEWER, UserRole.ADMIN):
        raise Forbidden("Only reviewers can approve or reject agent work.")
    if user.id == task.created_by_id:
        raise Forbidden("You cannot approve or reject a task you created (four-eyes rule).")


def _human_approval(session, task, user, decision, notes, target_step=None):
    session.add(
        OrgApproval(
            task_id=task.id,
            approver_type=ApproverType.HUMAN,
            approver_user_id=user.id,
            decision=decision,
            notes=notes,
            target_step=target_step,
        )
    )
    _log(
        session,
        task,
        kind=ExecutionKind.APPROVAL,
        status=ExecutionStatus.SUCCEEDED
        if decision == ApprovalDecision.APPROVED
        else ExecutionStatus.REVISE
        if decision == ApprovalDecision.REVISION_REQUESTED
        else ExecutionStatus.FAILED,
        agent_key=HUMAN_ACTOR,
        output={"decision": decision.value, "notes": notes, "target_step": target_step},
        actor=(ActorType.USER, str(user.id)),
    )


def approve(session: Session, task_id: uuid.UUID, user: User, notes: str | None) -> OrgTask:
    task = _get(session, task_id)
    _require_reviewer(user, task)
    if task.status != OrgTaskStatus.AWAITING_APPROVAL:
        raise Conflict(f"Task is {task.status.value}; only AWAITING_APPROVAL can be approved.")
    steps = _steps(session, task)
    gate = next((s for s in steps if s.agent_key == "compliance_agent"), None)
    if gate and gate.status == StepStatus.DONE and not gate.output["passed"]:
        raise Conflict("Compliance violations block approval.")
    _human_approval(session, task, user, ApprovalDecision.APPROVED, notes)
    _complete(session, task, steps, actor=(ActorType.USER, str(user.id)))
    return task


def reject(session: Session, task_id: uuid.UUID, user: User, notes: str) -> OrgTask:
    task = _get(session, task_id)
    _require_reviewer(user, task)
    if task.status in TERMINAL:
        raise Conflict(f"Task is {task.status.value}.")
    if not notes or not notes.strip():
        raise Unprocessable("Rejecting requires notes.")
    _human_approval(session, task, user, ApprovalDecision.REJECTED, notes)
    task.status = OrgTaskStatus.REJECTED
    task.completed_at = datetime.now(UTC)
    return task


def request_revision(
    session: Session, task_id: uuid.UUID, user: User, step_key: str, notes: str
) -> OrgTask:
    task = _get(session, task_id)
    _require_reviewer(user, task)
    if task.status not in (OrgTaskStatus.AWAITING_APPROVAL, OrgTaskStatus.ESCALATED):
        raise Conflict(
            f"Task is {task.status.value}; revisions need AWAITING_APPROVAL or ESCALATED."
        )
    if not notes or not notes.strip():
        raise Unprocessable("A revision request requires notes.")
    if task.human_revisions >= MAX_HUMAN_REVISIONS:
        raise Conflict(f"Revision limit ({MAX_HUMAN_REVISIONS}) reached; approve or reject.")
    spec = next((s for s in WORKFLOWS[task.workflow].steps if s.key == step_key), None)
    if spec is None or not spec.revisable:
        raise Unprocessable(f"Step {step_key!r} cannot be revised by request.")
    steps = _steps(session, task)
    target = next(s for s in steps if s.step_key == step_key)
    task.human_revisions += 1
    _human_approval(session, task, user, ApprovalDecision.REVISION_REQUESTED, notes, step_key)
    for s in steps:  # the target and everything after it re-runs (bounded by the limits above)
        if s.seq >= target.seq:
            s.status = StepStatus.PENDING
            s.iterations = 0
            s.escalation = None
            if s.step_key == step_key:
                s.feedback = [*s.feedback, {"from": "human", "summary": notes, "issues": []}]
    task.status = OrgTaskStatus.PENDING
    session.flush()
    return task


def retry(session: Session, task_id: uuid.UUID, user: User, notes: str) -> OrgTask:
    """Retry an escalated step once (e.g. after a provider outage or a fixed input)."""
    task = _get(session, task_id)
    if user.role not in (UserRole.ANALYST, UserRole.REVIEWER, UserRole.ADMIN):
        raise Forbidden("Analysts and above can retry tasks.")
    if task.status != OrgTaskStatus.ESCALATED:
        raise Conflict(f"Task is {task.status.value}; only ESCALATED tasks can be retried.")
    step = next(s for s in _steps(session, task) if s.status == StepStatus.ESCALATED)
    if step.retries >= MAX_STEP_RETRIES:
        raise Conflict(f"Step {step.step_key} was already retried {MAX_STEP_RETRIES} time(s).")
    step.retries += 1
    step.iterations = 0
    step.status = StepStatus.PENDING
    step.escalation = None
    task.status = OrgTaskStatus.PENDING
    AuditService(session).record(
        actor_type=ActorType.USER,
        actor_id=str(user.id),
        action="org.task_retried",
        entity_type="org_task",
        entity_id=task.id,
        payload={"step": step.step_key, "notes": notes},
    )
    session.flush()
    return task


def cancel(session: Session, task_id: uuid.UUID, user: User, notes: str) -> OrgTask:
    task = _get(session, task_id)
    if task.status in TERMINAL:
        raise Conflict(f"Task is {task.status.value}.")
    task.status = OrgTaskStatus.CANCELLED
    task.completed_at = datetime.now(UTC)
    AuditService(session).record(
        actor_type=ActorType.USER,
        actor_id=str(user.id),
        action="org.task_cancelled",
        entity_type="org_task",
        entity_id=task.id,
        payload={"notes": notes},
    )
    return task


def _get(session: Session, task_id: uuid.UUID) -> OrgTask:
    task = session.get(OrgTask, task_id)
    if task is None:
        raise NotFound("Task not found.")
    return task
