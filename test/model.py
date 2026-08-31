from dataclasses import dataclass
from enum import IntEnum


class Priority(IntEnum):
    """任务优先级，数值越大优先级越高"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3


@dataclass
class Task:
    id: int
    title: str
    is_completed: bool = False
    priority: Priority = Priority.MEDIUM
