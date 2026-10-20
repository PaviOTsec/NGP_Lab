from app.routes import (
    audit as audit_routes,
    board as board_routes,
    fanout as fanout_routes,
    files as files_routes,
    hyperv as hyperv_routes,
    inventory as inventory_routes,
    playbooks as playbooks_routes,
    session as session_routes,
    terminals as terminals_routes,
    vmtext as vmtext_routes,
)

__all__ = [
    "audit_routes",
    "board_routes",
    "fanout_routes",
    "files_routes",
    "hyperv_routes",
    "inventory_routes",
    "playbooks_routes",
    "session_routes",
    "terminals_routes",
    "vmtext_routes",
]
