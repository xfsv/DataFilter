#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据筛选工具
- 浏览 episode 文件夹下的图片（A/D 键切换）
- 为每个 episode 打标签
- 保存 flag.json 或删除整个 episode 文件夹
"""

import sys
import json
import shutil
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QScrollArea, QCheckBox,
    QGroupBox, QComboBox, QFrame, QSplitter, QMessageBox,
    QFileDialog, QSizePolicy, QLineEdit, QRadioButton, QButtonGroup,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

# ──────────────────────────────────────────────────────────────────────────────
#  标签结构定义
#  None / []  → 该 key 本身作为单个复选框
#  list(非空) → 该 key 下展开多个复选框
#  dict       → 递归子分组
# ──────────────────────────────────────────────────────────────────────────────
TAG_STRUCTURE: dict = {
    "物体": {
        "刚性物体": {
            "水果(fruit)": ["无", "苹果", "梨子", "香蕉", "杨桃", "黄瓜", "柿子"],
            "方块(cube)":  ["无", "魔方", "积木", "充电器"],
            "工具(tool)":  ["无", "锤子", "钳子"],
            "可抓取容器":  ["无", "马克杯", "可乐瓶", "易拉罐"],
        },
        "柔性物体": {
            "布(fabric)":     ["无", "抹布", "毛巾"],
            "衣物(clothing)": ["无", "衬衫", "T恤", "裤子"],
            "清洁工具":       ["无", "海绵"],
        },
    },
    "容器": {
        "刚性容器": {
            "承载刚体的容器": {
                "三维容器": ["无", "菜篮子", "收纳盒", "三层置物架"],
                "二维容器": ["无", "盘子", "砧板", "杯垫"],
            },
            "承载液体的容器": ["无", "马克杯", "塑料瓶"],
        },
        "柔性容器": {
            "布料容器": ["无", "帆布袋"],
            "塑料容器": ["无", "塑料袋"],
        },
    },
    "背景": {
        "光照": {
            "强度": ["无", "早全灯", "晚全灯", "早半灯", "晚半灯"],
            "颜色": ["无", "暖色", "冷色"],
        },
        "桌面材质": ["木头材质", "金属材质", "塑料材质"],
        "背景物体": {
            "二维物体": ["无", "砧板", "桌垫", "杯垫"],
            "三维物体": ["无", "三层置物架", "菜篮子"],
            "零散物体": ["无", "水果", "工具", "方块"],
        },
    },
}


class DataFilterApp(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.base_folder: Path | None = None
        self.episodes:    list[Path] = []
        self.current_episode_idx: int = 0
        self.images:      list[Path] = []
        self.current_image_idx: int = 0
        self.checkboxes:        dict[str, QCheckBox] = {}
        self.task_radios:       dict[str, QRadioButton] = {}
        self.task_group:        QButtonGroup | None = None
        self.obj_pos_edit:      QLineEdit | None = None
        self.cont_pos_radios:   dict[str, QRadioButton] = {}
        self.cont_pos_group:    QButtonGroup | None = None
        self.hand_radios:       dict[str, QRadioButton] = {}
        self.hand_group:        QButtonGroup | None = None
        self.rating_radios:     dict[str, QRadioButton] = {}
        self.rating_group:      QButtonGroup | None = None

        self.setWindowTitle("数据筛选工具")
        self.resize(1520, 900)

        self._init_ui()
        self._connect_signals()
        self.setStyleSheet(_STYLESHEET)

    # ─────────────────────────── UI 构建 ─────────────────────────────────────

    def _init_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        layout.addWidget(self._build_top_bar())

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.image_label = QLabel("请点击「选择文件夹」开始")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setObjectName("imageLabel")
        self.image_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        # 必须设置，否则 setPixmap 后 sizeHint 会返回图片尺寸，
        # 导致布局不断扩大窗口并触发 resizeEvent，形成反馈循环
        self.image_label.setMinimumSize(1, 1)
        splitter.addWidget(self.image_label)
        splitter.addWidget(self._build_tags_panel())
        splitter.setSizes([960, 500])

        layout.addWidget(splitter, stretch=1)
        layout.addWidget(self._build_bottom_bar())

    def _build_top_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("topBar")
        h = QHBoxLayout(bar)
        h.setContentsMargins(12, 8, 12, 8)
        h.setSpacing(10)

        self.open_btn = QPushButton("📂  选择文件夹")
        self.open_btn.setObjectName("openBtn")
        self.open_btn.setFixedHeight(36)
        h.addWidget(self.open_btn)

        h.addSpacing(16)
        h.addWidget(QLabel("Episode："))
        self.episode_combo = QComboBox()
        self.episode_combo.setMinimumWidth(200)
        self.episode_combo.setFixedHeight(36)
        h.addWidget(self.episode_combo)

        h.addSpacing(16)
        self.prev_btn = QPushButton("◀  上一张  (A)")
        self.prev_btn.setFixedHeight(36)
        h.addWidget(self.prev_btn)

        self.counter_lbl = QLabel("—  /  —")
        self.counter_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.counter_lbl.setMinimumWidth(80)
        h.addWidget(self.counter_lbl)

        self.next_btn = QPushButton("下一张  (D)  ▶")
        self.next_btn.setFixedHeight(36)
        h.addWidget(self.next_btn)

        h.addStretch()

        # ── 人员信息 ──────────────────────────────────
        h.addWidget(QLabel("采集员："))
        self.collector_edit = QLineEdit()
        self.collector_edit.setPlaceholderText("请输入采集员姓名")
        self.collector_edit.setFixedHeight(32)
        self.collector_edit.setMinimumWidth(120)
        self.collector_edit.setObjectName("nameEdit")
        h.addWidget(self.collector_edit)

        h.addSpacing(12)

        h.addWidget(QLabel("筛选员："))
        self.screener_edit = QLineEdit()
        self.screener_edit.setPlaceholderText("请输入筛选员姓名")
        self.screener_edit.setFixedHeight(32)
        self.screener_edit.setMinimumWidth(120)
        self.screener_edit.setObjectName("nameEdit")
        h.addWidget(self.screener_edit)

        h.addSpacing(16)
        # ─────────────────────────────────────────────

        self.status_lbl = QLabel("")
        h.addWidget(self.status_lbl)

        return bar

    def _build_tags_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("tagsPanel")
        panel.setMinimumWidth(430)
        v = QVBoxLayout(panel)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        title = QLabel("  标签面板")
        title.setObjectName("panelTitle")
        title.setFixedHeight(38)
        v.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content.setObjectName("scrollContent")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(10, 10, 10, 10)
        cl.setSpacing(10)

        cl.addWidget(self._build_task_section())
        cl.addWidget(self._build_position_section())
        cl.addWidget(self._build_hand_section())
        cl.addWidget(self._build_rating_section())

        for sec_name, sec_data in TAG_STRUCTURE.items():
            cl.addWidget(self._build_group(sec_name, sec_data, prefix="", level=0))

        cl.addStretch()
        scroll.setWidget(content)
        v.addWidget(scroll)
        return panel

    def _build_task_section(self) -> QGroupBox:
        """构建互斥的任务选择分组（单选）。"""
        group = QGroupBox("任务")
        group.setObjectName("group0")
        gl = QVBoxLayout(group)
        gl.setSpacing(4)
        gl.setContentsMargins(8, 14, 8, 10)

        self.task_group = QButtonGroup(self)
        self.task_group.setExclusive(True)

        # ── 抓放任务（含两个子类型） ──────────────────
        grab_lbl = QLabel("抓放任务：")
        grab_lbl.setObjectName("subLabel")
        gl.addWidget(grab_lbl)

        grab_row = QWidget()
        grab_layout = QHBoxLayout(grab_row)
        grab_layout.setContentsMargins(16, 0, 0, 0)
        grab_layout.setSpacing(16)
        for name in ("简单抓放任务", "分类任务"):
            rb = QRadioButton(name)
            self.task_radios[name] = rb
            self.task_group.addButton(rb)
            grab_layout.addWidget(rb)
        grab_layout.addStretch()
        gl.addWidget(grab_row)

        # ── 分隔线 ────────────────────────────────────
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setObjectName("taskSeparator")
        gl.addWidget(line)

        # ── 擦拭任务（独立类别） ──────────────────────
        wipe_lbl = QLabel("擦拭任务：")
        wipe_lbl.setObjectName("subLabel")
        gl.addWidget(wipe_lbl)

        wipe_rb = QRadioButton("擦拭任务")
        self.task_radios["擦拭任务"] = wipe_rb
        self.task_group.addButton(wipe_rb)
        wipe_row = QWidget()
        wipe_layout = QHBoxLayout(wipe_row)
        wipe_layout.setContentsMargins(16, 0, 0, 0)
        wipe_layout.addWidget(wipe_rb)
        wipe_layout.addStretch()
        gl.addWidget(wipe_row)

        # ── 分隔线 ────────────────────────────────────
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setObjectName("taskSeparator")
        gl.addWidget(line2)

        # ── 锤击任务（独立类别） ──────────────────────
        hammer_lbl = QLabel("锤击任务：")
        hammer_lbl.setObjectName("subLabel")
        gl.addWidget(hammer_lbl)

        hammer_rb = QRadioButton("锤击任务")
        self.task_radios["锤击任务"] = hammer_rb
        self.task_group.addButton(hammer_rb)
        hammer_row = QWidget()
        hammer_layout = QHBoxLayout(hammer_row)
        hammer_layout.setContentsMargins(16, 0, 0, 0)
        hammer_layout.addWidget(hammer_rb)
        hammer_layout.addStretch()
        gl.addWidget(hammer_row)

        return group

    def _build_group(self, name: str, data: dict, prefix: str, level: int) -> QGroupBox:
        """递归构建标签分组，支持任意嵌套深度。"""
        group = QGroupBox(name)
        group.setObjectName(f"group{min(level, 2)}")
        gl = QVBoxLayout(group)
        gl.setSpacing(4)
        gl.setContentsMargins(8, 14, 8, 8)

        full_prefix = f"{prefix}|{name}" if prefix else name

        for key, value in data.items():
            key_path = f"{full_prefix}|{key}"

            if value is None or value == []:
                cb = QCheckBox(key)
                self.checkboxes[key_path] = cb
                gl.addWidget(cb)

            elif isinstance(value, list):
                gl.addWidget(self._build_checkbox_grid(key, value, full_prefix))

            elif isinstance(value, dict):
                gl.addWidget(self._build_group(key, value, full_prefix, level + 1))

        return group

    def _build_checkbox_grid(self, key: str, items: list[str], prefix: str) -> QFrame:
        """构建带标题的复选框网格（每行 3 列）。"""
        frame = QFrame()
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(0, 2, 0, 4)
        fl.setSpacing(2)

        lbl = QLabel(f"{key}：")
        lbl.setObjectName("subLabel")
        fl.addWidget(lbl)

        grid_w = QWidget()
        grid = QGridLayout(grid_w)
        grid.setContentsMargins(16, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(2)

        cols = 3
        for i, item in enumerate(items):
            cb = QCheckBox(item)
            cb_key = f"{prefix}|{key}|{item}"
            self.checkboxes[cb_key] = cb
            grid.addWidget(cb, i // cols, i % cols)

        fl.addWidget(grid_w)
        return frame

    def _build_position_section(self) -> QGroupBox:
        """4.5 位置标签：物体位置（文本输入）+ 容器位置（1~4 单选）。"""
        group = QGroupBox("位置标签")
        group.setObjectName("group0")
        gl = QVBoxLayout(group)
        gl.setSpacing(4)
        gl.setContentsMargins(8, 14, 8, 10)

        # ── 物体位置：自由输入 ────────────────────────
        obj_lbl = QLabel("物体位置：")
        obj_lbl.setObjectName("subLabel")
        gl.addWidget(obj_lbl)

        obj_row = QWidget()
        obj_row_layout = QHBoxLayout(obj_row)
        obj_row_layout.setContentsMargins(16, 0, 0, 0)
        self.obj_pos_edit = QLineEdit()
        self.obj_pos_edit.setPlaceholderText("请输入物体位置描述")
        self.obj_pos_edit.setFixedHeight(32)
        self.obj_pos_edit.setObjectName("nameEdit")
        obj_row_layout.addWidget(self.obj_pos_edit)
        gl.addWidget(obj_row)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setObjectName("taskSeparator")
        gl.addWidget(line)

        # ── 容器位置：1 / 2 / 3 / 4 单选 ────────────
        cont_lbl = QLabel("容器位置：")
        cont_lbl.setObjectName("subLabel")
        gl.addWidget(cont_lbl)

        self.cont_pos_group = QButtonGroup(self)
        self.cont_pos_group.setExclusive(True)
        cont_row = QWidget()
        cont_row_layout = QHBoxLayout(cont_row)
        cont_row_layout.setContentsMargins(16, 0, 0, 0)
        cont_row_layout.setSpacing(16)
        for opt in ("A", "B", "C", "D"):
            rb = QRadioButton(opt)
            self.cont_pos_radios[opt] = rb
            self.cont_pos_group.addButton(rb)
            cont_row_layout.addWidget(rb)
        cont_row_layout.addStretch()
        gl.addWidget(cont_row)

        return group

    def _build_hand_section(self) -> QGroupBox:
        """4.6 抓取手标签：左 / 右（互斥）。"""
        group = QGroupBox("抓取手标签")
        group.setObjectName("group0")
        gl = QVBoxLayout(group)
        gl.setSpacing(4)
        gl.setContentsMargins(8, 14, 8, 10)

        lbl = QLabel("使用的抓取手：")
        lbl.setObjectName("subLabel")
        gl.addWidget(lbl)

        self.hand_group = QButtonGroup(self)
        self.hand_group.setExclusive(True)
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(16, 0, 0, 0)
        row_layout.setSpacing(16)
        for opt in ("左", "右"):
            rb = QRadioButton(opt)
            self.hand_radios[opt] = rb
            self.hand_group.addButton(rb)
            row_layout.addWidget(rb)
        row_layout.addStretch()
        gl.addWidget(row)

        return group

    def _build_rating_section(self) -> QGroupBox:
        """episode 综合评价：优 / 良 / 平（互斥单选）。"""
        group = QGroupBox("评价")
        group.setObjectName("group0")
        gl = QVBoxLayout(group)
        gl.setSpacing(4)
        gl.setContentsMargins(8, 14, 8, 10)

        lbl = QLabel("综合评价：")
        lbl.setObjectName("subLabel")
        gl.addWidget(lbl)

        self.rating_group = QButtonGroup(self)
        self.rating_group.setExclusive(True)
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(16, 0, 0, 0)
        row_layout.setSpacing(24)
        for opt in ("优", "良", "平"):
            rb = QRadioButton(opt)
            rb.setObjectName(f"rating_{opt}")
            self.rating_radios[opt] = rb
            self.rating_group.addButton(rb)
            row_layout.addWidget(rb)
        row_layout.addStretch()
        gl.addWidget(row)
        return group

    def _build_bottom_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("bottomBar")
        v = QVBoxLayout(bar)
        v.setContentsMargins(12, 8, 12, 8)
        v.setSpacing(6)

        # ── 未填提示条 ────────────────────────────────
        self.unfilled_lbl = QLabel("")
        self.unfilled_lbl.setObjectName("unfilledLbl")
        self.unfilled_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.unfilled_lbl.setFixedHeight(22)
        v.addWidget(self.unfilled_lbl)

        # ── 按钮行 ────────────────────────────────────
        btn_row = QWidget()
        h = QHBoxLayout(btn_row)
        h.setContentsMargins(0, 0, 0, 0)

        self.save_btn = QPushButton("💾   保存标签  ( Space )")
        self.save_btn.setObjectName("saveBtn")
        self.save_btn.setFixedHeight(46)
        self.save_btn.setMinimumWidth(260)

        self.prev_episode_btn = QPushButton("⏮   上一个 Episode")
        self.prev_episode_btn.setObjectName("prevEpisodeBtn")
        self.prev_episode_btn.setFixedHeight(46)
        self.prev_episode_btn.setMinimumWidth(180)

        self.next_episode_btn = QPushButton("⏭   下一个 Episode")
        self.next_episode_btn.setObjectName("nextEpisodeBtn")
        self.next_episode_btn.setFixedHeight(46)
        self.next_episode_btn.setMinimumWidth(180)

        self.delete_btn = QPushButton("🗑   删除轨迹  ( Q )")
        self.delete_btn.setObjectName("deleteBtn")
        self.delete_btn.setFixedHeight(46)
        self.delete_btn.setMinimumWidth(160)

        h.addStretch()
        h.addWidget(self.save_btn)
        h.addSpacing(32)
        h.addWidget(self.prev_episode_btn)
        h.addSpacing(8)
        h.addWidget(self.next_episode_btn)
        h.addSpacing(32)
        h.addWidget(self.delete_btn)
        h.addStretch()
        v.addWidget(btn_row)
        return bar

    # ─────────────────────────── 信号连接 ─────────────────────────────────────

    def _connect_signals(self) -> None:
        self.open_btn.clicked.connect(self._select_folder)
        self.episode_combo.currentIndexChanged.connect(self._on_episode_changed)
        self.prev_btn.clicked.connect(self._prev_image)
        self.next_btn.clicked.connect(self._next_image)
        self.save_btn.clicked.connect(self._save_tags)
        self.prev_episode_btn.clicked.connect(self._prev_episode)
        self.next_episode_btn.clicked.connect(self._next_episode)
        self.delete_btn.clicked.connect(self._delete_episode)

        # 任意关键单选变化时刷新未填提示
        for rb in (*self.task_radios.values(),
                   *self.hand_radios.values(),
                   *self.rating_radios.values()):
            rb.toggled.connect(lambda _: self._update_unfilled_warning())

    # ─────────────────────────── 键盘事件 ─────────────────────────────────────

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_A:
            self._prev_image()
        elif event.key() == Qt.Key.Key_D:
            self._next_image()
        elif event.key() == Qt.Key.Key_Space:
            self._save_tags()
        elif event.key() == Qt.Key.Key_Q:
            self._delete_episode()
        else:
            super().keyPressEvent(event)

    # ─────────────────────────── 数据加载 ─────────────────────────────────────

    def _select_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择数据根目录")
        if folder:
            self.base_folder = Path(folder)
            self._load_episodes()

    def _load_episodes(self) -> None:
        self.episodes = sorted(
            d for d in self.base_folder.iterdir()
            if d.is_dir() and d.name.startswith("episode_")
        )
        self.episode_combo.blockSignals(True)
        self.episode_combo.clear()
        for ep in self.episodes:
            self.episode_combo.addItem(ep.name)
        self.episode_combo.setCurrentIndex(0)
        self.episode_combo.blockSignals(False)

        if self.episodes:
            self.current_episode_idx = 0
            self._clear_checkboxes()   # 新文件夹：先清空再加载第一个
            self._load_episode(0)
        else:
            self._set_status("未找到任何 episode 文件夹", "error")

    def _load_episode(self, idx: int) -> None:
        if idx < 0 or idx >= len(self.episodes):
            return
        self.current_episode_idx = idx
        ep_path = self.episodes[idx]

        colors_path = ep_path / "colors"
        self.images = (
            sorted(colors_path.glob("*.jpg")) if colors_path.exists() else []
        )
        self.current_image_idx = 0

        flag_exists = (ep_path / "flag.json").exists()
        if flag_exists:
            # 已有保存记录：清空后加载文件中的选项
            self._clear_checkboxes()
            self._load_existing_flag(ep_path)
        # 无记录：保留上一 episode 的选项作为默认起点，不清空也不写入

        self._refresh_image()
        self._update_unfilled_warning()
        self._set_status(f"已加载 {ep_path.name}  —  共 {len(self.images)} 张图片")

    def _clear_checkboxes(self) -> None:
        for cb in self.checkboxes.values():
            cb.setChecked(False)
        if self.obj_pos_edit:
            self.obj_pos_edit.clear()
        for grp, radios in (
            (self.task_group,     self.task_radios),
            (self.cont_pos_group, self.cont_pos_radios),
            (self.hand_group,     self.hand_radios),
            (self.rating_group,   self.rating_radios),
        ):
            if grp:
                grp.setExclusive(False)
                for rb in radios.values():
                    rb.setChecked(False)
                grp.setExclusive(True)

    # 保存时写入、读取时需排除的非标签元数据字段
    _META_KEYS = {"episode", "采集员", "筛选员", "任务", "物体位置", "容器位置", "抓取手", "评价"}

    def _load_existing_flag(self, ep_path: Path) -> None:
        flag = ep_path / "flag.json"
        if not flag.exists():
            return
        try:
            with open(flag, encoding="utf-8") as f:
                data = json.load(f)

            # 回填人员姓名（采集员随 episode 切换；筛选员若已填则不覆盖）
            if "采集员" in data:
                self.collector_edit.setText(data["采集员"])
            if "筛选员" in data and not self.screener_edit.text().strip():
                self.screener_edit.setText(data["筛选员"])

            # 回填任务选项
            task = data.get("任务", "")
            if task in self.task_radios:
                self.task_radios[task].setChecked(True)

            # 回填位置 / 抓取手
            if "物体位置" in data and self.obj_pos_edit:
                self.obj_pos_edit.setText(data["物体位置"])
            for field, radios in (
                ("容器位置", self.cont_pos_radios),
                ("抓取手",   self.hand_radios),
                ("评价",     self.rating_radios),
            ):
                val = data.get(field, "")
                if val in radios:
                    radios[val].setChecked(True)

            # 解析标签
            if "selected_tags" in data:
                flat_keys = data["selected_tags"]
            else:
                flat_keys = self._flatten_tag_dict(
                    {k: v for k, v in data.items() if k not in self._META_KEYS}
                )

            for key in flat_keys:
                if key in self.checkboxes:
                    self.checkboxes[key].setChecked(True)
        except Exception as exc:
            self._set_status(f"读取 flag.json 失败：{exc}", "error")

    def _flatten_tag_dict(self, data: dict, prefix: str = "") -> list[str]:
        """将嵌套的标签结构展平为 checkbox key 列表，用于回填复选框。"""
        keys: list[str] = []
        for key, value in data.items():
            full_key = f"{prefix}|{key}" if prefix else key
            if value is True:
                keys.append(full_key)
            elif isinstance(value, list):
                for item in value:
                    keys.append(f"{full_key}|{item}")
            elif isinstance(value, dict):
                keys.extend(self._flatten_tag_dict(value, full_key))
        return keys

    def _build_structured_tags(self) -> dict:
        """将当前勾选状态还原为与 TAG_STRUCTURE 同层次的嵌套字典。"""
        selected = {k for k, cb in self.checkboxes.items() if cb.isChecked()}

        def walk(data: dict, prefix: str) -> dict:
            result: dict = {}
            for key, value in data.items():
                key_path = f"{prefix}|{key}" if prefix else key
                if value is None or value == []:
                    if key_path in selected:
                        result[key] = True
                elif isinstance(value, list):
                    items = [item for item in value if f"{key_path}|{item}" in selected]
                    if items:
                        result[key] = items
                elif isinstance(value, dict):
                    sub = walk(value, key_path)
                    if sub:
                        result[key] = sub
            return result

        return walk(TAG_STRUCTURE, "")

    # ─────────────────────────── 图片导航 ─────────────────────────────────────

    def _refresh_image(self) -> None:
        if not self.images:
            self.image_label.setText("该 episode 无图片")
            self.counter_lbl.setText("0  /  0")
            return

        total = len(self.images)
        idx   = self.current_image_idx
        self.counter_lbl.setText(f"{idx + 1}  /  {total}")

        pix = QPixmap(str(self.images[idx]))
        if pix.isNull():
            self.image_label.setText("无法加载图片")
            return

        scaled = pix.scaled(
            self.image_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)

    def _prev_image(self) -> None:
        if self.images:
            self.current_image_idx = (self.current_image_idx - 1) % len(self.images)
            self._refresh_image()

    def _next_image(self) -> None:
        if self.images:
            self.current_image_idx = (self.current_image_idx + 1) % len(self.images)
            self._refresh_image()

    def _on_episode_changed(self, idx: int) -> None:
        if idx >= 0:
            self._load_episode(idx)

    # ─────────────────────────── 保存 / 删除 ──────────────────────────────────

    def _save_tags(self) -> None:
        if not self.episodes:
            self._set_status("请先选择文件夹", "error")
            return

        ep_path = self.episodes[self.current_episode_idx]

        def _checked(radios: dict) -> str:
            return next((n for n, rb in radios.items() if rb.isChecked()), "")

        payload = {
            "episode":  ep_path.name,
            "采集员":   self.collector_edit.text().strip(),
            "筛选员":   self.screener_edit.text().strip(),
            "任务":     _checked(self.task_radios),
            "物体位置": self.obj_pos_edit.text().strip() if self.obj_pos_edit else "",
            "容器位置": _checked(self.cont_pos_radios),
            "抓取手":   _checked(self.hand_radios),
            "评价":     _checked(self.rating_radios),
            **self._build_structured_tags(),
        }

        flag_path = ep_path / "flag.json"
        try:
            with open(flag_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            self._set_status(f"✓ 已保存  →  {flag_path}", "success")
            self._next_episode()
        except Exception as exc:
            self._set_status(f"保存失败：{exc}", "error")

    def _delete_episode(self) -> None:
        if not self.episodes:
            return
        ep_path = self.episodes[self.current_episode_idx]
        reply = QMessageBox.warning(
            self,
            "确认删除",
            f"即将永久删除：\n\n  {ep_path}\n\n此操作不可撤销，是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            deleted_idx = self.current_episode_idx
            shutil.rmtree(ep_path)
            self._set_status(f"已删除 {ep_path.name}", "success")

            # 重新扫描目录，然后定位到下一个 episode
            self.episodes = sorted(
                d for d in self.base_folder.iterdir()
                if d.is_dir() and d.name.startswith("episode_")
            )
            self.episode_combo.blockSignals(True)
            self.episode_combo.clear()
            for ep in self.episodes:
                self.episode_combo.addItem(ep.name)
            self.episode_combo.blockSignals(False)

            if not self.episodes:
                self.images = []
                self.image_label.setText("已无 episode 文件夹")
                self.counter_lbl.setText("—  /  —")
                return

            # 尽量停留在同一位置（原来的下一个），超出时退到末尾
            next_idx = min(deleted_idx, len(self.episodes) - 1)
            self.episode_combo.blockSignals(True)
            self.episode_combo.setCurrentIndex(next_idx)
            self.episode_combo.blockSignals(False)
            self._load_episode(next_idx)

        except Exception as exc:
            self._set_status(f"删除失败：{exc}", "error")

    def _prev_episode(self) -> None:
        if not self.episodes:
            return
        prev_idx = self.current_episode_idx - 1
        if prev_idx < 0:
            self._set_status("已是第一个 Episode", "error")
            return
        self.episode_combo.setCurrentIndex(prev_idx)

    def _next_episode(self) -> None:
        if not self.episodes:
            return
        next_idx = self.current_episode_idx + 1
        if next_idx >= len(self.episodes):
            self._set_status("已是最后一个 Episode", "error")
            return
        self.episode_combo.setCurrentIndex(next_idx)

    # ─────────────────────────── 工具方法 ─────────────────────────────────────

    def _update_unfilled_warning(self) -> None:
        """检查关键单选项是否已填，未填则在底部提示条显示。"""
        missing = []
        if not any(rb.isChecked() for rb in self.task_radios.values()):
            missing.append("任务")
        if not any(rb.isChecked() for rb in self.hand_radios.values()):
            missing.append("抓取手")
        if not any(rb.isChecked() for rb in self.rating_radios.values()):
            missing.append("评价")

        if missing:
            self.unfilled_lbl.setText(f"⚠  尚未填写：{'  ·  '.join(missing)}")
            self.unfilled_lbl.setVisible(True)
        else:
            self.unfilled_lbl.setVisible(False)

    def _set_status(self, msg: str, level: str = "info") -> None:
        color = {
            "info":    "#9aafc8",
            "success": "#4ade80",
            "error":   "#f87171",
        }.get(level, "#9aafc8")
        self.status_lbl.setStyleSheet(f"color: {color}; font-size: 12px;")
        self.status_lbl.setText(msg)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._refresh_image()


# ──────────────────────────────────────────────────────────────────────────────
#  全局样式表
# ──────────────────────────────────────────────────────────────────────────────
_STYLESHEET = """
* {
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
    font-size: 13px;
}
QMainWindow, QWidget {
    background-color: #111827;
    color: #d1d5db;
}
QFrame#topBar, QFrame#bottomBar {
    background: #1f2937;
    border-radius: 8px;
}
QFrame#tagsPanel {
    background: #1f2937;
    border-radius: 8px;
}
QWidget#scrollContent {
    background: transparent;
}
QLabel#imageLabel {
    background: #0d1117;
    color: #6b7280;
    font-size: 16px;
    border-radius: 10px;
    border: 1px solid #1f2937;
}
QLabel#panelTitle {
    background: #374151;
    color: #93c5fd;
    font-size: 15px;
    font-weight: bold;
    padding-left: 10px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}
