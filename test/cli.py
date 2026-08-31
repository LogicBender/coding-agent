from repository import TaskRepository
from service import TaskService


def main():
    repo = TaskRepository()
    service = TaskService(repo)

    # 模拟用户操作
    service.create_task("Fix critical bug", "high")
    service.create_task("Buy milk")  # 默认 medium，用于对比过滤效果

    print("=== 所有 high 优先级任务 ===")
    for t in service.list_tasks_by_priority("high"):
        status = "[x]" if t.is_completed else "[ ]"
        print(f"{status} {t.id}: [{t.priority}] {t.title}")


if __name__ == "__main__":
    main()
