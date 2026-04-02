"""
Paper Agent — 记忆管理工具

核心职责:
1. 项目进度追踪 (progress.yaml)
2. 用户偏好管理 (preferences.yaml)
3. 关键决策记录 (decisions.yaml)
4. 会话摘要管理 (sessions/)

设计原则:
- 所有状态持久化在 memory/ 目录中
- Agent 可通过本工具读写，也可直接编辑 YAML
- 读操作幂等，写操作做最小增量更新
- 不依赖外部数据库，纯文件系统
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# ============================================================
# 常量
# ============================================================

_THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _THIS_DIR.parent
MEMORY_DIR = PROJECT_ROOT / "memory"

# 合法的阶段和状态
PHASES = ("init", "research", "analysis", "writing", "review", "final")
PHASE_STATUSES = ("not_started", "in_progress", "completed")
SECTION_STATUSES = ("not_started", "outline", "draft", "review", "final")
FIGURE_STATUSES = ("planned", "in_progress", "completed")


# ============================================================
# 数据类
# ============================================================

@dataclass
class PhaseInfo:
    """单个阶段的状态。"""
    name: str
    status: str = "not_started"
    started_at: str | None = None
    completed_at: str | None = None


@dataclass
class SectionInfo:
    """单个章节的进度。"""
    name: str
    status: str = "not_started"
    word_count: int = 0
    last_edited: str | None = None
    todo_count: int = 0


@dataclass
class Decision:
    """一条决策记录。"""
    timestamp: str
    topic: str
    decision: str
    rationale: str = ""
    agent: str = ""


@dataclass
class SessionSummary:
    """一次会话的摘要。"""
    session_id: str
    date: str
    summary: str
    actions: list[str] = field(default_factory=list)
    files_changed: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)


@dataclass
class ProjectDashboard:
    """项目全局状态面板。"""
    current_phase: str
    phases: dict[str, PhaseInfo]
    sections: dict[str, SectionInfo]
    literature: dict[str, int]
    recent_decisions: list[Decision]
    last_session: SessionSummary | None

    def summary(self) -> str:
        lines = [
            "=" * 50,
            "  Paper Agent — 项目状态面板",
            "=" * 50,
            "",
            f"当前阶段: {self.current_phase}",
            "",
            "## 各阶段进度",
        ]
        for name in PHASES:
            info = self.phases.get(name)
            if info:
                icon = {"not_started": "○", "in_progress": "◐", "completed": "●"}.get(
                    info.status, "?"
                )
                lines.append(f"  {icon} {name}: {info.status}")

        if self.sections:
            lines.append("")
            lines.append("## 章节进度")
            for name, sec in self.sections.items():
                icon = {"not_started": "○", "outline": "◔", "draft": "◑",
                        "review": "◕", "final": "●"}.get(sec.status, "?")
                extra = f" ({sec.word_count} 字)" if sec.word_count else ""
                lines.append(f"  {icon} {name}: {sec.status}{extra}")

        lit = self.literature
        if any(v > 0 for v in lit.values()):
            lines.append("")
            lines.append("## 文献进度")
            lines.append(f"  文献库: {lit.get('total_in_library', 0)} 篇")
            lines.append(f"  已阅读: {lit.get('papers_with_notes', 0)} 篇")
            lines.append(f"  已引用: {lit.get('papers_cited', 0)} 篇")

        if self.recent_decisions:
            lines.append("")
            lines.append("## 近期决策")
            for d in self.recent_decisions[-3:]:
                lines.append(f"  [{d.timestamp[:10]}] {d.topic}: {d.decision}")

        if self.last_session:
            lines.append("")
            lines.append(f"## 上次会话 ({self.last_session.date})")
            lines.append(f"  {self.last_session.summary}")
            if self.last_session.next_steps:
                lines.append("  待办:")
                for step in self.last_session.next_steps:
                    lines.append(f"    - {step}")

        lines.append("")
        lines.append("=" * 50)
        return "\n".join(lines)


# ============================================================
# 核心类
# ============================================================

class MemoryManager:
    """项目记忆管理。

    读写 memory/ 目录下的 YAML 文件，提供结构化的进度追踪、
    偏好管理、决策记录和会话摘要功能。
    """

    def __init__(self, project_root: str | Path | None = None):
        self.root = Path(project_root) if project_root else PROJECT_ROOT
        self.memory_dir = self.root / "memory"
        self.progress_path = self.memory_dir / "progress.yaml"
        self.preferences_path = self.memory_dir / "preferences.yaml"
        self.decisions_path = self.memory_dir / "decisions.yaml"
        self.sessions_dir = self.memory_dir / "sessions"

    def ensure_dirs(self) -> None:
        """确保 memory/ 目录结构存在。"""
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    # ----------------------------------------------------------
    # 进度管理 (progress.yaml)
    # ----------------------------------------------------------

    def get_progress(self) -> dict[str, Any]:
        """加载当前进度。"""
        return self._load_yaml(self.progress_path) or self._default_progress()

    def get_current_phase(self) -> str:
        """获取当前阶段名。"""
        data = self.get_progress()
        return data.get("current_phase", "init")

    def set_current_phase(self, phase: str) -> None:
        """设置当前阶段（同时标记该阶段为 in_progress）。"""
        if phase not in PHASES:
            raise ValueError(f"无效阶段: {phase}，合法值: {PHASES}")
        data = self.get_progress()
        data["current_phase"] = phase
        phases = data.setdefault("phases", {})
        phase_data = phases.setdefault(phase, {})
        if phase_data.get("status") != "completed":
            phase_data["status"] = "in_progress"
            if not phase_data.get("started_at"):
                phase_data["started_at"] = self._now()
        self._save_yaml(self.progress_path, data)

    def complete_phase(self, phase: str) -> None:
        """标记一个阶段为已完成。"""
        if phase not in PHASES:
            raise ValueError(f"无效阶段: {phase}，合法值: {PHASES}")
        data = self.get_progress()
        phases = data.setdefault("phases", {})
        phase_data = phases.setdefault(phase, {})
        phase_data["status"] = "completed"
        phase_data["completed_at"] = self._now()
        if not phase_data.get("started_at"):
            phase_data["started_at"] = phase_data["completed_at"]

        # 自动推进到下一阶段
        idx = PHASES.index(phase)
        if data.get("current_phase") == phase and idx + 1 < len(PHASES):
            data["current_phase"] = PHASES[idx + 1]

        self._save_yaml(self.progress_path, data)

    def update_section(self, section: str, *,
                       status: str | None = None,
                       word_count: int | None = None,
                       todo_count: int | None = None) -> None:
        """更新章节进度。"""
        if status and status not in SECTION_STATUSES:
            raise ValueError(f"无效章节状态: {status}，合法值: {SECTION_STATUSES}")
        data = self.get_progress()
        sections = data.setdefault("sections", {})
        if not isinstance(sections, dict):
            sections = {}
            data["sections"] = sections
        sec = sections.setdefault(section, {})
        if status is not None:
            sec["status"] = status
        if word_count is not None:
            sec["word_count"] = word_count
        if todo_count is not None:
            sec["todo_count"] = todo_count
        sec["last_edited"] = self._now()
        self._save_yaml(self.progress_path, data)

    def update_figure(self, figure_name: str, *,
                      status: str | None = None,
                      path: str | None = None,
                      section: str | None = None) -> None:
        """更新图表进度。"""
        if status and status not in FIGURE_STATUSES:
            raise ValueError(f"无效图表状态: {status}，合法值: {FIGURE_STATUSES}")
        data = self.get_progress()
        figures = data.setdefault("figures", {})
        if not isinstance(figures, dict):
            figures = {}
            data["figures"] = figures
        fig = figures.setdefault(figure_name, {})
        if status is not None:
            fig["status"] = status
        if path is not None:
            fig["path"] = path
        if section is not None:
            fig["section"] = section
        self._save_yaml(self.progress_path, data)

    def update_literature_stats(self, *,
                                total: int | None = None,
                                with_notes: int | None = None,
                                cited: int | None = None) -> None:
        """更新文献统计。"""
        data = self.get_progress()
        lit = data.setdefault("literature", {})
        if total is not None:
            lit["total_in_library"] = total
        if with_notes is not None:
            lit["papers_with_notes"] = with_notes
        if cited is not None:
            lit["papers_cited"] = cited
        self._save_yaml(self.progress_path, data)

    # ----------------------------------------------------------
    # 偏好管理 (preferences.yaml)
    # ----------------------------------------------------------

    def get_preferences(self) -> dict[str, Any]:
        """加载所有偏好。"""
        return self._load_yaml(self.preferences_path) or {}

    def get_preference(self, category: str, key: str) -> Any:
        """获取单个偏好值。"""
        prefs = self.get_preferences()
        cat = prefs.get(category) or {}
        return cat.get(key)

    def set_preference(self, category: str, key: str, value: Any) -> None:
        """设置单个偏好值。"""
        prefs = self.get_preferences()
        cat = prefs.setdefault(category, {})
        if not isinstance(cat, dict):
            cat = {}
            prefs[category] = cat
        cat[key] = value
        self._save_yaml(self.preferences_path, prefs)

    # ----------------------------------------------------------
    # 决策记录 (decisions.yaml)
    # ----------------------------------------------------------

    def get_decisions(self) -> list[dict[str, Any]]:
        """加载所有决策。"""
        data = self._load_yaml(self.decisions_path) or {}
        decisions = data.get("decisions") or []
        if not isinstance(decisions, list):
            return []
        return decisions

    def log_decision(self, topic: str, decision: str,
                     rationale: str = "", agent: str = "") -> None:
        """记录一条新决策。"""
        data = self._load_yaml(self.decisions_path) or {}
        decisions = data.get("decisions") or []
        if not isinstance(decisions, list):
            decisions = []
        entry = {
            "timestamp": self._now(),
            "topic": topic,
            "decision": decision,
        }
        if rationale:
            entry["rationale"] = rationale
        if agent:
            entry["agent"] = agent
        decisions.append(entry)
        data["decisions"] = decisions
        self._save_yaml(self.decisions_path, data)

    # ----------------------------------------------------------
    # 会话摘要 (sessions/)
    # ----------------------------------------------------------

    def create_session_summary(self, summary: str,
                               actions: list[str] | None = None,
                               files_changed: list[str] | None = None,
                               next_steps: list[str] | None = None) -> Path:
        """创建一次会话摘要，保存到 sessions/ 目录。"""
        self.ensure_dirs()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        # 生成序号
        existing = sorted(self.sessions_dir.glob(f"{today}_*.yaml"))
        seq = len(existing) + 1
        session_id = f"{today}_{seq:03d}"
        filename = f"{session_id}.yaml"

        data: dict[str, Any] = {
            "session_id": session_id,
            "date": today,
            "timestamp": self._now(),
            "summary": summary,
        }
        if actions:
            data["actions"] = actions
        if files_changed:
            data["files_changed"] = files_changed
        if next_steps:
            data["next_steps"] = next_steps

        out_path = self.sessions_dir / filename
        self._save_yaml(out_path, data)
        return out_path

    def get_latest_session(self) -> dict[str, Any] | None:
        """获取最近一次会话摘要。"""
        if not self.sessions_dir.exists():
            return None
        files = sorted(self.sessions_dir.glob("*.yaml"))
        if not files:
            return None
        return self._load_yaml(files[-1])

    def list_sessions(self) -> list[str]:
        """列出所有会话摘要的 session_id。"""
        if not self.sessions_dir.exists():
            return []
        files = sorted(self.sessions_dir.glob("*.yaml"))
        return [f.stem for f in files]

    # ----------------------------------------------------------
    # 全局状态面板
    # ----------------------------------------------------------

    def get_dashboard(self) -> ProjectDashboard:
        """生成项目全局状态面板。"""
        progress = self.get_progress()
        decisions = self.get_decisions()
        last_session_data = self.get_latest_session()

        # 解析阶段
        phases_dict: dict[str, PhaseInfo] = {}
        raw_phases = progress.get("phases") or {}
        for name in PHASES:
            p = raw_phases.get(name) or {}
            phases_dict[name] = PhaseInfo(
                name=name,
                status=p.get("status", "not_started"),
                started_at=p.get("started_at"),
                completed_at=p.get("completed_at"),
            )

        # 解析章节
        sections_dict: dict[str, SectionInfo] = {}
        raw_sections = progress.get("sections") or {}
        if isinstance(raw_sections, dict):
            for name, s in raw_sections.items():
                if isinstance(s, dict):
                    sections_dict[name] = SectionInfo(
                        name=name,
                        status=s.get("status", "not_started"),
                        word_count=s.get("word_count", 0),
                        last_edited=s.get("last_edited"),
                        todo_count=s.get("todo_count", 0),
                    )

        # 解析文献
        literature = progress.get("literature") or {}

        # 解析决策
        recent = [
            Decision(
                timestamp=d.get("timestamp", ""),
                topic=d.get("topic", ""),
                decision=d.get("decision", ""),
                rationale=d.get("rationale", ""),
                agent=d.get("agent", ""),
            )
            for d in decisions[-5:]  # 最近 5 条
        ]

        # 解析上次会话
        last_session = None
        if last_session_data:
            last_session = SessionSummary(
                session_id=last_session_data.get("session_id", ""),
                date=last_session_data.get("date", ""),
                summary=last_session_data.get("summary", ""),
                actions=last_session_data.get("actions", []),
                files_changed=last_session_data.get("files_changed", []),
                next_steps=last_session_data.get("next_steps", []),
            )

        return ProjectDashboard(
            current_phase=progress.get("current_phase", "init"),
            phases=phases_dict,
            sections=sections_dict,
            literature=literature,
            recent_decisions=recent,
            last_session=last_session,
        )

    # ----------------------------------------------------------
    # 工具函数
    # ----------------------------------------------------------

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _load_yaml(self, path: Path) -> dict | None:
        if not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as fp:
                return yaml.safe_load(fp) or {}
        except yaml.YAMLError:
            return None

    def _save_yaml(self, path: Path, data: dict) -> None:
        self.ensure_dirs()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fp:
            yaml.dump(data, fp, default_flow_style=False,
                      allow_unicode=True, sort_keys=False)

    def _default_progress(self) -> dict[str, Any]:
        return {
            "current_phase": "init",
            "phases": {p: {"status": "not_started",
                           "started_at": None,
                           "completed_at": None} for p in PHASES},
            "sections": {},
            "figures": {},
            "literature": {
                "total_in_library": 0,
                "papers_with_notes": 0,
                "papers_cited": 0,
            },
        }


# ============================================================
# CLI 入口
# ============================================================

def main():
    """命令行入口：显示项目状态面板。"""
    mm = MemoryManager()
    dashboard = mm.get_dashboard()
    print(dashboard.summary())


if __name__ == "__main__":
    main()
