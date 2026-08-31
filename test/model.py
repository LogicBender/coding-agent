from dataclasses import dataclass


@dataclass
class Task:
    id: int
    title: str
    is_completed: bool = False
    priority: str = "medium"
