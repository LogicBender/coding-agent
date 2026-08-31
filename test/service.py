from repository import TaskRepository
from model import Task, Priority
from typing import List, Optional


class TaskService:
    def __init__(self, repo: TaskRepository):
        self.repo = repo

    def create_task(self, title: str, priority: Priority = Priority.MEDIUM) -> Task:
        if not title:
            raise ValueError("Title cannot be empty")
        task = Task(id=0, title=title, priority=priority)
        return self.repo.add(task)

    def list_all_tasks(self) -> List[Task]:
        return self.repo.get_all()

    def list_tasks_sorted_by_priority(self) -> List[Task]:
        """按优先级从高到低返回任务列表"""
        return self.repo.get_all_sorted_by_priority()

    def list_tasks_by_priority(self, priority: Priority) -> List[Task]:
        """返回指定优先级的任务列表"""
        return [t for t in self.repo.get_all() if t.priority == priority]

    def set_task_priority(self, task_id: int, priority: Priority) -> Optional[Task]:
        """修改指定任务的优先级，任务不存在时返回 None"""
        task = self.repo.get(task_id)
        if task is None:
            return None
        task.priority = priority
        return task
