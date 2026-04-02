"""tests/test_memory_manager.py — 记忆管理工具测试"""

from __future__ import annotations

import pytest
import yaml
from pathlib import Path

from tools.memory_manager import (
    MemoryManager,
    PHASES,
    PHASE_STATUSES,
    SECTION_STATUSES,
    FIGURE_STATUSES,
)


@pytest.fixture
def tmp_project(tmp_path):
    """创建临时项目目录结构。"""
    (tmp_path / "memory").mkdir()
    (tmp_path / "memory" / "sessions").mkdir()
    return tmp_path


@pytest.fixture
def mm(tmp_project):
    """创建 MemoryManager 实例。"""
    return MemoryManager(project_root=tmp_project)


# ============================================================
# 目录与初始化
# ============================================================

class TestSetup:
    def test_ensure_dirs_creates_structure(self, tmp_path):
        mm = MemoryManager(project_root=tmp_path)
        mm.ensure_dirs()
        assert (tmp_path / "memory").is_dir()
        assert (tmp_path / "memory" / "sessions").is_dir()

    def test_ensure_dirs_idempotent(self, mm):
        mm.ensure_dirs()
        mm.ensure_dirs()  # 不应报错

    def test_get_progress_returns_default_when_no_file(self, mm):
        progress = mm.get_progress()
        assert progress["current_phase"] == "init"
        assert "phases" in progress
        assert all(p in progress["phases"] for p in PHASES)


# ============================================================
# 阶段管理
# ============================================================

class TestPhaseManagement:
    def test_get_current_phase_default(self, mm):
        assert mm.get_current_phase() == "init"

    def test_set_current_phase(self, mm):
        mm.set_current_phase("research")
        assert mm.get_current_phase() == "research"
        progress = mm.get_progress()
        assert progress["phases"]["research"]["status"] == "in_progress"
        assert progress["phases"]["research"]["started_at"] is not None

    def test_set_invalid_phase_raises(self, mm):
        with pytest.raises(ValueError, match="无效阶段"):
            mm.set_current_phase("invalid_phase")

    def test_complete_phase(self, mm):
        mm.set_current_phase("init")
        mm.complete_phase("init")
        progress = mm.get_progress()
        assert progress["phases"]["init"]["status"] == "completed"
        assert progress["phases"]["init"]["completed_at"] is not None
        # 应自动推进到下一阶段
        assert progress["current_phase"] == "research"

    def test_complete_phase_auto_sets_started_at(self, mm):
        mm.complete_phase("analysis")
        progress = mm.get_progress()
        assert progress["phases"]["analysis"]["started_at"] is not None

    def test_complete_last_phase_stays(self, mm):
        mm.set_current_phase("final")
        mm.complete_phase("final")
        progress = mm.get_progress()
        assert progress["phases"]["final"]["status"] == "completed"
        # final 是最后一个阶段，current_phase 保持不变
        assert progress["current_phase"] == "final"

    def test_complete_invalid_phase_raises(self, mm):
        with pytest.raises(ValueError, match="无效阶段"):
            mm.complete_phase("nonexistent")

    def test_set_phase_preserves_completed(self, mm):
        """已完成的阶段不应被重置为 in_progress。"""
        mm.complete_phase("init")
        mm.set_current_phase("init")
        progress = mm.get_progress()
        assert progress["phases"]["init"]["status"] == "completed"


# ============================================================
# 章节进度
# ============================================================

class TestSectionProgress:
    def test_update_section_creates_entry(self, mm):
        mm.update_section("01-introduction", status="draft", word_count=500)
        progress = mm.get_progress()
        sec = progress["sections"]["01-introduction"]
        assert sec["status"] == "draft"
        assert sec["word_count"] == 500
        assert sec["last_edited"] is not None

    def test_update_section_partial(self, mm):
        mm.update_section("02-related", status="outline")
        mm.update_section("02-related", word_count=300)
        progress = mm.get_progress()
        sec = progress["sections"]["02-related"]
        assert sec["status"] == "outline"
        assert sec["word_count"] == 300

    def test_update_section_invalid_status(self, mm):
        with pytest.raises(ValueError, match="无效章节状态"):
            mm.update_section("01-intro", status="bogus")

    def test_update_section_todo_count(self, mm):
        mm.update_section("03-method", status="draft", todo_count=5)
        progress = mm.get_progress()
        assert progress["sections"]["03-method"]["todo_count"] == 5

    def test_multiple_sections(self, mm):
        mm.update_section("01-intro", status="final")
        mm.update_section("02-related", status="draft")
        mm.update_section("03-method", status="not_started")
        progress = mm.get_progress()
        assert len(progress["sections"]) == 3


