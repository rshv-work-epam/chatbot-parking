"""Durable orchestrator: runs a single chat turn via an activity."""

from __future__ import annotations

import azure.durable_functions as df


def orchestrator(context: df.DurableOrchestrationContext):
    payload = context.get_input() or {}
    result = yield context.call_activity("run_chat_turn_activity", payload)
    return result


main = df.Orchestrator.create(orchestrator)

