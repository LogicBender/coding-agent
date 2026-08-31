from model import Task
from typing import List, Optional


class TaskRepository:
    def __init__(self):
        self._db = {}
        self._current_id = 1

    def add(self, task: Task) -> Task:
        task.id = self._current_id
        self._db[self._current_id] = task
        self._current_id += 1
        return task

    def get(self, task_id: int) -> Optional[Task]:
        return self._db.get(task_id)

    def get_all(self) -> List[Task]:
        return list(self._db.values())

    def get_all_sorted_by_priority(self) -> List[Task]:
        """按优先级从高到低排序返回所有任务"""
        return sorted(self.get_all(), key=lambda t: t.priority, reverse=True)