# ============================================================
# 图表进度
# ============================================================

class TestFigureProgress:
    def test_update_figure(self, mm):
        mm.update_figure("fig_01_arch", status="completed",
                         path="pipeline/figures/fig_01.pdf", section="03-method")
        progress = mm.get_progress()
        fig = progress["figures"]["fig_01_arch"]
        assert fig["status"] == "completed"
        assert fig["path"] == "pipeline/figures/fig_01.pdf"
        assert fig["section"] == "03-method"

    def test_update_figure_invalid_status(self, mm):
        with pytest.raises(ValueError, match="无效图表状态"):
            mm.update_figure("fig_01", status="wrong")

    def test_update_figure_partial(self, mm):
        mm.update_figure("fig_02", status="planned")
        mm.update_figure("fig_02", status="completed",
                         path="pipeline/figures/fig_02.pdf")
        progress = mm.get_progress()
        assert progress["figures"]["fig_02"]["status"] == "completed"


# ============================================================
# 文献统计
# ============================================================

class TestLiteratureStats:
    def test_update_literature(self, mm):
        mm.update_literature_stats(total=15, with_notes=8, cited=6)
        progress = mm.get_progress()
        lit = progress["literature"]
        assert lit["total_in_library"] == 15
        assert lit["papers_with_notes"] == 8
        assert lit["papers_cited"] == 6

    def test_partial_update(self, mm):
        mm.update_literature_stats(total=10)
        mm.update_literature_stats(cited=3)
        progress = mm.get_progress()
        assert progress["literature"]["total_in_library"] == 10
        assert progress["literature"]["papers_cited"] == 3


# ============================================================
# 偏好管理
# ============================================================

class TestPreferences:
    def test_get_empty_preferences(self, mm):
        prefs = mm.get_preferences()
        assert isinstance(prefs, dict)

    def test_set_and_get_preference(self, mm):
        mm.set_preference("writing", "tone", "formal")
        assert mm.get_preference("writing", "tone") == "formal"

    def test_set_preference_creates_category(self, mm):
        mm.set_preference("new_cat", "key", "value")
        prefs = mm.get_preferences()
        assert prefs["new_cat"]["key"] == "value"

    def test_overwrite_preference(self, mm):
        mm.set_preference("writing", "tone", "casual")
        mm.set_preference("writing", "tone", "formal")
        assert mm.get_preference("writing", "tone") == "formal"

    def test_get_nonexistent_preference(self, mm):
        assert mm.get_preference("nope", "nope") is None

    def test_multiple_categories(self, mm):
        mm.set_preference("writing", "tone", "formal")
        mm.set_preference("workflow", "auto_compile", True)
        mm.set_preference("interaction", "verbosity", "concise")
        prefs = mm.get_preferences()
        assert len(prefs) >= 3


# ============================================================
# 决策记录
# ============================================================

class TestDecisions:
    def test_get_empty_decisions(self, mm):
        assert mm.get_decisions() == []

    def test_log_decision(self, mm):
        mm.log_decision("结构", "5 章", rationale="页数限制", agent="writer")
        decisions = mm.get_decisions()
        assert len(decisions) == 1
        d = decisions[0]
        assert d["topic"] == "结构"
        assert d["decision"] == "5 章"
        assert d["rationale"] == "页数限制"
        assert d["agent"] == "writer"
        assert "timestamp" in d

    def test_multiple_decisions(self, mm):
        mm.log_decision("A", "a1")
        mm.log_decision("B", "b1")
        mm.log_decision("C", "c1")
        assert len(mm.get_decisions()) == 3

    def test_log_decision_minimal(self, mm):
        mm.log_decision("topic", "decision")
        d = mm.get_decisions()[0]
        assert "rationale" not in d
        assert "agent" not in d

    def test_decisions_persist(self, mm, tmp_project):
        mm.log_decision("X", "x1")
        # 新实例应能读到
        mm2 = MemoryManager(project_root=tmp_project)
        assert len(mm2.get_decisions()) == 1


# ============================================================
# 会话摘要
# ============================================================

