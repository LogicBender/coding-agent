from repository import TaskRepository
from model import Task
from typing import List


class TaskService:
    def __init__(self, repo: TaskRepository):
        self.repo = repo

    def create_task(self, title: str, priority: str = "medium") -> Task:
        if not title:
            raise ValueError("Title cannot be empty")
        task = Task(id=0, title=title, priority=priority)
        return self.repo.add(task)

    def list_all_tasks(self) -> List[Task]:
        return self.repo.get_all()

    def list_tasks_by_priority(self, priority: str) -> List[Task]:
        """返回指定优先级的任务列表"""
        return self.repo.get_by_priority(priority)
