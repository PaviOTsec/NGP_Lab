"""Application session: the not-ready/ready lifecycle that everything else hangs off.

The console starts with no credentials. The operator picks a credentials file in the app
(uploaded from the browser, or a path on MC01); loading it builds the inventory and the
session pool and warms connections. Unloading closes every session. There is exactly one
AppSession per running backend.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.config import Settings
from app.core.audit import AuditLog
from app.core.credentials import CredentialStore
from app.core.pool import SessionPool
from app.models.inventory import Inventory


class SessionNotReady(Exception):
    """Raised when an operation needs loaded credentials and there aren't any."""


@dataclass
class AppSession:
    settings: Settings
    audit: AuditLog = field(init=False)
    _creds: CredentialStore | None = field(default=None, init=False)
    _pool: SessionPool | None = field(default=None, init=False)
    _inventory: Inventory | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        # The audit log is available from launch, so pre-load events (clipboard) are recorded.
        self.audit = AuditLog(self.settings.audit_abs, self.settings.audit.rotate_mb)

    @property
    def ready(self) -> bool:
        return self._creds is not None

    @property
    def credentials_source(self) -> str:
        return self._creds.source if self._creds else ""

    @property
    def credentials(self) -> CredentialStore:
        if self._creds is None:
            raise SessionNotReady("no credentials loaded")
        return self._creds

    @property
    def pool(self) -> SessionPool:
        if self._pool is None:
            raise SessionNotReady("no credentials loaded")
        return self._pool

    @property
    def inventory(self) -> Inventory:
        if self._inventory is None:
            raise SessionNotReady("no credentials loaded")
        return self._inventory

    async def load_credentials(self, store: CredentialStore, *, remember_path: str = "") -> None:
        """Swap in a credentials store. Any existing sessions are closed first."""
        if self.ready:
            await self.unload("reload")
        inventory = Inventory.load(self.settings.inventory_path)
        self._creds = store
        self._inventory = inventory
        self._pool = SessionPool(settings=self.settings, inventory=inventory, creds=store)
        self.audit.record(action="credentials-load", target="-", result="ok",
                          detail={"source": store.source, "entries": len(store.names())})
        if remember_path:
            self._remember({"last_credentials_path": remember_path})

    async def unload(self, reason: str = "manual") -> None:
        if not self.ready:
            return
        self.audit.record(action="credentials-unload", target="-", result=reason)
        if self._pool is not None:
            await self._pool.close_all()
        self._creds = None
        self._pool = None
        self._inventory = None

    async def warm_up(self):
        return await self.pool.warm_all()

    # --- remembered, non-secret state ---

    def remembered(self) -> dict:
        try:
            return json.loads(self.settings.state_abs.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _remember(self, values: dict) -> None:
        state = self.remembered() | values
        try:
            self.settings.state_abs.parent.mkdir(parents=True, exist_ok=True)
            self.settings.state_abs.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except OSError:
            pass  # remembering is a convenience; never fail a load over it
