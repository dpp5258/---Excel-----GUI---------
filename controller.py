"""业务控制层 — 调度核心，连接 GUI 与存储层"""

from datetime import datetime
from typing import Optional

import os

from storage import ExcelStorage, get_app_dir
from model import Task, setup_logger


class TaskController:

    def __init__(self):
        self.storage = ExcelStorage()
        self.logger = setup_logger(os.path.join(get_app_dir(), "control.log"))
        self.todo_tasks: dict[int, Task] = {}
        self.done_tasks: dict[int, Task] = {}
        self.archive_tasks: dict[int, Task] = {}

    # ── 数据加载 ──────────────────────────────────────

    def load_all_tasks(self) -> None:
        """从 Excel 加载三表数据到内存 dict。"""
        self.storage.init_file()
        todo_rows, done_rows, archive_rows = self.storage.read_all()
        self.todo_tasks = self._rows_to_dict(todo_rows)
        self.done_tasks = self._rows_to_dict(done_rows)
        self.archive_tasks = self._rows_to_dict(archive_rows)
        self._enforce_business_rules()
        self.logger.info(
            f"加载数据: 待办{len(self.todo_tasks)} 已完成{len(self.done_tasks)} "
            f"归档{len(self.archive_tasks)}"
        )

    def refresh(self) -> None:
        """重新读取 Excel 覆盖内存数据（未保存的 GUI 操作将丢失）。"""
        self.logger.info("刷新数据")
        self.load_all_tasks()

    # ── CRUD ──────────────────────────────────────────

    def create_task(
        self,
        title: str,
        content: str = "",
        create_time: str = "",
        deadline: str = "",
        priority: int = 0,
        note: str = "",
    ) -> Task:
        """新增待办任务，自动生成 ID，创建时间默认当前时间。"""
        if not title or not title.strip():
            raise ValueError("任务标题不能为空")
        if not 0 <= priority <= 100:
            raise ValueError("优先级范围为 0-100")

        new_id = self._next_id()
        task = Task(
            id=new_id,
            title=title.strip(),
            content=content,
            create_time=create_time or datetime.now().strftime("%Y-%m-%d %H:%M"),
            deadline=deadline,
            priority=priority,
            note=note,
            status="未开始",
        )
        self.todo_tasks[task.id] = task
        self._sync_to_excel()
        self.logger.info(f"新增任务 id={task.id} title={task.title}")
        return task

    def update_task(self, task_id: int, **fields) -> Task:
        """修改指定任务的字段。task_id 不得修改。"""
        task = self._find_task(task_id)
        allowed = {"title", "content", "create_time", "deadline", "priority", "note", "status", "finish_desc"}
        for key, value in fields.items():
            if key in allowed:
                setattr(task, key, value)
        if hasattr(task, "title") and not task.title.strip():
            raise ValueError("任务标题不能为空")
        self._sync_to_excel()
        self.logger.info(f"编辑任务 id={task_id}")
        return task

    def delete_task(self, task_id: int) -> None:
        """永久删除指定ID的任务。"""
        task = self._find_task(task_id)
        for d in (self.todo_tasks, self.done_tasks, self.archive_tasks):
            if task_id in d:
                del d[task_id]
                break
        self._sync_to_excel()
        self.logger.info(f"删除任务 id={task_id} title={task.title}")

    # ── 状态流转 ──────────────────────────────────────

    def finish_task(self, task_id: int, finish_desc: str = "") -> None:
        """待办 → 已完成。"""
        if task_id not in self.todo_tasks:
            raise KeyError(f"待办列表中不存在任务 id={task_id}")
        task = self.todo_tasks.pop(task_id)
        task.status = "已完成"
        task.finish_desc = finish_desc
        self.done_tasks[task.id] = task
        self._sync_to_excel()
        self.logger.info(f"完成任务 id={task_id}")

    def revert_task(self, task_id: int) -> None:
        """已完成 → 待办，状态重置为「未开始」，完成情况清空。"""
        if task_id not in self.done_tasks:
            raise KeyError(f"已完成列表中不存在任务 id={task_id}")
        task = self.done_tasks.pop(task_id)
        task.status = "未开始"
        task.finish_desc = ""
        self.todo_tasks[task.id] = task
        self._sync_to_excel()
        self.logger.info(f"撤回任务 id={task_id}")

    def archive_all_done(self) -> int:
        """清空已完成：全部迁移至归档表，返回归档数量。"""
        count = len(self.done_tasks)
        if count == 0:
            return 0
        for task in self.done_tasks.values():
            self.archive_tasks[task.id] = task
        self.done_tasks.clear()
        self._sync_to_excel()
        self.logger.info(f"归档任务 {count} 条")
        return count

    # ── 查询 ──────────────────────────────────────────

    def search(self, keyword: str) -> tuple[list[Task], list[Task]]:
        """按标题关键字搜索（不区分大小写），返回 (待办列表, 已完成列表)。"""
        kw = keyword.strip().lower()
        if not kw:
            return (self.get_sorted_todo(), self.get_sorted_done())
        matched_todo = [t for t in self.todo_tasks.values() if kw in t.title.lower()]
        matched_done = [t for t in self.done_tasks.values() if kw in t.title.lower()]
        return (self._sort_tasks(matched_todo), self._sort_tasks(matched_done))

    def get_sorted_todo(self) -> list[Task]:
        return self._sort_tasks(self.todo_tasks.values())

    def get_sorted_done(self) -> list[Task]:
        return self._sort_tasks(self.done_tasks.values())

    def get_task(self, task_id: int) -> Optional[Task]:
        """按 ID 查找任务，三表都找。"""
        for d in (self.todo_tasks, self.done_tasks, self.archive_tasks):
            if task_id in d:
                return d[task_id]
        return None

    # ── 内部方法 ──────────────────────────────────────

    def _next_id(self) -> int:
        existing = set(self.todo_tasks) | set(self.done_tasks) | set(self.archive_tasks)
        if not existing:
            return 1
        return max(existing) + 1

    def _find_task(self, task_id: int) -> Task:
        """三表查找，找不到抛 KeyError。"""
        for d in (self.todo_tasks, self.done_tasks, self.archive_tasks):
            if task_id in d:
                return d[task_id]
        raise KeyError(f"任务 id={task_id} 不存在")

    def _sync_to_excel(self) -> None:
        """将内存三组 dict 全量写入 Excel。"""
        self.storage.write_all(
            [Task.task_to_row(t) for t in self._sort_tasks(self.todo_tasks.values())],
            [Task.task_to_row(t) for t in self._sort_tasks(self.done_tasks.values())],
            [Task.task_to_row(t) for t in self._sort_tasks(self.archive_tasks.values())],
        )

    @staticmethod
    def _sort_tasks(tasks) -> list[Task]:
        """排序规则：优先级降序 → 截止时间升序 → ID 升序。"""
        def sort_key(t: Task):
            dl = t.deadline if t.deadline else "9999-99-99 99:99"
            return (-t.priority, dl, t.id)
        return sorted(tasks, key=sort_key)

    @staticmethod
    def _rows_to_dict(rows: list[list]) -> dict[int, Task]:
        result: dict[int, Task] = {}
        seen_ids: set[int] = set()
        for row in rows:
            task = Task.row_to_task(row)
            if task.id == 0:
                continue
            if task.id in seen_ids:
                task.id = max(seen_ids) + 1 if seen_ids else 1
            seen_ids.add(task.id)
            result[task.id] = task
        return result

    def _enforce_business_rules(self) -> None:
        """修正违规数据：待办表中已完成状态 → 移入已完成表。"""
        migrate_ids = [
            tid for tid, t in self.todo_tasks.items()
            if t.status == "已完成"
        ]
        for tid in migrate_ids:
            task = self.todo_tasks.pop(tid)
            self.done_tasks[tid] = task
        if migrate_ids:
            self.logger.info(f"自动迁移 {len(migrate_ids)} 条异常状态任务到已完成表")
            self._sync_to_excel()

        # 已完成/归档表中非「已完成」状态 → 修正
        for d in (self.done_tasks, self.archive_tasks):
            for t in d.values():
                if t.status != "已完成":
                    t.status = "已完成"
