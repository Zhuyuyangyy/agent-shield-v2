"""
test_causality_engine.py
========================
Comprehensive tests for CausalityEngine (V3 Layer 2).
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
from app.shadow.behavior.agent_behavior_graph import AgentBehaviorGraph, BehaviorNode, BehaviorEdge
from app.shadow.causality.causality_engine import CausalityEngine, RiskAttribution, CausalChain


@pytest.fixture
def simple_graph():
    """Simple two-node graph."""
    graph = AgentBehaviorGraph(session_id="test_causal")
    n1 = BehaviorNode(agent_id="agent_1", tool_name="cursor.execute", shadow_risk_score=0.3)
    n2 = BehaviorNode(agent_id="agent_2", tool_name="send_email", shadow_risk_score=0.95)
    graph.add_node(n1)
    graph.add_node(n2)
    graph.add_edge(BehaviorEdge(from_node_id=n1.node_id, to_node_id=n2.node_id))
    return graph


@pytest.fixture
def complex_graph():
    """Complex multi-agent graph."""
    graph = AgentBehaviorGraph(session_id="test_complex")
    n1 = BehaviorNode(agent_id="FinancialAgent", tool_name="cursor.execute", shadow_risk_score=0.05)
    n2 = BehaviorNode(agent_id="CustomerDataAgent", tool_name="cursor.execute", shadow_risk_score=0.75)
    n3 = BehaviorNode(agent_id="EmailAgent", tool_name="send_email", shadow_risk_score=0.98)
    n4 = BehaviorNode(agent_id="DataExportAgent", tool_name="export_csv", shadow_risk_score=0.82)
    graph.add_node(n1)
    graph.add_node(n2)
    graph.add_node(n3)
    graph.add_node(n4)
    graph.add_edge(BehaviorEdge(from_node_id=n1.node_id, to_node_id=n2.node_id))
    graph.add_edge(BehaviorEdge(from_node_id=n2.node_id, to_node_id=n3.node_id))
    graph.add_edge(BehaviorEdge(from_node_id=n1.node_id, to_node_id=n4.node_id))
    return graph


class TestCausalityEngineBasic:
    """Test basic causality engine functionality."""

    def test_engine_creation(self, simple_graph):
        engine = CausalityEngine(simple_graph)
        assert engine.graph == simple_graph

    def test_analyze_returns_dict(self, simple_graph):
        engine = CausalityEngine(simple_graph)
        result = engine.analyze()
        assert isinstance(result, dict)

    def test_analyze_empty_graph(self):
        graph = AgentBehaviorGraph(session_id="empty")
        engine = CausalityEngine(graph)
        result = engine.analyze()
        assert isinstance(result, dict)


class TestCausalityEngineReport:
    """Test report generation."""

    def test_report_has_graph_summary(self, simple_graph):
        engine = CausalityEngine(simple_graph)
        report = engine.analyze()
        assert "graph_summary" in report

    def test_report_has_critical_chains(self, simple_graph):
        engine = CausalityEngine(simple_graph)
        report = engine.analyze()
        assert "critical_chains" in report

    def test_report_has_root_cause_attributions(self, simple_graph):
        engine = CausalityEngine(simple_graph)
        report = engine.analyze()
        assert "root_cause_attributions" in report

    def test_complex_graph_has_chains(self, complex_graph):
        engine = CausalityEngine(complex_graph)
        report = engine.analyze()
        chains = report.get("critical_chains", [])
        assert len(chains) > 0


class TestCausalChain:
    """Test CausalChain dataclass."""

    def test_chain_fields(self):
        chain = CausalChain(
            chain_id="chain_1",
            root_node_id="n1",
            root_agent_id="agent_1",
            terminal_node_id="n3",
            terminal_risk_score=0.95,
            chain_risk_trajectory=[0.1, 0.5, 0.95],
            amplification_factor=9.5,
            weak_links=["n2"],
        )
        assert chain.chain_id == "chain_1"
        assert chain.amplification_factor == 9.5
        assert "n2" in chain.weak_links


class TestRiskAttribution:
    """Test RiskAttribution dataclass."""

    def test_attribution_fields(self):
        attr = RiskAttribution(
            responsible_node_id="n1",
            responsible_agent_id="agent_1",
            responsibility_score=0.8,
            direct_risk_contribution=0.95,
            inherited_risk_contribution=0.5,
            chain_length=3,
            causal_path=["n1", "n2", "n3"],
            explanation="Test explanation",
        )
        assert attr.responsible_agent_id == "agent_1"
        assert attr.responsibility_score == 0.8
        assert len(attr.causal_path) == 3


class TestCausalityEngineThresholds:
    """Test engine threshold constants."""

    def test_amplification_threshold(self):
        assert CausalityEngine.AMPLIFICATION_THRESHOLD == 1.2

    def test_root_cause_threshold(self):
        assert CausalityEngine.ROOT_CAUSE_THRESHOLD == 0.4
