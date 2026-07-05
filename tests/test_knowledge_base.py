"""KnowledgeBase state machine tests — status transitions, error handling."""
from __future__ import annotations

import pytest

from knowledge.knowledge_base import (
    KnowledgeBase,
    StatusError,
    HYPOTHESIS_TRANSITIONS,
    FAILURE_TRANSITIONS,
    HYPOTHESIS_INITIAL_STATUS,
    FAILURE_INITIAL_STATUS,
)


class TestTransitionsDefinition:
    def test_hypothesis_has_initial_state(self):
        assert HYPOTHESIS_INITIAL_STATUS == "draft"

    def test_failure_has_initial_state(self):
        assert FAILURE_INITIAL_STATUS == "new"

    def test_obsolete_is_terminal(self):
        assert HYPOTHESIS_TRANSITIONS["obsolete"] == set()

    def test_archived_is_terminal(self):
        assert FAILURE_TRANSITIONS["archived"] == set()

    def test_hypothesis_chain_is_valid(self):
        """Full lifecycle: draft→active→verified→obsolete"""
        assert "active" in HYPOTHESIS_TRANSITIONS["draft"]
        assert "verified" in HYPOTHESIS_TRANSITIONS["active"]
        assert "obsolete" in HYPOTHESIS_TRANSITIONS["verified"]

    def test_rejected_shortcut(self):
        """draft can go directly to rejected."""
        assert "rejected" in HYPOTHESIS_TRANSITIONS["draft"]
        assert "obsolete" in HYPOTHESIS_TRANSITIONS["rejected"]

    def test_failure_chain(self):
        """new→reviewed→actioned→archived"""
        assert "reviewed" in FAILURE_TRANSITIONS["new"]
        assert "actioned" in FAILURE_TRANSITIONS["reviewed"]
        assert "archived" in FAILURE_TRANSITIONS["actioned"]


class TestHypothesisStatus:
    def test_save_defaults_to_draft(self, temp_kb: KnowledgeBase):
        h_id = temp_kb.save_hypothesis({"title": "test"})
        hypotheses = temp_kb.load_hypotheses(status="draft")
        ids = [h["id"] for h in hypotheses]
        assert h_id in ids

    def test_set_status_valid(self, temp_kb: KnowledgeBase):
        h_id = temp_kb.save_hypothesis({"title": "test"})
        updated = temp_kb.set_hypothesis_status(h_id, "active")
        assert updated["status"] == "active"

    def test_set_status_raises_on_illegal(self, temp_kb: KnowledgeBase):
        h_id = temp_kb.save_hypothesis({"title": "test"})
        temp_kb.set_hypothesis_status(h_id, "active")
        temp_kb.set_hypothesis_status(h_id, "verified")
        with pytest.raises(StatusError):
            temp_kb.set_hypothesis_status(h_id, "draft")  # verified→draft invalid

    def test_set_status_raises_on_unknown_state(self, temp_kb: KnowledgeBase):
        h_id = temp_kb.save_hypothesis({"title": "test"})
        with pytest.raises(StatusError):
            temp_kb.set_hypothesis_status(h_id, "nonexistent_state")

    def test_set_status_raises_on_nonexistent_id(self, temp_kb: KnowledgeBase):
        with pytest.raises(ValueError):
            temp_kb.set_hypothesis_status("hyp_nonexistent", "active")

    def test_full_lifecycle(self, temp_kb: KnowledgeBase):
        h_id = temp_kb.save_hypothesis({"title": "test"})
        assert temp_kb.set_hypothesis_status(h_id, "active")["status"] == "active"
        assert temp_kb.set_hypothesis_status(h_id, "verified")["status"] == "verified"
        assert temp_kb.set_hypothesis_status(h_id, "obsolete")["status"] == "obsolete"

    def test_rejected_flow(self, temp_kb: KnowledgeBase):
        h_id = temp_kb.save_hypothesis({"title": "nonsense"})
        temp_kb.set_hypothesis_status(h_id, "rejected")
        assert temp_kb.set_hypothesis_status(h_id, "obsolete")["status"] == "obsolete"


class TestFailureStatus:
    def test_save_defaults_to_new(self, temp_kb: KnowledgeBase):
        f_id = temp_kb.save_failure({"category": "strategy", "lesson": "oops"})
        failures = temp_kb.load_failures(status="new")
        ids = [f["id"] for f in failures]
        assert f_id in ids

    def test_failure_status_valid(self, temp_kb: KnowledgeBase):
        f_id = temp_kb.save_failure({"category": "strategy", "lesson": "oops"})
        updated = temp_kb.set_failure_status(f_id, "reviewed")
        assert updated["status"] == "reviewed"

    def test_failure_status_raises_on_illegal(self, temp_kb: KnowledgeBase):
        f_id = temp_kb.save_failure({"category": "strategy", "lesson": "oops"})
        with pytest.raises(StatusError):
            temp_kb.set_failure_status(f_id, "archived")  # new→archived invalid


class TestHypothesisStats:
    def test_stats_reflects_status_changes(self, temp_kb: KnowledgeBase):
        h1 = temp_kb.save_hypothesis({"title": "a"})
        h2 = temp_kb.save_hypothesis({"title": "b"})
        temp_kb.set_hypothesis_status(h1, "active")
        temp_kb.set_hypothesis_status(h2, "rejected")
        stats = temp_kb.get_hypothesis_stats()
        assert stats["total"] == 2
        assert stats["active"] == 1
        assert stats["rejected"] == 1

    def test_filter_by_status(self, temp_kb: KnowledgeBase):
        h_id = temp_kb.save_hypothesis({"title": "test"})
        temp_kb.set_hypothesis_status(h_id, "active")
        temp_kb.set_hypothesis_status(h_id, "verified")
        verified = temp_kb.load_hypotheses_by_status("verified")
        assert len(verified) == 1
        assert verified[0]["id"] == h_id
        draft = temp_kb.load_hypotheses_by_status("draft")
        matching = [h for h in draft if h["id"] == h_id]
        assert len(matching) == 0
