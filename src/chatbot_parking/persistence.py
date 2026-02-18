"""Persistence backends for chat threads, admin approvals, and reservations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
import os
from typing import Any
from uuid import uuid4


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class PersistenceSettings:
    backend: str
    cosmos_endpoint: str | None
    cosmos_key: str | None
    cosmos_use_managed_identity: bool
    cosmos_database: str
    cosmos_threads_container: str
    cosmos_approvals_container: str
    cosmos_reservations_container: str


class Persistence:
    def get_thread(self, thread_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def upsert_thread(self, thread_id: str, state: dict[str, Any]) -> None:
        raise NotImplementedError

    def create_approval(self, payload: dict[str, Any]) -> str:
        raise NotImplementedError

    def get_approval(self, request_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def list_pending_approvals(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def list_decided_approvals(self, approved: bool | None = None) -> list[dict[str, Any]]:
        """Return approvals that have a decision (approved/declined)."""
        raise NotImplementedError

    def set_approval_decision(
        self,
        request_id: str,
        approved: bool,
        notes: str | None = None,
    ) -> dict[str, Any] | None:
        raise NotImplementedError

    def append_reservation(
        self,
        name: str,
        car_number: str,
        reservation_period: str,
        approval_time: str,
        request_id: str | None = None,
        spot_id: str | None = None,
        start_at: str | None = None,
        end_at: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def list_reservations(self, limit: int = 200) -> list[dict[str, Any]]:
        raise NotImplementedError


class InMemoryPersistence(Persistence):
    def __init__(self) -> None:
        self.threads: dict[str, dict[str, Any]] = {}
        self.approvals: dict[str, dict[str, Any]] = {}
        self.reservations: list[dict[str, Any]] = []

    def get_thread(self, thread_id: str) -> dict[str, Any] | None:
        entry = self.threads.get(thread_id)
        if not entry:
            return None
        return dict(entry.get("state", {}))

    def upsert_thread(self, thread_id: str, state: dict[str, Any]) -> None:
        self.threads[thread_id] = {
            "thread_id": thread_id,
            "state": dict(state),
            "updated_at": _utc_now(),
        }

    def create_approval(self, payload: dict[str, Any]) -> str:
        request_id = str(uuid4())
        self.approvals[request_id] = {
            "request_id": request_id,
            "payload": payload,
            "decision": None,
            "created_at": _utc_now(),
        }
        return request_id

    def get_approval(self, request_id: str) -> dict[str, Any] | None:
        item = self.approvals.get(request_id)
        if not item:
            return None
        return dict(item)

    def list_pending_approvals(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self.approvals.values() if not item.get("decision")]

    def list_decided_approvals(self, approved: bool | None = None) -> list[dict[str, Any]]:
        decided = [dict(item) for item in self.approvals.values() if item.get("decision")]
        if approved is None:
            return decided
        return [
            item
            for item in decided
            if isinstance(item.get("decision"), dict) and item["decision"].get("approved") is approved
        ]

    def set_approval_decision(
        self,
        request_id: str,
        approved: bool,
        notes: str | None = None,
    ) -> dict[str, Any] | None:
        item = self.approvals.get(request_id)
        if not item:
            return None

        decision = {
            "approved": approved,
            "decided_at": _utc_now(),
            "notes": notes,
        }
        item["decision"] = decision
        return dict(decision)

    def append_reservation(
        self,
        name: str,
        car_number: str,
        reservation_period: str,
        approval_time: str,
        request_id: str | None = None,
        spot_id: str | None = None,
        start_at: str | None = None,
        end_at: str | None = None,
    ) -> dict[str, Any]:
        entry = {
            "id": str(uuid4()),
            "request_id": request_id,
            "name": name,
            "car_number": car_number,
            "reservation_period": reservation_period,
            "approval_time": approval_time,
            "spot_id": spot_id,
            "start_at": start_at,
            "end_at": end_at,
            "created_at": _utc_now(),
        }
        self.reservations.append(entry)
        return dict(entry)

    def list_reservations(self, limit: int = 200) -> list[dict[str, Any]]:
        # Return newest first.
        items = list(self.reservations)[-limit:]
        items.reverse()
        return [dict(item) for item in items]


class CosmosPersistence(Persistence):
    def __init__(self, settings: PersistenceSettings) -> None:
        from azure.cosmos import CosmosClient

        if not settings.cosmos_endpoint:
            raise ValueError("COSMOS_DB_ENDPOINT is required for Cosmos backend")

        credential = None
        if settings.cosmos_key:
            credential = settings.cosmos_key
        elif settings.cosmos_use_managed_identity:
            from azure.identity import DefaultAzureCredential

            # Prefer non-interactive credentials (managed identity in Azure, or env-based locally).
            credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)

        if credential is None:
            raise ValueError(
                "Cosmos backend requires COSMOS_DB_KEY or COSMOS_USE_MANAGED_IDENTITY=true"
            )

        client = CosmosClient(settings.cosmos_endpoint, credential=credential)
        database = client.get_database_client(settings.cosmos_database)
        self._threads = database.get_container_client(settings.cosmos_threads_container)
        self._approvals = database.get_container_client(settings.cosmos_approvals_container)
        self._reservations = database.get_container_client(settings.cosmos_reservations_container)

    def get_thread(self, thread_id: str) -> dict[str, Any] | None:
        try:
            item = self._threads.read_item(item=thread_id, partition_key=thread_id)
            return dict(item.get("state") or {})
        except Exception:
            return None

    def upsert_thread(self, thread_id: str, state: dict[str, Any]) -> None:
        self._threads.upsert_item(
            {
                "id": thread_id,
                "thread_id": thread_id,
                "state": dict(state),
                "updated_at": _utc_now(),
            }
        )

    def create_approval(self, payload: dict[str, Any]) -> str:
        request_id = str(uuid4())
        self._approvals.upsert_item(
            {
                "id": request_id,
                "request_id": request_id,
                "payload": payload,
                "decision": None,
                "created_at": _utc_now(),
            }
        )
        return request_id

    def get_approval(self, request_id: str) -> dict[str, Any] | None:
        try:
            item = self._approvals.read_item(item=request_id, partition_key=request_id)
            return {
                "request_id": item.get("request_id", request_id),
                "payload": item.get("payload") or {},
                "decision": item.get("decision"),
                "created_at": item.get("created_at"),
            }
        except Exception:
            return None

    def list_pending_approvals(self) -> list[dict[str, Any]]:
        query = (
            "SELECT * FROM c WHERE NOT IS_DEFINED(c.decision) OR IS_NULL(c.decision)"
        )
        items = self._approvals.query_items(query=query, enable_cross_partition_query=True)
        return [
            {
                "request_id": item.get("request_id", item.get("id")),
                "payload": item.get("payload") or {},
                "decision": item.get("decision"),
                "created_at": item.get("created_at"),
            }
            for item in items
        ]

    def list_decided_approvals(self, approved: bool | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM c WHERE IS_DEFINED(c.decision) AND NOT IS_NULL(c.decision)"
        if approved is True:
            query = query + " AND c.decision.approved = true"
        elif approved is False:
            query = query + " AND c.decision.approved = false"

        items = self._approvals.query_items(query=query, enable_cross_partition_query=True)
        return [
            {
                "request_id": item.get("request_id", item.get("id")),
                "payload": item.get("payload") or {},
                "decision": item.get("decision"),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
            }
            for item in items
        ]

    def set_approval_decision(
        self,
        request_id: str,
        approved: bool,
        notes: str | None = None,
    ) -> dict[str, Any] | None:
        approval = self.get_approval(request_id)
        if not approval:
            return None

        decision = {
            "approved": approved,
            "decided_at": _utc_now(),
            "notes": notes,
        }
        self._approvals.upsert_item(
            {
                "id": request_id,
                "request_id": request_id,
                "payload": approval.get("payload") or {},
                "decision": decision,
                "created_at": approval.get("created_at") or _utc_now(),
                "updated_at": _utc_now(),
            }
        )
        return dict(decision)

    def append_reservation(
        self,
        name: str,
        car_number: str,
        reservation_period: str,
        approval_time: str,
        request_id: str | None = None,
        spot_id: str | None = None,
        start_at: str | None = None,
        end_at: str | None = None,
    ) -> dict[str, Any]:
        entry_id = str(uuid4())
        partition_key = request_id or entry_id
        payload = {
            "id": entry_id,
            "request_id": request_id,
            "partition_key": partition_key,
            "name": name,
            "car_number": car_number,
            "reservation_period": reservation_period,
            "approval_time": approval_time,
            "spot_id": spot_id,
            "start_at": start_at,
            "end_at": end_at,
            "created_at": _utc_now(),
        }
        self._reservations.upsert_item(payload)
        return payload

    def list_reservations(self, limit: int = 200) -> list[dict[str, Any]]:
        # Cosmos supports ORDER BY with cross-partition query.
        query = "SELECT * FROM c ORDER BY c.created_at DESC"
        items = self._reservations.query_items(query=query, enable_cross_partition_query=True)
        results: list[dict[str, Any]] = []
        for item in items:
            results.append(dict(item))
            if len(results) >= limit:
                break
        return results


@lru_cache(maxsize=1)
def get_persistence_settings() -> PersistenceSettings:
    return PersistenceSettings(
        backend=os.getenv("PERSISTENCE_BACKEND", "auto").lower(),
        cosmos_endpoint=os.getenv("COSMOS_DB_ENDPOINT"),
        cosmos_key=os.getenv("COSMOS_DB_KEY"),
        cosmos_use_managed_identity=os.getenv("COSMOS_USE_MANAGED_IDENTITY", "false").strip().lower()
        in {"1", "true", "yes", "on"},
        cosmos_database=os.getenv("COSMOS_DB_DATABASE", "chatbotParking"),
        cosmos_threads_container=os.getenv("COSMOS_DB_CONTAINER_THREADS", "threads"),
        cosmos_approvals_container=os.getenv("COSMOS_DB_CONTAINER_APPROVALS", "approvals"),
        cosmos_reservations_container=os.getenv(
            "COSMOS_DB_CONTAINER_RESERVATIONS", "reservations"
        ),
    )


IN_MEMORY_PERSISTENCE = InMemoryPersistence()


@lru_cache(maxsize=1)
def get_persistence() -> Persistence:
    settings = get_persistence_settings()

    use_cosmos = settings.backend == "cosmos" or (
        settings.backend == "auto"
        and settings.cosmos_endpoint
        and (settings.cosmos_key or settings.cosmos_use_managed_identity)
    )

    if use_cosmos:
        try:
            return CosmosPersistence(settings)
        except Exception:
            # If the caller explicitly requested Cosmos, fail closed (don't silently
            # fall back to in-memory state in production).
            if settings.backend == "cosmos":
                raise
            return IN_MEMORY_PERSISTENCE

    return IN_MEMORY_PERSISTENCE
