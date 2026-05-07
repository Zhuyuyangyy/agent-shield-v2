"""CausalityEngine - V3 Layer 2
===================================
因果推断引擎：识别关键风险节点、计算归因、追踪风险扩散路径。

核心能力：
1. 关键风险节点识别（Root Cause Attribution）
2. 风险扩散路径追踪（Risk Diffusion Tracking）
3. 风险加权因果图（Causal Graph with Risk Weights）
4. "哪个 Agent 导致系统失控"的归因答案

这层回答：哪个节点是风险根源？风险沿哪条路径扩散？
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..behavior.agent_behavior_graph import AgentBehaviorGraph, BehaviorNode, BehaviorEdge


@dataclass
class RiskAttribution:
    """
    风险归因结果：哪个节点对风险事件负责
    """
    responsible_node_id: str
    responsible_agent_id: str
    responsibility_score: float          # 0.0~1.0，这个节点要负责多少
    direct_risk_contribution: float      # 该节点自身的风险
    inherited_risk_contribution: float   # 该节点继承自上游的风险
    chain_length: int                   # 到风险爆发点的距离
    causal_path: list[str]              # 从该节点到风险爆发点的路径节点IDs
    explanation: str                    # 自然语言解释


@dataclass
class CausalChain:
    """
    一条因果链：从风险根源到风险事件的完整路径
    """
    chain_id: str
    root_node_id: str
    root_agent_id: str
    terminal_node_id: str              # 风险爆发的节点
    terminal_risk_score: float
    chain_risk_trajectory: list[float]  # 沿路径的风险分变化
    amplification_factor: float        # 整条链路的风险放大倍数
    weak_links: list[str]              # 薄弱节点（应该被干预却没有干预的）


class CausalityEngine:
    """
    因果推断引擎

    输入：AgentBehaviorGraph（图谱）
    输出：
    - 每个高风险节点的归因结果
    - 关键因果链
    - 风险扩散的薄弱环节
    """

    # 风险放大阈值：某节点 inherited_risk * 此系数 > shadow_risk → 放大器
    AMPLIFICATION_THRESHOLD = 1.2

    # 关键节点阈值：归因得分 > 此值视为关键风险根源
    ROOT_CAUSE_THRESHOLD = 0.4

    def __init__(self, graph: AgentBehaviorGraph):
        self.graph = graph
        # 预先计算风险传播（已在 graph.compute_risk_propagation() 中完成）
        self._risk_map: dict[str, float] = {}
        # 保存归因结果（避免重复计算）
        self._attributions: dict[str, RiskAttribution] = {}
        self._causal_chains: list[CausalChain] = []

    def analyze(self) -> dict:
        """
        主分析入口：运行完整因果分析
        返回结构化分析报告
        """
        # 1. 计算风险传播
        self._risk_map = self.graph.compute_risk_propagation()

        # 2. 识别关键因果链
        self._causal_chains = self._identify_causal_chains()

        # 3. 对每个高风险节点做归因
        high_risk_nodes = [
            n for n in self.graph.get_session_nodes()
            if n.shadow_risk_score >= 0.70 or n.inherited_risk >= 0.30
        ]
        for node in high_risk_nodes:
            self._attributions[node.node_id] = self._attribute_risk(node)

        return self.get_report()

    def _identify_causal_chains(self) -> list[CausalChain]:
        """
        识别所有从低风险根源到高风险爆发的因果链
        """
        chains = []
        nodes = self.graph.get_session_nodes()

        # 找所有叶子节点（风险爆发点）
        has_child = {edge.from_node_id for edge in self.graph.edges.values()}
        leaf_nodes = [n for n in nodes if n.node_id not in has_child]

        for leaf in leaf_nodes:
            if leaf.shadow_risk_score < 0.50:
                continue

            # 逆向追溯到根源
            path = self._trace_back_to_root(leaf.node_id)
            if len(path) < 2:
                continue

            # 计算整条链的风险放大倍数
            node_ids = [p["node_id"] for p in path]
            scores = [self._risk_map.get(nid, 0.0) for nid in node_ids]
            if scores and scores[0] > 0:
                amplification = max(scores) / scores[0]
            else:
                amplification = 1.0

            chain = CausalChain(
                chain_id=f"chain_{leaf.node_id[:8]}",
                root_node_id=path[0]["node_id"],
                root_agent_id=path[0]["agent_id"],
                terminal_node_id=leaf.node_id,
                terminal_risk_score=leaf.shadow_risk_score,
                chain_risk_trajectory=scores,
                amplification_factor=round(amplification, 3),
                weak_links=self._find_weak_links_in_path(path),
            )
            chains.append(chain)

        # 按风险放大倍数排序
        chains.sort(key=lambda c: c.amplification_factor, reverse=True)
        return chains

    def _trace_back_to_root(self, node_id: str) -> list[dict]:
        """
        逆向追溯：从某节点一直追溯到风险根源（inherited_risk 最低的祖先）
        """
        # 建立 to → from 的反向邻接表
        reverse_adj: dict[str, list[str]] = {nid: [] for nid in self.graph.nodes}
        for edge in self.graph.edges.values():
            reverse_adj[edge.to_node_id].append(edge.from_node_id)

        path = []
        current_id = node_id

        # 最多追溯 10 步
        for _ in range(10):
            if current_id not in self.graph.nodes:
                break
            node = self.graph.nodes[current_id]
            path.append({"node_id": node.node_id, "agent_id": node.agent_id})
            parents = reverse_adj.get(current_id, [])
            if not parents:
                break
            # 选择 inherited_risk 最高的父节点（最接近根源）
            best_parent = max(parents, key=lambda pid: self.graph.nodes[pid].inherited_risk)
            current_id = best_parent

        path.reverse()
        return path

    def _find_weak_links_in_path(self, path: list[dict]) -> list[str]:
        """
        找到路径中的薄弱环节：
        inherited_risk > 0.2 但 fuse_action == "allow" 的节点
        （应该被干预却放过了）
        """
        weak = []
        for p in path:
            node = self.graph.nodes.get(p["node_id"])
            if not node:
                continue
            if node.inherited_risk > 0.2 and node.fuse_action == "allow":
                weak.append(node.node_id)
        return weak

    def _attribute_risk(self, node: BehaviorNode) -> RiskAttribution:
        """
        对单个高风险节点做归因：
        它自身有多少风险是从上游继承的？哪个父节点是真正的根源？
        """
        # 建立 to → from 的反向邻接表
        reverse_adj: dict[str, list[str]] = {nid: [] for nid in self.graph.nodes}
        for edge in self.graph.edges.values():
            reverse_adj[edge.to_node_id].append(edge.from_node_id)

        # 找所有上游父节点
        parents = reverse_adj.get(node.node_id, [])

        if not parents:
            # 孤立节点，自身是根源
            return RiskAttribution(
                responsible_node_id=node.node_id,
                responsible_agent_id=node.agent_id,
                responsibility_score=1.0,
                direct_risk_contribution=node.shadow_risk_score,
                inherited_risk_contribution=0.0,
                chain_length=0,
                causal_path=[node.node_id],
                explanation=(
                    f"Agent {node.agent_id} 的工具调用 {node.tool_name} "
                    f"为风险根源，自身风险分 {node.shadow_risk_score:.2f}。"
                ),
            )

        # 计算各父节点的贡献度
        total_inherited = sum(self.graph.nodes[pid].inherited_risk for pid in parents if pid in self.graph.nodes)

        # 归因到最 responsible 的父节点
        responsible_parent_id = max(
            parents,
            key=lambda pid: self.graph.nodes[pid].inherited_risk if pid in self.graph.nodes else 0.0
        )
        responsible_parent = self.graph.nodes.get(responsible_parent_id)

        # 追溯因果路径
        causal_path_ids = [node.node_id]
        current_id = responsible_parent_id
        for _ in range(10):
            causal_path_ids.insert(0, current_id)
            parents_of_parent = reverse_adj.get(current_id, [])
            if not parents_of_parent:
                break
            current_id = max(
                parents_of_parent,
                key=lambda pid: self.graph.nodes[pid].inherited_risk if pid in self.graph.nodes else 0.0
            )
            if current_id in causal_path_ids:  # 避免循环
                break

        responsibility_score = (
            responsible_parent.inherited_risk / (node.inherited_risk + 0.001)
            if node.inherited_risk > 0 else 0.0
        )

        explanation = (
            f"Agent {responsible_parent.agent_id} 的 {responsible_parent.tool_name} "
            f"（风险分 {responsible_parent.shadow_risk_score:.2f}）导致下游 "
            f"Agent {node.agent_id} 的 {node.tool_name} 风险上升至 {node.shadow_risk_score:.2f}。"
            f"继承风险 {node.inherited_risk:.2f}，因果链长度 {len(causal_path_ids)}。"
        )

        return RiskAttribution(
            responsible_node_id=responsible_parent_id,
            responsible_agent_id=responsible_parent.agent_id if responsible_parent else node.agent_id,
            responsibility_score=round(min(responsibility_score, 1.0), 3),
            direct_risk_contribution=node.shadow_risk_score,
            inherited_risk_contribution=node.inherited_risk,
            chain_length=len(causal_path_ids),
            causal_path=causal_path_ids,
            explanation=explanation,
        )

    def get_report(self) -> dict:
        """
        生成结构化因果分析报告
        """
        return {
            "graph_summary": self.graph.summary(),
            "critical_chains": [
                {
                    "chain_id": c.chain_id,
                    "root_agent": c.root_agent_id,
                    "terminal_risk": c.terminal_risk_score,
                    "amplification": c.amplification_factor,
                    "weak_links": c.weak_links,
                    "trajectory": c.chain_risk_trajectory,
                }
                for c in self._causal_chains[:5]  # 最多 5 条关键链
            ],
            "root_cause_attributions": [
                {
                    "node_id": node_id,
                    "agent_id": attr.responsible_agent_id,
                    "responsibility": attr.responsibility_score,
                    "direct": round(attr.direct_risk_contribution, 3),
                    "inherited": round(attr.inherited_risk_contribution, 3),
                    "chain_length": attr.chain_length,
                    "explanation": attr.explanation,
                }
                for node_id, attr in sorted(
                    self._attributions.items(),
                    key=lambda x: x[1].responsibility_score,
                    reverse=True
                )
            ],
        }
