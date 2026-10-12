"""The agent team: building each agent, running each agent's own loop, and delegation.

Every agent is a separate PydanticAI Agent with its own prompt, its own model
instance, its own tool subset, and its own loop (`agent.iter`) with its own
usage limits. Any agent can reach any other through the `ask_teammate` tool,
which starts the teammate's loop and hands its structured report back. All of
it is written to the audit trail step by step.
"""

import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import AgentRunError, ModelHTTPError, UsageLimitExceeded
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import UsageLimits
from pydantic_core import to_jsonable_python

from audit import AuditTrail
from config import (
    MAX_DELEGATION_DEPTH,
    MAX_DELEGATIONS,
    MODEL_NAME,
    OUTPUT_RETRIES,
    TEAM_TOKEN_BUDGET,
    build_model,
    load_prompt,
)
from mcp_connection import create_mcp_toolset, tools_for_agent
from models import AgentDeps, AgentName, ApprovalMode, TeamRun

def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]


PART_FIELDS = ("part_kind", "content", "tool_name", "args", "tool_call_id", "model_name")


@dataclass(frozen=True)
class AgentSpec:
    name: AgentName
    title: str
    role: str  # one line, shown to teammates so they know when to ask this agent
    mcp_tools: frozenset[str]
    output_type: type[BaseModel]
    limits: UsageLimits
    settings: ModelSettings


def _usage(obj: Any) -> Any:
    u = obj.usage
    return u() if callable(u) else u


def _part(part: Any) -> dict:
    data = to_jsonable_python(part, fallback=str)
    return {k: data[k] for k in PART_FIELDS if k in data and data[k] not in (None, "")}


def _describe_node(node: Any) -> dict:
    """What happened in one loop step, in enough detail to audit it afterwards."""
    if Agent.is_user_prompt_node(node):
        return {"node": "user_prompt"}
    if Agent.is_model_request_node(node):
        # What is about to be sent to the model: the prompt, tool results, or retry requests.
        return {"node": "model_request", "parts": [_part(p) for p in node.request.parts]}
    if Agent.is_call_tools_node(node):
        # What the model answered: text and/or tool calls, plus token usage for this request.
        resp = node.model_response
        return {
            "node": "model_response",
            "model_name": resp.model_name,
            "finish_reason": getattr(resp, "finish_reason", None),
            "usage": to_jsonable_python(resp.usage, fallback=str),
            "parts": [_part(p) for p in resp.parts],
        }
    if Agent.is_end_node(node):
        return {"node": "end", "output": to_jsonable_python(node.data.output, fallback=str)}
    return {"node": type(node).__name__}


