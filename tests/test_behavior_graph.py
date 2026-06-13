"""
test_behavior_graph.py
======================
Comprehensive tests for AgentBehaviorGraph (V3 Layer 1).
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
from app.shadow.behavior.agent_behavior_graph import (
    AgentBehaviorGraph, BehaviorNode, BehaviorEdge, NodeRiskStatus
)


@pytest.fixture
def graph():
    return AgentBehaviorGraph(session_id="test_session")


class TestBehaviorNode:
    """Test BehaviorNode dataclass."""

    def test_node_creation(self):
        node = BehaviorNode(agent_id="agent_1", tool_name="cursor.execute")
        assert node.agent_id == "agent_1"
        assert node.tool_name == "cursor.execute"
        assert node.node_id is not None
        assert node.shadow_risk_score == 0.0
        assert node.fuse_action == "allow"

    def test_node_default_values(self):
        node = BehaviorNode()
        assert node.agent_id == "unknown"
        assert node.risk_status == NodeRiskStatus.SAFE
        assert node.downstream_risk_amplified is False
        assert node.intervention_count == 0
        assert node.inherited_risk == 0.0

    def test_node_unique_ids(self):
        node1 = BehaviorNode()
        node2 = BehaviorNode()
        assert node1.node_id != node2.node_id

    def test_is_risk_amplifier(self):
        node = BehaviorNode()
        assert node.is_risk_amplifier() is False
        node.downstream_risk_amplified = True
        assert node.is_risk_amplifier() is True

    def test_to_summary(self):
        node = BehaviorNode(
            agent_id="agent_1",
            tool_name="cursor.execute",
            shadow_risk_score=0.75,
        )
        summary = node.to_summary()
        assert summary["agent_id"] == "agent_1"
        assert summary["tool_name"] == "cursor.execute"
        assert summary["risk_score"] == 0.75
        assert "node_id" in summary
        assert "fuse_action" in summary


class TestBehaviorEdge:
    """Test BehaviorEdge dataclass."""

    def test_edge_creation(self):
        edge = BehaviorEdge(from_node_id="n1", to_node_id="n2")
        assert edge.from_node_id == "n1"
        assert edge.to_node_id == "n2"
        assert edge.edge_type == "calls"
        assert edge.risk_flow == 0.0

    def test_edge_unique_ids(self):
        edge1 = BehaviorEdge(from_node_id="n1", to_node_id="n2")
        edge2 = BehaviorEdge(from_node_id="n1", to_node_id="n2")
        assert edge1.edge_id != edge2.edge_id

    def test_to_summary(self):
        edge = BehaviorEdge(
            from_node_id="n1",
            to_node_id="n2",
            edge_type="data_flow",
            risk_flow=0.5,
        )
        summary = edge.to_summary()
        assert summary["from"] == "n1"
        assert summary["to"] == "n2"
        assert summary["type"] == "data_flow"
        assert summary["risk_flow"] == 0.5


class TestAgentBehaviorGraphAddNode:
    """Test node addition."""

    def test_add_single_node(self, graph):
        node = BehaviorNode(agent_id="agent_1")
        result = graph.add_node(node)
        assert result.node_id == node.node_id
        assert len(graph.nodes) == 1

    def test_add_multiple_nodes(self, graph):
        for i in range(5):
            graph.add_node(BehaviorNode(agent_id=f"agent_{i}"))
        assert len(graph.nodes) == 5

    def test_add_duplicate_node_updates(self, graph):
        node = BehaviorNode(agent_id="agent_1", shadow_risk_score=0.5)
        graph.add_node(node)
        node.shadow_risk_score = 0.8
        graph.add_node(node)
        assert len(graph.nodes) == 1
        assert graph.nodes[node.node_id].shadow_risk_score == 0.8


class TestAgentBehaviorGraphAddEdge:
    """Test edge addition."""

    def test_add_edge(self, graph):
        n1 = BehaviorNode(agent_id="agent_1")
        n2 = BehaviorNode(agent_id="agent_2")
        graph.add_node(n1)
        graph.add_node(n2)
        edge = BehaviorEdge(from_node_id=n1.node_id, to_node_id=n2.node_id)
        result = graph.add_edge(edge)
        assert result.edge_id == edge.edge_id
        assert len(graph.edges) == 1

    def test_add_edge_invalid_from(self, graph):
        n2 = BehaviorNode(agent_id="agent_2")
        graph.add_node(n2)
        edge = BehaviorEdge(from_node_id="nonexistent", to_node_id=n2.node_id)
        with pytest.raises(ValueError):
            graph.add_edge(edge)

    def test_add_edge_invalid_to(self, graph):
        n1 = BehaviorNode(agent_id="agent_1")
        graph.add_node(n1)
        edge = BehaviorEdge(from_node_id=n1.node_id, to_node_id="nonexistent")
        with pytest.raises(ValueError):
            graph.add_edge(edge)

    def test_add_duplicate_edge(self, graph):
        n1 = BehaviorNode(agent_id="agent_1")
        n2 = BehaviorNode(agent_id="agent_2")
        graph.add_node(n1)
        graph.add_node(n2)
        edge = BehaviorEdge(from_node_id=n1.node_id, to_node_id=n2.node_id)
        graph.add_edge(edge)
        graph.add_edge(edge)
        assert len(graph.edges) == 1


class TestAgentBehaviorGraphToolCall:
    """Test add_tool_call_as_node."""

    def test_add_tool_call(self, graph):
        node = graph.add_tool_call_as_node(
            agent_id="agent_1",
            tool_name="cursor.execute",
            params_summary="SELECT * FROM customers",
            fuse_action="block",
            shadow_risk_score=0.95,
        )
        assert node.agent_id == "agent_1"
        assert node.tool_name == "cursor.execute"
        assert len(graph.nodes) == 1

    def test_add_tool_call_with_parent(self, graph):
        n1 = graph.add_tool_call_as_node(
            agent_id="agent_1",
            tool_name="cursor.execute",
            params_summary="SELECT 1",
            fuse_action="allow",
            shadow_risk_score=0.1,
        )
        n2 = graph.add_tool_call_as_node(
            agent_id="agent_2",
            tool_name="send_email",
            params_summary="send data",
            fuse_action="block",
            shadow_risk_score=0.95,
            parent_node_id=n1.node_id,
        )
        assert len(graph.nodes) == 2
        assert len(graph.edges) == 1

    def test_add_tool_call_with_labels(self, graph):
        node = graph.add_tool_call_as_node(
            agent_id="agent_1",
            tool_name="cursor.execute",
            params_summary="SELECT 1",
            fuse_action="allow",
            shadow_risk_score=0.1,
            labels=["low_risk", "test"],
        )
        assert "low_risk" in node.labels


class TestAgentBehaviorGraphQueries:
    """Test graph query methods."""

    def test_get_node(self, graph):
        node = BehaviorNode(agent_id="agent_1")
        graph.add_node(node)
        assert graph.get_node(node.node_id) == node

    def test_get_nonexistent_node(self, graph):
        assert graph.get_node("nonexistent") is None

    def test_get_session_nodes(self, graph):
        for i in range(3):
            graph.add_node(BehaviorNode(agent_id=f"agent_{i}"))
        nodes = graph.get_session_nodes()
        assert len(nodes) == 3

    def test_get_critical_nodes(self, graph):
        n1 = BehaviorNode(agent_id="agent_1", shadow_risk_score=0.8)
        n1.downstream_risk_amplified = True
        n2 = BehaviorNode(agent_id="agent_2", shadow_risk_score=0.3)
        graph.add_node(n1)
        graph.add_node(n2)
        critical = graph.get_critical_nodes(threshold=0.5)
        assert len(critical) == 1
        assert critical[0].node_id == n1.node_id

    def test_get_downstream_nodes(self, graph):
        n1 = BehaviorNode(agent_id="agent_1")
        n2 = BehaviorNode(agent_id="agent_2")
        n3 = BehaviorNode(agent_id="agent_3")
        graph.add_node(n1)
        graph.add_node(n2)
        graph.add_node(n3)
        graph.add_edge(BehaviorEdge(from_node_id=n1.node_id, to_node_id=n2.node_id))
        graph.add_edge(BehaviorEdge(from_node_id=n2.node_id, to_node_id=n3.node_id))
        downstream = graph.get_downstream_nodes(n1.node_id)
        assert len(downstream) == 2


class TestAgentBehaviorGraphRiskPropagation:
    """Test risk propagation computation."""

    def test_risk_propagation_empty(self, graph):
        result = graph.compute_risk_propagation()
        assert result == {}

    def test_risk_propagation_single_node(self, graph):
        node = BehaviorNode(agent_id="agent_1", shadow_risk_score=0.5)
        graph.add_node(node)
        result = graph.compute_risk_propagation()
        assert node.node_id in result

    def test_risk_propagation_chain(self, graph):
        n1 = BehaviorNode(agent_id="agent_1", shadow_risk_score=0.3)
        n2 = BehaviorNode(agent_id="agent_2", shadow_risk_score=0.8)
        graph.add_node(n1)
        graph.add_node(n2)
        graph.add_edge(BehaviorEdge(from_node_id=n1.node_id, to_node_id=n2.node_id))
        result = graph.compute_risk_propagation()
        assert n1.node_id in result
        assert n2.node_id in result


class TestAgentBehaviorGraphExport:
    """Test graph export."""

    def test_to_graph_dict(self, graph):
        n1 = BehaviorNode(agent_id="agent_1", shadow_risk_score=0.5)
        graph.add_node(n1)
        result = graph.to_graph_dict()
        assert "session_id" in result
        assert "nodes" in result
        assert "edges" in result
        assert "critical_nodes" in result
        assert len(result["nodes"]) == 1

    def test_summary(self, graph):
        n1 = BehaviorNode(agent_id="agent_1", shadow_risk_score=0.95)
        n1.fuse_action = "block"
        graph.add_node(n1)
        summary = graph.summary()
        assert summary["total_nodes"] == 1
        assert summary["blocked_count"] == 1


class TestNodeRiskStatus:
    """Test NodeRiskStatus enum."""

    def test_all_statuses(self):
        assert NodeRiskStatus.SAFE.value == "safe"
        assert NodeRiskStatus.LOW.value == "low"
        assert NodeRiskStatus.MEDIUM.value == "medium"
        assert NodeRiskStatus.HIGH.value == "high"
        assert NodeRiskStatus.CRITICAL.value == "critical"
        assert NodeRiskStatus.UNKNOWN.value == "unknown"
