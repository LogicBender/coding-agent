from repository import TaskRepository
from service import TaskService
from model import Priority


def main():
    repo = TaskRepository()
    service = TaskService(repo)

    # 模拟用户操作
    service.create_task("Buy milk", Priority.LOW)
    service.create_task("Write code", Priority.HIGH)
    service.create_task("Pay bills", Priority.MEDIUM)
    service.create_task("Read a book")  # 使用默认优先级

    print("=== 全部任务 ===")
    for t in service.list_all_tasks():
        print(_format_task(t))

    print("\n=== 按优先级排序（高 -> 低）===")
    for t in service.list_tasks_sorted_by_priority():
        print(_format_task(t))

    print("\n=== 仅高优先级任务 ===")
    for t in service.list_tasks_by_priority(Priority.HIGH):
        print(_format_task(t))

    print("\n=== 修改任务 1 优先级为 HIGH ===")
    updated = service.set_task_priority(1, Priority.HIGH)
    if updated:
        print(_format_task(updated))


def _format_task(t):
    status = "[x]" if t.is_completed else "[ ]"
    return f"{status} {t.id}: [{t.priority.name}] {t.title}"


if __name__ == "__main__":
    main()