class Team:
    def __init__(self, specs: list[AgentSpec], audit: AuditTrail | None = None, mcp: MCPToolset | None = None):
        self.specs: dict[AgentName, AgentSpec] = {s.name: s for s in specs}
        self.audit = audit or AuditTrail()
        self.mcp = mcp or create_mcp_toolset()
        self.agents: dict[AgentName, Agent] = {s.name: self._build_agent(s) for s in specs}

    # ---- construction -------------------------------------------------------

    def _directory(self, me: AgentName) -> str:
        lines = [f"- `{s.name}` ({s.title}): {s.role}" for s in self.specs.values() if s.name != me]
        return (
            "\n\n## Your teammates (reach them with the `ask_teammate` tool)\n"
            + "\n".join(lines)
            + f"\n\nDelegation limits: you cannot ask yourself or anyone who is already waiting on you, "
            f"chains stop at depth {MAX_DELEGATION_DEPTH}, and the team has {MAX_DELEGATIONS} delegations per run. "
            "Ask a precise question that includes the ticket id and the facts you already have, so the "
            "teammate does not have to repeat your lookups."
        )

    def _build_agent(self, spec: AgentSpec) -> Agent:
        agent = Agent(
            build_model(),  # each agent gets its own model instance
            name=spec.name,
            instructions=load_prompt(spec.name) + self._directory(spec.name),
            deps_type=AgentDeps,
            output_type=spec.output_type,
            toolsets=[tools_for_agent(self.mcp, spec.mcp_tools)],
            model_settings=spec.settings,
            retries=OUTPUT_RETRIES,
        )
        team = self

        @agent.tool
        async def ask_teammate(ctx: RunContext[AgentDeps], teammate: AgentName, request: str) -> dict:
            """Delegate work to, or ask a question of, another agent on the team.

            The teammate runs its own loop with its own tools and returns its report
            (summary, facts with sources, actions taken, recommended status, whether a
            human is needed). Returns ok=False with a reason if the request is refused
            or the teammate fails.
            """
            return await team.delegate(ctx.deps, teammate, request)

        return agent

    # ---- delegation ---------------------------------------------------------

    async def delegate(self, deps: AgentDeps, teammate: AgentName, request: str) -> dict:
        run = deps.run
        refusal = None
        if teammate not in self.agents:
            refusal = f"unknown teammate '{teammate}'"
        elif teammate == deps.agent:
            refusal = "you cannot delegate to yourself"
        elif teammate in deps.chain:
            refusal = f"{teammate} is already waiting on you (chain {' -> '.join(deps.chain)}); answer them instead"
        elif deps.depth + 1 > MAX_DELEGATION_DEPTH:
            refusal = f"delegation depth limit ({MAX_DELEGATION_DEPTH}) reached; finish with what you have"
        elif run.delegations >= MAX_DELEGATIONS:
            refusal = f"team delegation budget ({MAX_DELEGATIONS}) used up; finish with what you have"
        elif run.total_tokens >= TEAM_TOKEN_BUDGET:
            refusal = f"team token budget ({TEAM_TOKEN_BUDGET}) used up; finish with what you have"

        run.audit.record(run.run_id, "delegation", deps, to=teammate, request=request,
                         accepted=refusal is None, refusal=refusal)
        if refusal:
            return {"ok": False, "refused": True, "reason": refusal}

        run.delegations += 1
        return await self.run_agent(teammate, request, run, parent=deps)

    # ---- one agent loop -----------------------------------------------------

    async def run_agent(self, name: AgentName, prompt: str, run: TeamRun, parent: AgentDeps | None = None) -> dict:
        spec = self.specs[name]
        run.agent_runs += 1
        deps = AgentDeps(
            run=run,
            agent=name,
            agent_run_id=f"{run.run_id}-{run.agent_runs:02d}-{name}",
            chain=(parent.chain if parent else ()) + (name,),
        )
        run.audit.record(
            run.run_id, "agent_run_start", deps,
            prompt=prompt,
            requested_by=parent.agent if parent else "human",
            model=MODEL_NAME,
            prompt_file=f"backend/prompts/{name}.md",
            mcp_tools=sorted(spec.mcp_tools),
            limits=to_jsonable_python(spec.limits, fallback=str),
        )

        started = time.monotonic()
        agent_run = None
        try:
            async with self.agents[name].iter(prompt, deps=deps, usage_limits=spec.limits) as agent_run:
                step = 0
                async for node in agent_run:
                    step += 1
                    run.audit.record(run.run_id, "agent_step", deps, step=step, **_describe_node(node))
            result = agent_run.result
        except (UsageLimitExceeded, ModelHTTPError, AgentRunError) as exc:
            usage = _usage(agent_run) if agent_run else None
            run.total_tokens += getattr(usage, "total_tokens", 0) or 0
            run.audit.record(
                run.run_id, "agent_run_end", deps,
                status="error", error=f"{type(exc).__name__}: {exc}",
                usage=to_jsonable_python(usage, fallback=str),
                seconds=round(time.monotonic() - started, 2),
            )
            if parent is None:
                raise
            return {"ok": False, "agent": name, "error": f"{type(exc).__name__}: {exc}"}

        usage = _usage(result)
        run.total_tokens += usage.total_tokens or 0
        output = result.output.model_dump(mode="json")
        run.audit.record(
            run.run_id, "agent_run_end", deps,
            status="ok", output=output,
            usage=to_jsonable_python(usage, fallback=str),
            team_tokens_so_far=run.total_tokens,
            seconds=round(time.monotonic() - started, 2),
        )
        return {"ok": True, "agent": name, "report": output}

    # ---- a full team run ----------------------------------------------------

    async def run(
        self,
        prompt: str,
        entry_agent: AgentName = "boss",
        approver: str | None = None,
        approval_mode: ApprovalMode = "queue",
        run_id: str | None = None,
        ticket_id: int | None = None,
    ) -> dict:
        run = TeamRun(
            run_id=run_id or new_run_id(),
            audit=self.audit,
            approver=approver,
            approval_mode=approval_mode,
        )
        self.audit.record(run.run_id, "team_run_start", entry_agent=entry_agent, prompt=prompt,
                          ticket_id=ticket_id, approver=approver, approval_mode=approval_mode, model=MODEL_NAME)
        result: dict = {"ok": False}
        try:
            async with self.mcp:  # one MCP server process for the whole team run
                result = await self.run_agent(entry_agent, prompt, run)
            return result
        finally:
            self.audit.record(run.run_id, "team_run_end", ok=result.get("ok", False),
                              agent_runs=run.agent_runs, delegations=run.delegations,
                              total_tokens=run.total_tokens)
