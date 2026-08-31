from repository import TaskRepository
from service import TaskService

def main():
    repo = TaskRepository()
    service = TaskService(repo)
    
    # 模拟用户操作
    service.create_task("Buy milk")
    service.create_task("Write code")
    
    tasks = service.list_all_tasks()
    for t in tasks:
        status = "[x]" if t.is_completed else "[ ]"
        print(f"{status} {t.id}: {t.title}")

if __name__ == "__main__":
    main()