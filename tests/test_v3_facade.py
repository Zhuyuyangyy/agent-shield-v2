"""
test_v3_facade.py
=================
Comprehensive tests for AgentShieldV3 facade (V3 unified entry).
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
from app.shadow.v3_facade import AgentShieldV3, ChainAuditRequest, ChainAuditResult
from app.shadow.governance.governance_engine import GovernanceAction


@pytest.fixture
def v3():
    return AgentShieldV3(session_id="test_v3_session")


@pytest.fixture
def sample_request():
    return ChainAuditRequest(
        session_id="test_chain",
        agent_id="FinancialAgent",
        tool_call_records=[
            {
                "agent_id": "FinancialAgent",
                "tool_name": "cursor.execute",
                "params_summary": "SELECT name,price FROM products",
                "fuse_action": "allow",
                "shadow_risk_score": 0.05,
            },
            {
                "agent_id": "CustomerDataAgent",
                "tool_name": "cursor.execute",
                "params_summary": "SELECT phone,address FROM customers",
                "fuse_action": "allow",
                "shadow_risk_score": 0.75,
                "parent_agent_id": "FinancialAgent",
                "edge_type": "calls",
                "inherited_risk": 0.025,
            },
            {
                "agent_id": "EmailAgent",
                "tool_name": "send_email",
                "params_summary": "send_email(to=ext,data=cust)",
                "fuse_action": "block",
                "shadow_risk_score": 0.98,
                "parent_agent_id": "CustomerDataAgent",
                "edge_type": "data_flow",
                "inherited_risk": 0.55,
            },
        ],
    )


class TestAgentShieldV3Creation:
    """Test V3 facade creation."""

    def test_v3_creation(self, v3):
        assert v3.session_id == "test_v3_session"
        assert v3.graph is not None
        assert v3._processed_count == 0

    def test_v3_default_session(self):
        v3 = AgentShieldV3()
        assert v3.session_id == "unknown"


class TestAgentShieldV3AddToolCall:
    """Test adding tool calls."""

    def test_add_single_tool_call(self, v3):
        node = v3.add_tool_call(
            agent_id="agent_1",
            tool_name="cursor.execute",
            params_summary="SELECT 1",
            fuse_action="allow",
            shadow_risk_score=0.1,
        )
        assert node is not None
        assert v3._processed_count == 1

    def test_add_multiple_tool_calls(self, v3):
        for i in range(5):
            v3.add_tool_call(
                agent_id=f"agent_{i}",
                tool_name="cursor.execute",
                params_summary=f"SELECT {i}",
                fuse_action="allow",
                shadow_risk_score=0.1 * i,
            )
        assert v3._processed_count == 5

    def test_add_tool_call_with_parent(self, v3):
        n1 = v3.add_tool_call(
            agent_id="agent_1",
            tool_name="cursor.execute",
            params_summary="SELECT 1",
            fuse_action="allow",
            shadow_risk_score=0.1,
        )
        n2 = v3.add_tool_call(
            agent_id="agent_2",
            tool_name="send_email",
            params_summary="send data",
            fuse_action="block",
            shadow_risk_score=0.95,
            parent_agent_id="agent_1",
        )
        assert len(v3.graph.edges) == 1


class TestAgentShieldV3AuditChain:
    """Test full chain audit."""

    def test_audit_chain_returns_result(self, v3, sample_request):
        result = v3.audit_chain(sample_request)
        assert isinstance(result, ChainAuditResult)

    def test_audit_chain_result_fields(self, v3, sample_request):
        result = v3.audit_chain(sample_request)
        assert result.session_id == "test_chain"
        assert "total_calls" in result.v2_summary
        assert "nodes" in result.behavior_graph
        assert "critical_chains" in result.causality_report
        assert "decisions" in result.governance_report
        assert result.overall_risk_level in ["safe", "low", "medium", "high", "critical"]

    def test_audit_chain_v2_summary(self, v3, sample_request):
        result = v3.audit_chain(sample_request)
        v2 = result.v2_summary
        assert v2["total_calls"] == 3
        assert v2["blocked"] == 1
        assert v2["allowed"] == 2


class TestAgentShieldV3RunGovernance:
    """Test run_governance method."""

    def test_run_governance_after_adding_calls(self, v3):
        v3.add_tool_call(
            agent_id="agent_1",
            tool_name="cursor.execute",
            params_summary="SELECT phone FROM customers",
            fuse_action="block",
            shadow_risk_score=0.95,
        )
        report = v3.run_governance()
        assert "decisions" in report
        assert "whatif_scenarios" in report


class TestAgentShieldV3GetResult:
    """Test get_result method."""

    def test_get_result_before_governance(self, v3):
        result = v3.get_result()
        assert result is None

    def test_get_result_after_governance(self, v3):
        v3.add_tool_call(
            agent_id="agent_1",
            tool_name="cursor.execute",
            params_summary="SELECT 1",
            fuse_action="allow",
            shadow_risk_score=0.1,
        )
        v3.run_governance()
        result = v3.get_result()
        assert result is not None
        assert isinstance(result, ChainAuditResult)


class TestAgentShieldV3OverallRisk:
    """Test overall risk computation."""

    def test_overall_risk_safe(self):
        v3 = AgentShieldV3(session_id="safe_test")
        # No governance run yet
        assert v3._compute_overall_risk() == "unknown"

    def test_overall_risk_with_blocked(self, v3, sample_request):
        result = v3.audit_chain(sample_request)
        assert result.overall_risk_level in ["high", "critical"]


class TestAgentShieldV3Summary:
    """Test summary generation."""

    def test_summary_without_governance(self, v3):
        summary = v3._generate_summary()
        assert summary == "无治理决策。"

    def test_summary_with_governance(self, v3, sample_request):
        result = v3.audit_chain(sample_request)
        assert isinstance(result.governance_summary, str)
        assert len(result.governance_summary) > 0


class TestChainAuditRequest:
    """Test ChainAuditRequest dataclass."""

    def test_request_fields(self):
        req = ChainAuditRequest(session_id="test")
        assert req.session_id == "test"
        assert req.agent_id == "unknown"
        assert req.tool_call_records == []

    def test_request_with_records(self):
        req = ChainAuditRequest(
            session_id="test",
            agent_id="agent_1",
            tool_call_records=[{"tool_name": "test"}],
        )
        assert len(req.tool_call_records) == 1


class TestChainAuditResult:
    """Test ChainAuditResult dataclass."""

    def test_result_fields(self):
        result = ChainAuditResult(
            session_id="test",
            v2_summary={},
            behavior_graph={},
            causality_report={},
            governance_report={},
            overall_risk_level="safe",
            governance_summary="test",
        )
        assert result.session_id == "test"
        assert result.timestamp is not None