QPushButton {
    background: #374151;
    color: #93c5fd;
    border: 1px solid #4b5563;
    border-radius: 6px;
    padding: 6px 14px;
}
QPushButton:hover  { background: #4b5563; }
QPushButton:pressed { background: #1f2937; }
QPushButton#openBtn {
    background: #1e3a5f;
    color: #bfdbfe;
    font-weight: bold;
    border-color: #2d5080;
}
QPushButton#saveBtn {
    background: #064e3b;
    color: #6ee7b7;
    border-color: #065f46;
    font-weight: bold;
    font-size: 14px;
}
QPushButton#saveBtn:hover { background: #065f46; }
QPushButton#deleteBtn {
    background: #450a0a;
    color: #fca5a5;
    border-color: #7f1d1d;
    font-weight: bold;
    font-size: 14px;
}
QPushButton#deleteBtn:hover { background: #7f1d1d; }
QPushButton#prevEpisodeBtn,
QPushButton#nextEpisodeBtn {
    background: #1c3a4a;
    color: #7dd3fc;
    border-color: #2a5470;
    font-weight: bold;
    font-size: 14px;
}
QPushButton#prevEpisodeBtn:hover,
QPushButton#nextEpisodeBtn:hover { background: #2a5470; }
QComboBox {
    background: #374151;
    color: #d1d5db;
    border: 1px solid #4b5563;
    border-radius: 6px;
    padding: 4px 8px;
}
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background: #374151;
    color: #d1d5db;
    selection-background-color: #4b5563;
    border: 1px solid #4b5563;
    outline: none;
}
QGroupBox#group0 {
    border: 1px solid #3b5280;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 6px;
    color: #93c5fd;
    font-weight: bold;
}
QGroupBox#group1 {
    border: 1px solid #2d3f60;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 6px;
    color: #a5b4fc;
    font-weight: bold;
}
QGroupBox#group2 {
    border: 1px solid #252e40;
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 4px;
    color: #c4b5fd;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 6px;
}
QRadioButton {
    color: #d1d5db;
    spacing: 5px;
}
QRadioButton::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #4b5563;
    border-radius: 7px;
    background: #111827;
}
QRadioButton::indicator:checked {
    background: #2563eb;
    border-color: #60a5fa;
}
QRadioButton::indicator:hover { border-color: #60a5fa; }
QLabel#unfilledLbl {
    color: #fbbf24;
    background: #292113;
    border: 1px solid #78490a;
    border-radius: 5px;
    font-size: 12px;
    padding: 0 8px;
}
QRadioButton#rating_优 { color: #4ade80; font-weight: bold; }
QRadioButton#rating_良 { color: #60a5fa; font-weight: bold; }
QRadioButton#rating_平 { color: #f87171; font-weight: bold; }
QFrame#taskSeparator {
    color: #374151;
    background: #374151;
    max-height: 1px;
    margin: 2px 0;
}
QCheckBox {
    color: #d1d5db;
    spacing: 5px;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #4b5563;
    border-radius: 3px;
    background: #111827;
}
QCheckBox::indicator:checked {
    background: #2563eb;
    border-color: #60a5fa;
}
QCheckBox::indicator:hover { border-color: #60a5fa; }
QLineEdit#nameEdit {
    background: #374151;
    color: #f0f0f0;
    border: 1px solid #4b5563;
    border-radius: 5px;
    padding: 0 8px;
    font-size: 13px;
}
QLineEdit#nameEdit:focus {
    border-color: #60a5fa;
}
QLineEdit#nameEdit:hover {
    border-color: #6b7280;
}
QLabel#subLabel {
    color: #6b8cba;
    font-weight: bold;
    font-size: 12px;
}
QScrollArea {
    border: none;
    background: transparent;
}
QScrollBar:vertical {
    background: #1f2937;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #4b5563;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical { height: 0; }
QSplitter::handle {
    background: #374151;
    width: 3px;
}
"""


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("数据筛选工具")
    win = DataFilterApp()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
