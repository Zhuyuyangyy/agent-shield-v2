"""AgentShield V3 Facade - 统一入口
========================================
融合 V2 影子审计 + V3 因果推断 + 治理干预 + 反事实推演。

V2 核心：单次工具调用的影子预演与熔断
V3 新增：
  Layer 1 - AgentBehaviorGraph：多工具调用链的行为追踪
  Layer 2 - CausalityEngine：风险沿调用链的因果推断
  Layer 3 - GovernanceEngine：治理干预 + 反事实推演

对外暴露单一接口：AgentShieldV3.audit_chain()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .behavior.agent_behavior_graph import AgentBehaviorGraph, BehaviorNode
from .causality.causality_engine import CausalityEngine
from .governance.governance_engine import GovernanceEngine, GovernanceAction


@dataclass
class ChainAuditRequest:
    """V3 批量工具调用链审计请求"""
    session_id: str
    agent_id: str = "unknown"
    tool_call_records: list[dict] = field(default_factory=list)


@dataclass
class ChainAuditResult:
    """V3 审计结果：包含 V2 结果 + V3 因果治理结果"""
    session_id: str
    v2_summary: dict
    behavior_graph: dict
    causality_report: dict
    governance_report: dict
    overall_risk_level: str
    governance_summary: str
    timestamp: datetime = field(default_factory=datetime.now)


class AgentShieldV3:
    """
    AgentShield V3 统一审计门面

    使用方式：
        v3 = AgentShieldV3()
        result = v3.audit_chain(request)

    或者直接用 add_tool_call 逐次添加，然后用 run_governance 触发完整分析：
        v3 = AgentShieldV3(session_id="sess_001")
        v3.add_tool_call(...)   # 每次工具调用后加入
        v3.run_governance()     # 触发完整 V3 分析
        result = v3.get_result()
    """

    def __init__(self, session_id: str = "unknown"):
        self.session_id = session_id
        self.graph = AgentBehaviorGraph(session_id=session_id)
        self._processed_count = 0
        self._governance_report: Optional[dict] = None
        self._causality_report: Optional[dict] = None

    # ─── 核心 API ─────────────────────────────────────────

    def add_tool_call(
        self,
        agent_id: str,
        tool_name: str,
        params_summary: str,
        fuse_action: str,
        shadow_risk_score: float,
        parent_agent_id: Optional[str] = None,
        edge_type: str = "calls",
        inherited_risk: float = 0.0,
        labels: Optional[list[str]] = None,
    ) -> BehaviorNode:
        """
        将一次工具调用（及其审计结果）加入行为图谱。
        """
        parent_node_id = self._find_latest_node_by_agent(parent_agent_id or agent_id)

        node = self.graph.add_tool_call_as_node(
            agent_id=agent_id,
            tool_name=tool_name,
            params_summary=params_summary,
            fuse_action=fuse_action,
            shadow_risk_score=shadow_risk_score,
            parent_node_id=parent_node_id,
            edge_type=edge_type,
            inherited_risk=inherited_risk,
            labels=labels,
        )
        self._processed_count += 1
        return node

    def audit_chain(self, request: ChainAuditRequest) -> ChainAuditResult:
        """完整审计入口"""
        for record in request.tool_call_records:
            self.add_tool_call(
                agent_id=record.get("agent_id", "unknown"),
                tool_name=record.get("tool_name", ""),
                params_summary=record.get("params_summary", ""),
                fuse_action=record.get("fuse_action", "allow"),
                shadow_risk_score=record.get("shadow_risk_score", 0.0),
                parent_agent_id=record.get("parent_agent_id"),
                edge_type=record.get("edge_type", "calls"),
                inherited_risk=record.get("inherited_risk", 0.0),
                labels=record.get("labels", []),
            )

        causality_engine = CausalityEngine(self.graph)
        self._causality_report = causality_engine.analyze()

        governance_engine = GovernanceEngine(self.graph, self._causality_report)
        governance_engine.govern()
        self._governance_report = governance_engine.get_governance_report()

        overall_risk = self._compute_overall_risk()
        summary = self._generate_summary()

        return ChainAuditResult(
            session_id=request.session_id,
            v2_summary=self._v2_summary(request),
            behavior_graph=self.graph.to_graph_dict(),
            causality_report=self._causality_report,
            governance_report=self._governance_report,
            overall_risk_level=overall_risk,
            governance_summary=summary,
        )

    def run_governance(self) -> dict:
        """
        在已有图谱上运行完整的 V3 分析（用于流式追加场景）。
        返回治理报告 dict。
        """
        causality_engine = CausalityEngine(self.graph)
        self._causality_report = causality_engine.analyze()
        governance_engine = GovernanceEngine(self.graph, self._causality_report)
        governance_engine.govern()
        self._governance_report = governance_engine.get_governance_report()
        return self._governance_report

    def get_result(self) -> Optional[ChainAuditResult]:
        """获取最新治理结果（需先调用 run_governance）"""
        if not self._governance_report:
            return None
        return ChainAuditResult(
            session_id=self.session_id,
            v2_summary={},
            behavior_graph=self.graph.to_graph_dict(),
            causality_report=self._causality_report or {},
            governance_report=self._governance_report,
            overall_risk_level=self._compute_overall_risk(),
            governance_summary=self._generate_summary(),
        )

    # ─── 内部辅助 ─────────────────────────────────────────

    def _find_latest_node_by_agent(self, agent_id: str) -> Optional[str]:
        """找指定 agent 的最近一个节点"""
        nodes = self.graph.get_session_nodes()
        for node in reversed(nodes):
            if node.agent_id == agent_id:
                return node.node_id
        return None

    def _compute_overall_risk(self) -> str:
        """综合所有决策计算整体风险等级"""
        if not self._governance_report:
            return "unknown"
        decisions = self._governance_report.get("decisions", [])
        blocked = sum(1 for d in decisions if d["action"] == GovernanceAction.BLOCK.value)
        degraded = sum(1 for d in decisions if d["action"] == GovernanceAction.DEGRADE.value)

        if blocked >= 2:
            return "critical"
        elif blocked == 1:
            return "high"
        elif degraded >= 1:
            return "medium"
        elif decisions:
            return "low"
        return "safe"

    def _generate_summary(self) -> str:
        """生成自然语言总结"""
        if not self._governance_report:
            return "无治理决策。"
        decisions = self._governance_report.get("decisions", [])
        whatifs = self._governance_report.get("whatif_scenarios", [])

        block_count = sum(1 for d in decisions if d["action"] == GovernanceAction.BLOCK.value)
        degrade_count = sum(1 for d in decisions if d["action"] == GovernanceAction.DEGRADE.value)

        parts = []
        if block_count:
            parts.append(f"阻断 {block_count} 个高风险节点。")
        if degrade_count:
            parts.append(f"降权 {degrade_count} 个风险放大器 Agent。")
        if whatifs:
            adopted = sum(1 for w in whatifs if "建议采纳" in w.get("recommendation", ""))
            if adopted:
                parts.append(f"生成 {len(whatifs)} 个反事实场景，其中 {adopted} 个建议采纳。")

        return " ".join(parts) if parts else "系统风险在可控范围内，无需干预。"

    @staticmethod
    def _v2_summary(request: ChainAuditRequest) -> dict:
        """汇总 V2 审计统计"""
        records = request.tool_call_records
        return {
            "total_calls": len(records),
            "blocked": sum(1 for r in records if r.get("fuse_action") == "block"),
            "human_review": sum(1 for r in records if r.get("fuse_action") == "human_review"),
            "allowed": sum(1 for r in records if r.get("fuse_action") == "allow"),
            "avg_risk_score": (
                sum(r.get("shadow_risk_score", 0) for r in records) / max(len(records), 1)
            ),
        }
