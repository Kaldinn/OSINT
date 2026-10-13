"""Provider contract and safe subprocess support."""

from __future__ import annotations

import asyncio
import json
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from ..models import Entity, ProviderResult


class Provider(ABC):
    name: str
    command: str | None = None
    supported_entities: set[str] = set()

    def available(self) -> tuple[bool, str]:
        if self.command and not shutil.which(self.command):
            return False, f"program missing: {self.command}"
        return True, "ready"

    @abstractmethod
    async def run(self, entity: Entity, raw_dir: Path, timeout: float) -> ProviderResult: ...

    @abstractmethod
    def normalize(self, raw: Any, entity: Entity) -> ProviderResult: ...

    async def execute(self, args: list[str], timeout: float, cwd: Path | None = None) -> tuple[int, bytes, bytes]:
        process = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=cwd)
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except TimeoutError:
            process.kill(); await process.communicate(); raise
        return process.returncode or 0, stdout, stderr

    @staticmethod
    def load_json(path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))