class TestSessions:
    def test_create_session_summary(self, mm):
        path = mm.create_session_summary(
            "完成了初始化",
            actions=["扫描数据", "填充配置"],
            files_changed=["config/paper.yaml"],
            next_steps=["开始文献调研"],
        )
        assert path.exists()
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert data["summary"] == "完成了初始化"
        assert len(data["actions"]) == 2
        assert "config/paper.yaml" in data["files_changed"]

    def test_session_id_format(self, mm):
        path = mm.create_session_summary("test")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        # session_id 格式: YYYY-MM-DD_NNN
        assert "_" in data["session_id"]
        parts = data["session_id"].split("_")
        assert len(parts) == 2
        assert len(parts[1]) == 3

    def test_multiple_sessions_same_day(self, mm):
        p1 = mm.create_session_summary("session 1")
        p2 = mm.create_session_summary("session 2")
        assert p1 != p2
        d1 = yaml.safe_load(p1.read_text(encoding="utf-8"))
        d2 = yaml.safe_load(p2.read_text(encoding="utf-8"))
        assert d1["session_id"] != d2["session_id"]

    def test_get_latest_session(self, mm):
        mm.create_session_summary("first")
        mm.create_session_summary("second")
        latest = mm.get_latest_session()
        assert latest["summary"] == "second"

    def test_get_latest_session_empty(self, mm):
        assert mm.get_latest_session() is None

    def test_list_sessions(self, mm):
        mm.create_session_summary("s1")
        mm.create_session_summary("s2")
        ids = mm.list_sessions()
        assert len(ids) == 2


# ============================================================
# 全局面板
# ============================================================

class TestDashboard:
    def test_dashboard_default(self, mm):
        dashboard = mm.get_dashboard()
        assert dashboard.current_phase == "init"
        assert len(dashboard.phases) == len(PHASES)

    def test_dashboard_with_data(self, mm):
        mm.set_current_phase("writing")
        mm.complete_phase("init")
        mm.complete_phase("research")
        mm.update_section("01-intro", status="final", word_count=800)
        mm.update_literature_stats(total=10, with_notes=5, cited=3)
        mm.log_decision("结构", "5 章")
        mm.create_session_summary("完成初始化")

        dashboard = mm.get_dashboard()
        assert dashboard.current_phase == "writing"
        assert dashboard.phases["init"].status == "completed"
        assert "01-intro" in dashboard.sections
        assert dashboard.sections["01-intro"].word_count == 800
        assert dashboard.literature["total_in_library"] == 10
        assert len(dashboard.recent_decisions) == 1
        assert dashboard.last_session is not None
        assert dashboard.last_session.summary == "完成初始化"

    def test_dashboard_summary_string(self, mm):
        mm.set_current_phase("analysis")
        mm.update_section("01-intro", status="draft", word_count=500)
        dashboard = mm.get_dashboard()
        text = dashboard.summary()
        assert "项目状态面板" in text
        assert "analysis" in text
        assert "01-intro" in text

    def test_dashboard_empty_summary(self, mm):
        dashboard = mm.get_dashboard()
        text = dashboard.summary()
        assert "项目状态面板" in text


# ============================================================
# 边界情况
# ============================================================

class TestEdgeCases:
    def test_corrupted_yaml(self, mm):
        """损坏的 YAML 文件应安全处理。"""
        mm.progress_path.parent.mkdir(parents=True, exist_ok=True)
        mm.progress_path.write_text("{{invalid yaml", encoding="utf-8")
        progress = mm.get_progress()
        assert progress["current_phase"] == "init"

    def test_concurrent_writes(self, mm, tmp_project):
        """两个实例写同一文件不崩溃。"""
        mm2 = MemoryManager(project_root=tmp_project)
        mm.set_preference("a", "k", "v1")
        mm2.set_preference("a", "k", "v2")
        assert mm.get_preference("a", "k") == "v2"

    def test_no_memory_dir(self, tmp_path):
        """memory/ 目录不存在时应自动创建。"""
        mm = MemoryManager(project_root=tmp_path)
        mm.set_preference("x", "y", "z")
        assert (tmp_path / "memory" / "preferences.yaml").exists()

    def test_empty_sections_dict(self, mm):
        """sections 为空 dict 时不报错。"""
        mm.ensure_dirs()
        mm._save_yaml(mm.progress_path, {
            "current_phase": "init",
            "phases": {},
            "sections": {},
            "figures": {},
            "literature": {},
        })
        dashboard = mm.get_dashboard()
        assert dashboard.sections == {}
