"""A mock Transport so core logic (pool, hyperv, vmtext, playbooks) is testable without a host.

Scripts are matched by substring to canned responses, so tests can assert the backend reacts
correctly to e.g. a checkpoint coming back as the wrong type. A response may be a list, in
which case successive matching calls get successive results (the last one repeats).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.api import TransportName
from app.transports.base import CommandResult, Credential, Transport


@dataclass
class MockTransport(Transport):
    name_value: TransportName = TransportName.WINRM
    responses: list[tuple[str, CommandResult | list[CommandResult]]] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)
    files: dict[str, bytes] = field(default_factory=dict)

    @property
    def name(self) -> TransportName:
        return self.name_value

    async def connect(self) -> None:
        self._connected = True

    async def run(self, command: str, *, timeout: int = 120) -> CommandResult:
        self.calls.append(command)
        for needle, res in self.responses:
            if needle in command:
                if isinstance(res, list):
                    return res.pop(0) if len(res) > 1 else res[0]
                return res
        return CommandResult(0, "", "", 1, self.name)

    async def close(self) -> None:
        self._connected = False

    async def read_bytes(self, remote_path: str) -> bytes:
        return self.files.get(remote_path, b"")

    async def write_bytes(self, remote_path: str, data: bytes) -> None:
        self.files[remote_path] = data


def make(name: str = "HOST", **kw) -> MockTransport:
    return MockTransport(
        target_name=name,
        address="10.0.0.1",
        credential=Credential(username="u", password="p", source_entry="e"),
        **kw,
    )


def result(stdout: str = "", exit_code: int = 0, stderr: str = "") -> CommandResult:
    return CommandResult(exit_code, stdout, stderr, 5, TransportName.WINRM)


def vm_json(state: str, checkpoint_type: str = "Production") -> CommandResult:
    return result(f'{{"Name":"VM1","State":"{state}","CheckpointType":"{checkpoint_type}","Uptime":10}}')
