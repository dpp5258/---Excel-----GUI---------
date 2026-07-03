"""任务实体模型 & 截止时间状态枚举 & 日志工具"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging


class DeadlineStatus(Enum):
    EXPIRED = "expired"      # 已过期
    URGENT = "urgent"        # < 3 天
    MODERATE = "moderate"    # 3–7 天（无颜色）
    SAFE = "safe"            # 7–14 天
    DISTANT = "distant"      # > 14 天


# 截止时间状态 → 标识格背景色（MODERATE 不在映射中 = 无填充）
STATUS_COLORS: dict[DeadlineStatus, str] = {
    DeadlineStatus.EXPIRED: "#8B0000",   # 深红
    DeadlineStatus.URGENT:  "#FF8C00",   # 橙色
    DeadlineStatus.SAFE:    "#228B22",   # 绿色
    DeadlineStatus.DISTANT: "#4169E1",   # 蓝色
}

TIME_FORMAT = "%Y-%m-%d %H:%M"


@dataclass
class Task:
    id: int
    title: str
    content: str = ""
    create_time: str = ""
    deadline: str = ""
    priority: int = 0
    note: str = ""
    status: str = "未开始"
    finish_desc: str = ""

    def deadline_status(self) -> DeadlineStatus:
        if not self.deadline:
            return DeadlineStatus.MODERATE
        try:
            dl = datetime.strptime(self.deadline, TIME_FORMAT)
        except ValueError:
            return DeadlineStatus.MODERATE
        now = datetime.now()
        if dl < now:
            return DeadlineStatus.EXPIRED
        if dl <= now + timedelta(days=3):
            return DeadlineStatus.URGENT
        if dl <= now + timedelta(days=7):
            return DeadlineStatus.MODERATE
        if dl <= now + timedelta(days=14):
            return DeadlineStatus.SAFE
        return DeadlineStatus.DISTANT

    @staticmethod
    def row_to_task(row: list) -> "Task":
        cells = list(row) + [""] * (9 - len(row))
        return Task(
            id=int(cells[0]) if cells[0] else 0,
            title=str(cells[1]) if cells[1] else "",
            content=str(cells[2]) if cells[2] else "",
            create_time=str(cells[3]) if cells[3] else "",
            deadline=str(cells[4]) if cells[4] else "",
            priority=int(cells[5]) if cells[5] else 0,
            note=str(cells[6]) if cells[6] else "",
            status=str(cells[7]) if cells[7] else "未开始",
            finish_desc=str(cells[8]) if cells[8] else "",
        )

    @staticmethod
    def task_to_row(task: "Task") -> list:
        return [
            task.id,
            task.title,
            task.content,
            task.create_time,
            task.deadline,
            task.priority,
            task.note,
            task.status,
            task.finish_desc,
        ]


def remaining_time_str(deadline: str) -> str:
    """根据截止时间字符串返回剩余时间描述，如 '3 天 5 小时'。"""
    if not deadline:
        return "无截止时间"
    try:
        dl = datetime.strptime(deadline, TIME_FORMAT)
    except ValueError:
        return ""
    now = datetime.now()
    diff = dl - now
    total_hours = abs(diff.total_seconds()) / 3600
    days = int(total_hours // 24)
    hours = int(total_hours % 24)

    if diff.total_seconds() < 0:
        if days > 0:
            return f"已过期 {days} 天 {hours} 小时"
        return f"已过期 {hours} 小时"
    else:
        if days > 0:
            return f"{days} 天 {hours} 小时"
        if hours > 0:
            return f"{hours} 小时"
        return "即将到期"


def setup_logger(log_file: str = "control.log") -> logging.Logger:
    logger = logging.getLogger("TaskReminder")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "[%(asctime)s] %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(handler)
    return logger
