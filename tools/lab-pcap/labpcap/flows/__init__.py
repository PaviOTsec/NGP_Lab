"""Flow generators. Each module exposes `generate(ctx, name, cfg)`."""
from __future__ import annotations

import random
from dataclasses import dataclass

from ..spec import Spec
from ..timeline import Timeline


@dataclass
class Ctx:
    spec: Spec
    tl: Timeline
    rng: random.Random

    @property
    def duration(self) -> float:
        return self.tl.duration

    def jitter(self, base: float, spread: float) -> float:
        return base + self.rng.uniform(-spread, spread)
