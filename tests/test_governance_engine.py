"""
test_governance_engine.py
=========================
Comprehensive tests for GovernanceEngine (V3 Layer 3).
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
from app.shadow.behavior.agent_behavior_graph import AgentBehaviorGraph, BehaviorNode, BehaviorEdge
from app.shadow.causality.causality_engine import CausalityEngine
from app.shadow.governance.governance_engine import (
    GovernanceEngine, InterventionDecision, WhatIfScenario, GovernanceAction
)


@pytest.fixture
def high_risk_graph():
    """Graph with high-risk nodes."""
    graph = AgentBehaviorGraph(session_id="gov_test")
    n1 = BehaviorNode(agent_id="Agent_A", tool_name="cursor.execute", shadow_risk_score=0.1)
    n2 = BehaviorNode(agent_id="Agent_B", tool_name="send_email", shadow_risk_score=0.95)
    graph.add_node(n1)
    graph.add_node(n2)
    graph.add_edge(BehaviorEdge(from_node_id=n1.node_id, to_node_id=n2.node_id))
    return graph


@pytest.fixture
def causality_report(high_risk_graph):
    """Pre-computed causality report."""
    engine = CausalityEngine(high_risk_graph)
    return engine.analyze()


class TestGovernanceAction:
    """Test GovernanceAction enum."""

    def test_all_actions(self):
        assert GovernanceAction.BLOCK.value == "block"
        assert GovernanceAction.DEGRADE.value == "degrade"
        assert GovernanceAction.FORCE_EVIDENCE.value == "force_evidence"
        assert GovernanceAction.ESCALATE_AUDIT.value == "escalate_audit"
        assert GovernanceAction.UPDATE_RULES.value == "update_rules"
        assert GovernanceAction.ALLOW.value == "allow"
        assert GovernanceAction.WAIT.value == "wait"


class TestInterventionDecision:
    """Test InterventionDecision dataclass."""

    def test_decision_fields(self):
        decision = InterventionDecision(
            action=GovernanceAction.BLOCK,
            target_node_id="n1",
            target_agent_id="agent_1",
            rationale="High risk",
            predicted_effect=0.95,
            intervention_level="node",
        )
        assert decision.action == GovernanceAction.BLOCK
        assert decision.target_agent_id == "agent_1"
        assert decision.predicted_effect == 0.95


class TestWhatIfScenario:
    """Test WhatIfScenario dataclass."""

    def test_scenario_fields(self):
        scenario = WhatIfScenario(
            scenario_id="whatif_1",
            description="Test scenario",
            hypothetical_change={"action": "block_at_root"},
            predicted_risk_reduction=0.8,
            predicted_new_score=0.1,
            nodes_affected=["n1"],
            causal_chain_before=["n1", "n2"],
            causal_chain_after=["n1", "...(blocked)"],
            recommendation="建议采纳",
        )
        assert scenario.scenario_id == "whatif_1"
        assert scenario.predicted_risk_reduction == 0.8
        assert scenario.confidence == 0.7


class TestGovernanceEngine:
    """Test GovernanceEngine functionality."""

    def test_engine_creation(self, high_risk_graph, causality_report):
        engine = GovernanceEngine(high_risk_graph, causality_report)
        assert engine.graph == high_risk_graph
        assert engine.causality_report == causality_report

    def test_govern_returns_decisions(self, high_risk_graph, causality_report):
        engine = GovernanceEngine(high_risk_graph, causality_report)
        decisions = engine.govern()
        assert isinstance(decisions, list)

    def test_governance_report_structure(self, high_risk_graph, causality_report):
        engine = GovernanceEngine(high_risk_graph, causality_report)
        engine.govern()
        report = engine.get_governance_report()
        assert "decisions" in report
        assert "whatif_scenarios" in report

    def test_high_risk_node_blocked(self, high_risk_graph, causality_report):
        engine = GovernanceEngine(high_risk_graph, causality_report)
        decisions = engine.govern()
        # The high-risk node (score 0.95) should be blocked
        blocked = [d for d in decisions if d.action == GovernanceAction.BLOCK]
        assert len(blocked) > 0


class TestGovernanceEngineThresholds:
    """Test governance threshold constants."""

    def test_block_threshold(self):
        assert GovernanceEngine.BLOCK_THRESHOLD == 0.90

    def test_chain_block_threshold(self):
        assert GovernanceEngine.CHAIN_BLOCK_THRESHOLD == 0.50

    def test_degrade_threshold(self):
        assert GovernanceEngine.DEGRADE_THRESHOLD == 0.30

    def test_amplification_alert(self):
        assert GovernanceEngine.AMPLIFICATION_ALERT == 2.0


class TestGovernanceEngineRecordOutcome:
    """Test outcome recording."""

    def test_record_outcome(self, high_risk_graph, causality_report):
        engine = GovernanceEngine(high_risk_graph, causality_report)
        decisions = engine.govern()
        if decisions:
            outcome = engine.record_outcome(
                decisions[0],
                actual_risk_after=0.2,
                original_risk=0.95,
            )
            assert "decision_action" in outcome
            assert "actual_effectiveness" in outcome
            assert outcome["effective"] is True

    def test_record_outcome_ineffective(self, high_risk_graph, causality_report):
        engine = GovernanceEngine(high_risk_graph, causality_report)
        decisions = engine.govern()
        if decisions:
            outcome = engine.record_outcome(
                decisions[0],
                actual_risk_after=0.9,
                original_risk=0.95,
            )
            assert outcome["effective"] is False
