"""
ARIA — conversational recording, end to end.

One function, `handle_turn`, wires the four deterministic pieces together:

    aria_nlu       what did the farmer say
    aria_dialogue  what is still missing, and has it been confirmed
    (resolution)   which flock do they mean
    aria_actions   write it through the domain services

No AI provider is reachable from any of it. A farm with no Gemini or Claude key
configured, or a phone with no signal reaching them, records mortality exactly
the same way. That is the Module 13 requirement that operational actions never
depend on an LLM, and it falls out of the architecture rather than being bolted
on as a fallback.

`handle_turn` is stateless. The dialogue state travels with the request and
comes back in the response, so the caller decides where it lives — today the
frontend holds it for the length of a recording, which keeps a half-finished
mortality from outliving the conversation it belongs to.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.farm import Farm
from app.services import aria_actions, aria_dialogue
from app.services.aria_dialogue import DialogueState, Stage
from app.services.aria_nlu import Intent, parse


@dataclass
class TurnResult:
    """
    What ARIA says, and what the caller should do next.

    `handled` is the important flag: False means this was not a recording
    utterance at all and the caller should fall through to the existing Q&A
    path. A question about feed stock must not be answered by a slot-filler.
    """

    handled: bool
    reply: str = ""
    stage: str = ""
    options: list[str] = field(default_factory=list)
    state: dict[str, Any] | None = None
    #: Set once a write has happened.
    saved: bool = False
    summary: str | None = None
    module: str | None = None
    resource_id: str | None = None
    error: str | None = None


async def handle_turn(
    db: AsyncSession,
    farm: Farm,
    current_user: User,
    text: str,
    state_raw: dict[str, Any] | None = None,
    *,
    today: date | None = None,
) -> TurnResult:
    """
    Take one conversational turn.

    Pass the `state` returned by the previous turn to continue a recording;
    pass None to start fresh.
    """
    # Continuing an in-flight recording.
    if state_raw:
        state = DialogueState.from_dict(state_raw)
        state = _absorb_flock_choice(state, text)
        state, reply = aria_dialogue.advance(state, text, today=today)
    else:
        parsed = parse(text, today=today)
        if not parsed.is_actionable:
            # Not a recording. Hand back to the Q&A path untouched.
            return TurnResult(handled=False)
        if parsed.intent in aria_actions.UNSUPPORTED_INTENTS:
            return TurnResult(
                handled=True,
                reply=(
                    "I understood that, but I can't file it yet — purchases and "
                    "sales need a supplier and a category I don't collect in "
                    "conversation. Record it in Finance and I'll pick it up from there."
                ),
                stage=Stage.CANCELLED.value,
            )
        state = aria_dialogue.begin(parsed)
        # Resolve *before* asking anything. Otherwise a single-flock farm gets
        # asked "which flock?" — the dialogue only knows a reference is missing,
        # not that there is nothing to disambiguate.
        state, early = await _resolve_flock_if_needed(db, farm, state, today=today)
        if early is not None:
            return early
        state, reply = aria_dialogue.advance(state, None, today=today)

    if state.stage in (Stage.CANCELLED, Stage.ABANDONED):
        return TurnResult(handled=True, reply=reply.text, stage=state.stage.value)

    # Resolve again after an answer — this is the turn where a farmer's
    # "flock 2" becomes a real id.
    state, resolution_reply = await _resolve_flock_if_needed(db, farm, state, today=today)
    if resolution_reply is not None:
        return resolution_reply

    if state.stage is Stage.READY:
        return await _commit(db, farm, current_user, state)

    return TurnResult(
        handled=True,
        reply=reply.text,
        stage=state.stage.value,
        options=reply.options,
        state=state.to_dict(),
    )


def _absorb_flock_choice(state: DialogueState, text: str) -> DialogueState:
    """
    Match a tapped option back to its flock.

    The UI offers flock names as buttons; tapping one sends the label verbatim.
    Matching it here means the exact-name case never has to round-trip through
    the fuzzy resolver.
    """
    if state.pending != "flock_ref" or not state.flock_choices:
        return state
    answer = (text or "").strip().lower()
    for choice in state.flock_choices:
        if choice["label"].strip().lower() == answer:
            state.slots["flock_id"] = choice["id"]
            state.slots["flock_ref"] = choice["label"]
            state.slots["flock_label"] = choice["label"]
            state.pending = None
            break
    return state


async def _resolve_flock_if_needed(
    db: AsyncSession,
    farm: Farm,
    state: DialogueState,
    *,
    today: date | None,
) -> tuple[DialogueState, TurnResult | None]:
    """
    Turn a flock reference into a flock id, or ask which one.

    Runs whenever the intent needs a flock and one is not yet resolved. An
    unresolvable reference re-opens the question with the real flock names as
    options, which is far more useful than "I couldn't find that flock".
    """
    needs_flock = any(s.name == "flock_ref" for s in state.spec.required)
    if not needs_flock or state.slots.get("flock_id"):
        return state, None

    ref = state.slots.get("flock_ref")
    match, candidates = await aria_actions.resolve_flock(db, farm.id, ref)

    if match:
        state.slots["flock_id"] = str(match.id)
        state.slots["flock_label"] = match.label
        # `missing_required` looks for `flock_ref`, so satisfying only
        # `flock_id` would leave the dialogue still asking for a flock it has
        # already resolved. Set both.
        state.slots["flock_ref"] = match.label
        if state.pending == "flock_ref":
            state.pending = None
        # Resolution alone does not produce a reply — let the caller run the
        # dialogue forward so it asks whatever is genuinely next.
        return state, None

    if ref:
        # They named something we could not match. Ask again, with the options.
        state.slots.pop("flock_ref", None)
        state.pending = "flock_ref"
        state.stage = Stage.COLLECTING
        state.flock_choices = [{"id": str(c.id), "label": c.label} for c in candidates]
        names = ", ".join(c.label for c in candidates) or "none active"
        return state, TurnResult(
            handled=True,
            reply=f"I couldn't find a flock called “{ref}”. Your active flocks are: {names}. Which one?",
            stage=Stage.COLLECTING.value,
            options=[c.label for c in candidates],
            state=state.to_dict(),
        )

    # No reference yet and more than one flock — offer the names.
    state.flock_choices = [{"id": str(c.id), "label": c.label} for c in candidates]
    return state, None


async def _commit(
    db: AsyncSession,
    farm: Farm,
    current_user: User,
    state: DialogueState,
) -> TurnResult:
    payload = aria_dialogue.build_payload(state)
    result = await aria_actions.execute(db, farm, current_user, payload)

    if not result.ok:
        return TurnResult(
            handled=True,
            reply=result.summary,
            stage=Stage.CANCELLED.value,
            saved=False,
            error=result.error,
        )

    return TurnResult(
        handled=True,
        reply=result.summary,
        stage=Stage.READY.value,
        saved=True,
        summary=result.summary,
        module=result.module,
        resource_id=str(result.resource_id) if result.resource_id else None,
    )
