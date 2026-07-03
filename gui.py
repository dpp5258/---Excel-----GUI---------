"""GUI 界面层 — PyQt6 主窗口与弹窗"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QDialog, QFormLayout, QSpinBox,
    QTextEdit, QLabel, QDialogButtonBox, QApplication, QStatusBar,
    QDateTimeEdit, QCheckBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QDateTime
from PyQt6.QtGui import QColor, QBrush, QFont
import sys

from controller import TaskController
from model import Task, DeadlineStatus, STATUS_COLORS, remaining_time_str


class TaskDialog(QDialog):
    """新增 / 编辑任务弹窗"""

    def __init__(self, parent=None, task: Task = None):
        super().__init__(parent)
        self.task = task
        self._setup_ui()
        if task:
            self._load_task()

    def _setup_ui(self):
        self.setWindowTitle("编辑任务" if self.task else "新增任务")
        self.setMinimumWidth(450)
        layout = QFormLayout(self)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("（必填）")
        layout.addRow("任务标题:", self.title_edit)

        self.content_edit = QTextEdit()
        self.content_edit.setMaximumHeight(80)
        self.content_edit.setPlaceholderText("（选填）")
        layout.addRow("任务内容:", self.content_edit)

        self.create_time_edit = QDateTimeEdit()
        self.create_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.create_time_edit.setCalendarPopup(True)
        self.create_time_edit.setDateTime(QDateTime.currentDateTime())
        layout.addRow("创建时间:", self.create_time_edit)

        deadline_row = QHBoxLayout()
        self.no_deadline_cb = QCheckBox("无截止时间")
        self.no_deadline_cb.toggled.connect(self._on_no_deadline_toggled)
        deadline_row.addWidget(self.no_deadline_cb)
        self.deadline_edit = QDateTimeEdit()
        self.deadline_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.deadline_edit.setCalendarPopup(True)
        self.deadline_edit.setDateTime(QDateTime.currentDateTime())
        self.deadline_edit.dateTimeChanged.connect(self._update_remaining_display)
        deadline_row.addWidget(self.deadline_edit, stretch=1)
        layout.addRow("截止时间:", deadline_row)

        self.remaining_display = QLineEdit()
        self.remaining_display.setReadOnly(True)
        self.remaining_display.setStyleSheet("background-color: #f5f5f5; color: #333;")
        layout.addRow("剩余时间:", self.remaining_display)

        self.priority_spin = QSpinBox()
        self.priority_spin.setRange(0, 100)
        self.priority_spin.setValue(0)
        layout.addRow("优先级 (0-100):", self.priority_spin)

        self.note_edit = QTextEdit()
        self.note_edit.setMaximumHeight(60)
        self.note_edit.setPlaceholderText("（选填）")
        layout.addRow("备注:", self.note_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self._update_remaining_display()

    def _load_task(self):
        self.title_edit.setText(self.task.title)
        self.content_edit.setPlainText(self.task.content)
        if self.task.create_time:
            dt = QDateTime.fromString(self.task.create_time, "yyyy-MM-dd HH:mm")
            if dt.isValid():
                self.create_time_edit.setDateTime(dt)
        if self.task.deadline:
            self.no_deadline_cb.setChecked(False)
            dt = QDateTime.fromString(self.task.deadline, "yyyy-MM-dd HH:mm")
            if dt.isValid():
                self.deadline_edit.setDateTime(dt)
        else:
            self.no_deadline_cb.setChecked(True)
        self.priority_spin.setValue(self.task.priority)
        self.note_edit.setPlainText(self.task.note)

    def _validate_and_accept(self):
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "校验失败", "任务标题不能为空。")
            self.title_edit.setFocus()
            return
        self.accept()

    def _on_no_deadline_toggled(self, checked: bool):
        self.deadline_edit.setEnabled(not checked)
        self._update_remaining_display()

    def _update_remaining_display(self):
        if self.no_deadline_cb.isChecked():
            self.remaining_display.setText("无截止时间")
        else:
            dl_str = self.deadline_edit.dateTime().toString("yyyy-MM-dd HH:mm")
            self.remaining_display.setText(remaining_time_str(dl_str))

    def get_data(self) -> dict:
        deadline = ""
        if not self.no_deadline_cb.isChecked():
            deadline = self.deadline_edit.dateTime().toString("yyyy-MM-dd HH:mm")
        return {
            "title": self.title_edit.text().strip(),
            "content": self.content_edit.toPlainText().strip(),
            "create_time": self.create_time_edit.dateTime().toString("yyyy-MM-dd HH:mm"),
            "deadline": deadline,
            "priority": self.priority_spin.value(),
            "note": self.note_edit.toPlainText().strip(),
        }


class FinishDialog(QDialog):
    """完成确认弹窗"""

    def __init__(self, parent=None, task: Task = None):
        super().__init__(parent)
        self.setWindowTitle("标记任务完成")
        self.setMinimumWidth(400)
        layout = QFormLayout(self)

        info = (
            f"ID: {task.id}      创建时间: {task.create_time}\n"
            f"标题: {task.title}\n"
            f"优先级: {task.priority}"
        )
        layout.addRow("任务概要:", QLabel(info))

        self.desc_edit = QTextEdit()
        self.desc_edit.setMaximumHeight(100)
        self.desc_edit.setPlaceholderText("完成情况描述（选填）")
        layout.addRow("完成情况:", self.desc_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_finish_desc(self) -> str:
        return self.desc_edit.toPlainText().strip()


# ── 主窗口 ──────────────────────────────────────────

_COLUMNS_TODO = ["ID", "", "标题", "优先级", "截止时间", "剩余时间", "状态", "创建时间"]
_COLUMNS_DONE = ["ID", "标题", "优先级", "完成情况", "创建时间"]

# 待办/已完成 列索引（基于各自 _COLUMNS）
class _TodoCol:
    ID, INDICATOR, TITLE, PRIORITY, DEADLINE, REMAINING, STATUS, CREATE_TIME = range(8)

class _DoneCol:
    ID, TITLE, PRIORITY, FINISH_DESC, CREATE_TIME = range(5)


class MainWindow(QMainWindow):
    data_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.controller = TaskController()
        self._setup_ui()
        self._connect_signals()
        self._load_data()

    # ── UI 搭建 ──────────────────────────────────────

    def _setup_ui(self):
        self.setWindowTitle("日常任务提醒系统")
        self.setMinimumSize(900, 600)
        self.resize(1050, 680)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(6)

        # 工具栏
        root.addLayout(self._create_toolbar())

        # 搜索框
        root.addWidget(self._create_search_bar())

        # 选项卡
        self.tabs = QTabWidget()
        self.todo_table = self._create_table(_COLUMNS_TODO)
        self.done_table = self._create_table(_COLUMNS_DONE)
        todo_tab = self._wrap_table_with_actions(
            self.todo_table,
            ["编辑", "删除", "✓ 标记完成"],
            [self._on_edit, self._on_delete, self._on_finish],
        )
        done_tab = self._wrap_table_with_actions(
            self.done_table,
            ["编辑", "删除", "↩ 撤回"],
            [self._on_edit, self._on_delete, self._on_revert],
        )
        self.tabs.addTab(todo_tab, "◉ 待办任务")
        self.tabs.addTab(done_tab, "○ 已完成任务")
        root.addWidget(self.tabs, stretch=1)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def _create_toolbar(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        self.btn_add = QPushButton("＋ 新增任务")
        self.btn_refresh = QPushButton("⟳ 刷新")
        self.btn_archive = QPushButton("📦 清空已完成")
        self.btn_quit = QPushButton("✕ 退出")
        for btn in (self.btn_add, self.btn_refresh, self.btn_archive, self.btn_quit):
            layout.addWidget(btn)
        layout.addStretch()
        return layout

    def _create_search_bar(self) -> QLineEdit:
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 搜索任务标题...")
        self.search_edit.setClearButtonEnabled(True)
        return self.search_edit

    def _create_table(self, columns: list[str]) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(False)
        table.verticalHeader().setVisible(False)
        table.setSortingEnabled(False)

        header = table.horizontalHeader()
        for col, label in enumerate(columns):
            if label == "ID":
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
                table.setColumnWidth(col, 55)
            elif label == "":
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
                table.setColumnWidth(col, 28)
            elif label == "优先级":
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
                table.setColumnWidth(col, 70)
            elif label == "状态":
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
                table.setColumnWidth(col, 70)
            elif label == "截止时间" or label == "创建时间":
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
                table.setColumnWidth(col, 130)
            elif label == "剩余时间":
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
                table.setColumnWidth(col, 140)
            elif label == "标题":
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
            elif label == "完成情况":
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
                table.setColumnWidth(col, 180)

        return table

    def _wrap_table_with_actions(
        self, table: QTableWidget, labels: list[str], handlers: list
    ) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(table, stretch=1)
        bar = QHBoxLayout()
        bar.addStretch()
        for label, handler in zip(labels, handlers):
            btn = QPushButton(label)
            btn.clicked.connect(handler)
            bar.addWidget(btn)
        layout.addLayout(bar)
        return wrapper

    # ── 信号连接 ──────────────────────────────────────

    def _connect_signals(self):
        self.btn_add.clicked.connect(self._on_add)
        self.btn_refresh.clicked.connect(self._on_refresh)
        self.btn_archive.clicked.connect(self._on_archive)
        self.btn_quit.clicked.connect(self.close)
        self.search_edit.textChanged.connect(self._on_search)
        self.todo_table.doubleClicked.connect(lambda idx: self._on_edit())
        self.done_table.doubleClicked.connect(lambda idx: self._on_edit())

    # ── 数据渲染 ──────────────────────────────────────

    def _load_data(self):
        try:
            self.controller.load_all_tasks()
        except Exception as e:
            QMessageBox.critical(self, "加载失败", f"读取 Excel 失败:\n{e}")
        self._render_all()

    def _render_all(self):
        self._render_todo()
        self._render_done()
        self._update_status_bar()

    def _render_todo(self, tasks: list[Task] = None):
        if tasks is None:
            tasks = self.controller.get_sorted_todo()
        table = self.todo_table
        table.setRowCount(len(tasks))
        for row, task in enumerate(tasks):
            self._set_row(table, row, [
                str(task.id),
                "",
                task.title,
                str(task.priority),
                task.deadline,
                remaining_time_str(task.deadline),
                task.status,
                task.create_time,
            ], title_col=2)
            self._set_indicator_color(table, row, task)

    def _render_done(self, tasks: list[Task] = None):
        if tasks is None:
            tasks = self.controller.get_sorted_done()
        table = self.done_table
        table.setRowCount(len(tasks))
        for row, task in enumerate(tasks):
            self._set_row(table, row, [
                str(task.id),
                task.title,
                str(task.priority),
                task.finish_desc,
                task.create_time,
            ])

    def _set_row(self, table: QTableWidget, row: int, values: list[str], title_col: int = 1):
        for col, val in enumerate(values):
            item = QTableWidgetItem(val)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter if col != title_col else
                                  Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            table.setItem(row, col, item)

    def _set_indicator_color(self, table: QTableWidget, row: int, task: Task):
        status = task.deadline_status()
        if status not in STATUS_COLORS:
            return
        color = QColor(STATUS_COLORS[status])
        item = table.item(row, _TodoCol.INDICATOR)
        if item:
            item.setBackground(QBrush(color))

    def _update_status_bar(self):
        todo_count = len(self.controller.todo_tasks)
        done_count = len(self.controller.done_tasks)
        archive_count = len(self.controller.archive_tasks)
        self.status_bar.showMessage(
            f"待办: {todo_count}    已完成: {done_count}    归档: {archive_count}"
        )

    # ── 事件处理 ──────────────────────────────────────

    def _on_add(self):
        dlg = TaskDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            task = self.controller.create_task(**dlg.get_data())
            self._render_all()
            self._select_task(self.todo_table, task.id)
            self.status_bar.showMessage(f"已新增任务: {task.title}", 3000)
        except (ValueError, PermissionError) as e:
            QMessageBox.warning(self, "操作失败", str(e))

    def _on_edit(self):
        task_id = self._selected_task_id()
        if task_id is None:
            QMessageBox.information(self, "提示", "请先选择一条任务。")
            return
        task = self.controller.get_task(task_id)
        if task is None:
            return
        dlg = TaskDialog(self, task)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.controller.update_task(task_id, **dlg.get_data())
            self._render_all()
            self._select_current_tab_row(task_id)
            self.status_bar.showMessage(f"已更新任务: {task.title}", 3000)
        except (ValueError, PermissionError) as e:
            QMessageBox.warning(self, "操作失败", str(e))

    def _on_delete(self):
        task_id = self._selected_task_id()
        if task_id is None:
            QMessageBox.information(self, "提示", "请先选择一条任务。")
            return
        task = self.controller.get_task(task_id)
        if task is None:
            return
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定删除任务「{task.title}」？\n此操作不可恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.controller.delete_task(task_id)
            self._render_all()
            self.status_bar.showMessage(f"已删除任务: {task.title}", 3000)
        except (KeyError, PermissionError) as e:
            QMessageBox.warning(self, "操作失败", str(e))

    def _on_finish(self):
        task_id = self._selected_task_id()
        if task_id is None:
            QMessageBox.information(self, "提示", "请先选择一条待办任务。")
            return
        task = self.controller.get_task(task_id)
        if task is None or task.id not in self.controller.todo_tasks:
            QMessageBox.information(self, "提示", "请选择待办任务。")
            return
        dlg = FinishDialog(self, task)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.controller.finish_task(task_id, dlg.get_finish_desc())
            self._render_all()
            self.status_bar.showMessage(f"已完成任务: {task.title}", 3000)
        except (KeyError, PermissionError) as e:
            QMessageBox.warning(self, "操作失败", str(e))

    def _on_revert(self):
        task_id = self._selected_task_id()
        if task_id is None:
            QMessageBox.information(self, "提示", "请先选择一条已完成任务。")
            return
        task = self.controller.get_task(task_id)
        if task is None or task.id not in self.controller.done_tasks:
            QMessageBox.information(self, "提示", "请选择已完成任务。")
            return
        try:
            self.controller.revert_task(task_id)
            self._render_all()
            self.status_bar.showMessage(f"已撤回任务: {task.title}", 3000)
        except (KeyError, PermissionError) as e:
            QMessageBox.warning(self, "操作失败", str(e))

    def _on_refresh(self):
        try:
            self.controller.refresh()
            self._render_all()
            self.status_bar.showMessage("已刷新", 3000)
        except PermissionError as e:
            QMessageBox.warning(self, "刷新失败", str(e))

    def _on_archive(self):
        count = len(self.controller.done_tasks)
        if count == 0:
            QMessageBox.information(self, "提示", "没有需要归档的已完成任务。")
            return
        reply = QMessageBox.question(
            self, "确认归档",
            f"将 {count} 条已完成任务归档到归档表？\n数据可从 Excel 的「归档任务」Sheet 中找回。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            archived = self.controller.archive_all_done()
            self._render_all()
            self.status_bar.showMessage(f"已归档 {archived} 条任务", 3000)
        except PermissionError as e:
            QMessageBox.warning(self, "操作失败", str(e))

    def _on_search(self, text: str):
        todo_tasks, done_tasks = self.controller.search(text)
        self._render_todo(todo_tasks)
        self._render_done(done_tasks)
        self._update_status_bar()

    # ── 辅助 ──────────────────────────────────────────

    def _selected_task_id(self) -> int | None:
        current_tab = self.tabs.currentIndex()
        table = self.todo_table if current_tab == 0 else self.done_table
        rows = table.selectionModel().selectedRows()
        if not rows:
            return None
        item = table.item(rows[0].row(), 0)
        return int(item.text()) if item else None

    def _select_task(self, table: QTableWidget, task_id: int):
        for row in range(table.rowCount()):
            item = table.item(row, 0)
            if item and item.text() == str(task_id):
                table.selectRow(row)
                return

    def _select_current_tab_row(self, task_id: int):
        current_tab = self.tabs.currentIndex()
        table = self.todo_table if current_tab == 0 else self.done_table
        self._select_task(table, task_id)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
