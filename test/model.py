from dataclasses import dataclass
from typing import Optional

@dataclass
class Task:
    id: int
    title: str
    is_completed: bool = False