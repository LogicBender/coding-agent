from repository import TaskRepository
from models import Task
from typing import List

class TaskService:
    def __init__(self, repo: TaskRepository):
        self.repo = repo

    def create_task(self, title: str) -> Task:
        if not title:
            raise ValueError("Title cannot be empty")
        task = Task(id=0, title=title)
        return self.repo.add(task)

    def list_all_tasks(self) -> List[Task]:
        return self.repo.get_all()