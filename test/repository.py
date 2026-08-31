from model import Task
from typing import List


class TaskRepository:
    def __init__(self):
        self._db = {}
        self._current_id = 1

    def add(self, task: Task) -> Task:
        task.id = self._current_id
        self._db[self._current_id] = task
        self._current_id += 1
        return task

    def get_all(self) -> List[Task]:
        return list(self._db.values())

    def get_by_priority(self, priority: str) -> List[Task]:
        """返回指定优先级的任务列表"""
        return [task for task in self.get_all() if task.priority == priority]
