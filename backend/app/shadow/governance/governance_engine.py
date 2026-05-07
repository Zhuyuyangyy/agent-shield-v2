"""GovernanceEngine - V3 Layer 3
===================================
治理引擎：基于因果推断结果执行干预决策 + 反事实推演。

核心能力：
1. Governance Action Selection（治理动作选择）
   - 阻断（block）：直接终止工具调用
   - 降权（degrade）：降低 Agent 权限/提高阈值
   - 强制 RAG 补证（force_evidence）：要求补充证据链
   - 审计追踪（audit_trace）：升级到完整行为链审计
   - 规则更新（rule_update）：基于本次事件更新规则库

2. What-if Counterfactual Simulation（反事实推演）
   - "如果我提前干预 X 节点，风险会不会下降？"
   - "如果提高某类工具的风险阈值，会减少多少误伤？"
   - 返回 what-if 场景描述 + 预测结果

3. Evolution Feedback（演化反馈）
   - 记录本次干预是否有效
   - 自动调整规则阈值（半自动）

这一层回答：
- 风险来了，系统该怎么做？
- 如果提前阻断，后果会不会更好？
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class GovernanceAction(Enum):
    BLOCK = "block"                          # 阻断当前调用
    DEGRADE = "degrade"                      # 降权（提高该Agent后续门槛）
    FORCE_EVIDENCE = "force_evidence"        # 强制RAG补证
    ESCALATE_AUDIT = "escalate_audit"        # 升级到行为链审计
    UPDATE_RULES = "update_rules"           # 更新规则库
    ALLOW = "allow"                          # 放行（但记录）
    WAIT = "wait"                            # 暂停，等待人工确认


@dataclass
class InterventionDecision:
    """
    一次治理干预决策
    """
    action: GovernanceAction
    target_node_id: str
    target_agent_id: str
    rationale: str
    predicted_effect: float     # 预测干预效果（0.0~1.0，风险降低幅度）
    intervention_level: str     # node / chain / session / global
    timestamp: datetime = field(default_factory=datetime.now)
    rule_update: Optional[dict] = None  # 如果 action == UPDATE_RULES，附带规则更新


@dataclass
class WhatIfScenario:
    """
    反事实推演场景
    """
    scenario_id: str
    description: str                    # 自然语言描述
    hypothetical_change: dict           # 假设性变更内容
    # 假设变更后，预期结果：
    predicted_risk_reduction: float    # 风险降低幅度（0.0~1.0）
    predicted_new_score: float          # 假设变更后的影子风险分
    nodes_affected: list[str]          # 受影响节点
    causal_chain_before: list[str]      # 变更前的因果链
    causal_chain_after: list[str]       # 变更后的因果链（预测）
    recommendation: str                 # 建议采纳吗？
    confidence: float = 0.7             # 预测置信度
    recommendation: str                 # 建议采纳吗？
    confidence: float = 0.7             # 预测置信度
    timestamp: datetime = field(default_factory=datetime.now)


class GovernanceEngine:
    """
    治理引擎

    接收 CausalityEngine 的归因结果 + AgentBehaviorGraph，
    输出：
    - 干预决策（InterventionDecision）
    - 反事实场景（WhatIfScenario）

    治理策略表（硬编码 demo 逻辑）：
    - 节点 risk_score >= 0.90 → 阻断
    - 节点 inherited_risk >= 0.50 → 阻断整条链
    - 节点 downstream_risk_amplified == True → 降权该Agent
    - 因果链 amplification_factor > 2.0 → 强制补证 + 规则更新
    """

    # 治理阈值
    BLOCK_THRESHOLD = 0.90           # >= 此分直接阻断
    CHAIN_BLOCK_THRESHOLD = 0.50     # inherited_risk >= 此值，阻断整条链
    DEGRADE_THRESHOLD = 0.30         # downstream_risk_amplified 且 inherited >= 此值，降权
    AMPLIFICATION_ALERT = 2.0        # 放大倍数 >= 此值，触发规则更新

    def __init__(self, graph, causality_report: dict):
        self.graph = graph
        self.causality_report = causality_report
        self.decisions: list[InterventionDecision] = []
        self.whatif_scenarios: list[WhatIfScenario] = []

    # ─── 主治理入口 ────────────────────────────────────────

    def govern(self) -> list[InterventionDecision]:
        """
        主治理流程：
        1. 对每个高风险节点，根据治理策略做出干预决策
        2. 生成反事实场景
        3. 返回所有决策
        """
        # 1. 从因果报告中提取高风险节点
        for attr in self.causality_report.get("root_cause_attributions", []):
            node_id = attr["node_id"]
            node = self.graph.get_node(node_id)
            if not node:
                continue

            # 2. 根据治理策略表选择动作
            decision = self._select_intervention(node, attr)
            if decision:
                self.decisions.append(decision)

        # 3. 为每个高风险链生成 what-if 场景
        self._generate_whatif_scenarios()

        return self.decisions

    def _select_intervention(
        self, node, attr: dict
    ) -> Optional[InterventionDecision]:
        """
        根据节点风险属性，从治理策略表中选择最优动作
        """
        inherited = attr.get("inherited", 0.0)
        direct = attr.get("direct", node.shadow_risk_score)
        chain_len = attr.get("chain_length", 0)
        amplification = 1.0

        # 找该节点的 amplification_factor
        for chain in self.causality_report.get("critical_chains", []):
            if chain.get("root_agent") == attr.get("agent_id"):
                amplification = chain.get("amplification", 1.0)
                break

        # ── 策略选择 ──
        if direct >= self.BLOCK_THRESHOLD:
            action = GovernanceAction.BLOCK
            rationale = (
                f"节点风险分 {direct:.2f} >= {self.BLOCK_THRESHOLD}，直接阻断。"
            )
            predicted_effect = 0.95

        elif inherited >= self.CHAIN_BLOCK_THRESHOLD and chain_len > 0:
            action = GovernanceAction.BLOCK
            rationale = (
                f"继承风险 {inherited:.2f} >= {self.CHAIN_BLOCK_THRESHOLD}，"
                f"且因果链长度 {chain_len}，阻断整条调用链。"
            )
            predicted_effect = 0.85

        elif (node.downstream_risk_amplified
              and inherited >= self.DEGRADE_THRESHOLD):
            action = GovernanceAction.DEGRADE
            rationale = (
                f"节点为风险放大器（继承风险 {inherited:.2f}），"
                f"降低 Agent {node.agent_id} 权限并提高后续调用阈值。"
            )
            predicted_effect = 0.70

        elif amplification >= self.AMPLIFICATION_ALERT:
            action = GovernanceAction.UPDATE_RULES
            rationale = (
                f"因果链放大倍数 {amplification:.2f} >= {self.AMPLIFICATION_ALERT}，"
                f"触发规则自动更新，更新阈值配置。"
            )
            predicted_effect = 0.60
            rule_update = self._build_rule_update(node)
        else:
            action = GovernanceAction.ALLOW
            rationale = (
                f"节点风险可控（直接 {direct:.2f}，继承 {inherited:.2f}），"
                f"记录审计日志后放行。"
            )
            predicted_effect = 0.0
            rule_update = None

        decision = InterventionDecision(
            action=action,
            target_node_id=node.node_id,
            target_agent_id=node.agent_id,
            rationale=rationale,
            predicted_effect=predicted_effect,
            intervention_level="chain" if chain_len > 0 else "node",
            rule_update=rule_update if action == GovernanceAction.UPDATE_RULES else None,
        )
        return decision

    def _build_rule_update(self, node) -> dict:
        """
        生成规则更新内容（用于 UPDATE_RULES 动作）
        """
        tool_name = node.tool_name
        # 模拟：根据该节点的事件，生成新的规则条目
        return {
            "new_rule": {
                "condition": f'tool_name contains "{tool_name}"',
                "condition_type": "tool_pattern",
                "risk_threshold_raise": 0.10,  # 该模式的风险阈值提高 0.10
                "applies_to_agent": node.agent_id,
                "reason": f"因果链放大风险事件触发，tool={tool_name}",
                "auto_generated": True,
                "timestamp": datetime.now().isoformat(),
            },
            "affected_tools": [tool_name],
            "estimated_impact": "该类工具调用的人工复核率预计提高 20%",
        }

    # ─── 反事实推演 ────────────────────────────────────────

    def _generate_whatif_scenarios(self):
        """
        基于当前因果链，生成 what-if 反事实推演场景

        Demo 生成 3 类：
        1. "如果早期阻断这条链" → 预测整条链风险降到多少
        2. "如果提高阈值" → 预测误伤率变化
        3. "如果降权该 Agent" → 预测后续调用行为变化
        """
        chains = self.causality_report.get("critical_chains", [])
        if not chains:
            return

        for chain in chains[:3]:  # 最多 3 条链
            root_agent = chain.get("root_agent", "unknown")
            amplification = chain.get("amplification", 1.0)
            terminal_risk = chain.get("terminal_risk", 0.0)
            trajectory = chain.get("trajectory", [])

            # ── What-if 1: 早期阻断 ──
            if len(trajectory) >= 2:
                hypothetical_risk = trajectory[0] * 0.5  # 早期阻断后风险降到一半
                scenario1 = WhatIfScenario(
                    scenario_id=f"whatif_block_early_{chain['chain_id']}",
                    description=(
                        f"如果在因果链早期（root_agent={root_agent}）实施阻断，"
                        f"终端风险 {terminal_risk:.2f} 预计降至 {hypothetical_risk:.2f}。"
                    ),
                    hypothetical_change={
                        "action": "block_at_root",
                        "target": root_agent,
                        "mechanism": "在第一个节点直接阻断，不让它传播到下游",
                    },
                    predicted_risk_reduction=round(1 - hypothetical_risk / (terminal_risk + 0.001), 3),
                    predicted_new_score=round(hypothetical_risk, 3),
                    nodes_affected=trajectory,
                    causal_chain_before=trajectory,
                    causal_chain_after=[trajectory[0], "...(blocked)"],
                    confidence=0.75,
                    recommendation=(
                        "建议采纳：早期阻断的干预效果显著（风险降低 "
                        f"{1 - hypothetical_risk / (terminal_risk + 0.001):.0%}），"
                        "且对正常业务影响最小。"
                        if 1 - hypothetical_risk / (terminal_risk + 0.001) > 0.5
                        else "效果有限，建议结合其他治理动作。"
                    ),
                )
                self.whatif_scenarios.append(scenario1)

            # ── What-if 2: 提高阈值 ──
            new_threshold = self.BLOCK_THRESHOLD + 0.05
            scenario2 = WhatIfScenario(
                scenario_id=f"whatif_threshold_raise_{chain['chain_id']}",
                description=(
                    f"如果将阻断阈值从 {self.BLOCK_THRESHOLD} 提高到 {new_threshold}，"
                    f"当前链的 {terminal_risk:.2f} 分是否仍会被阻断？"
                ),
                hypothetical_change={
                    "action": "raise_threshold",
                    "from": self.BLOCK_THRESHOLD,
                    "to": new_threshold,
                },
                predicted_risk_reduction=round(max(0, terminal_risk - new_threshold) / (terminal_risk + 0.001), 3),
                predicted_new_score=terminal_risk,
                nodes_affected=[chain.get("root_agent", "")],
                causal_chain_before=trajectory,
                causal_chain_after=trajectory,
                confidence=0.60,
                recommendation=(
                    "不建议：提高阈值会增加漏检风险，"
                    "当前阈值的敏感性是合理的。"
                    if terminal_risk >= new_threshold
                    else "提高阈值后该链将绕过阻断，请结合降权动作。"
                ),
            )
            self.whatif_scenarios.append(scenario2)

    # ─── 演化反馈 ────────────────────────────────────────

    def record_outcome(
        self,
        decision: InterventionDecision,
        actual_risk_after: float,
        original_risk: float,
    ) -> dict:
        """
        记录干预结果，用于半自动规则演化。
        比较干预前后的实际风险，更新规则权重。
        """
        effectiveness = (
            (original_risk - actual_risk_after) / (original_risk + 0.001)
        )

        outcome = {
            "decision_action": decision.action.value,
            "predicted_effect": decision.predicted_effect,
            "actual_effectiveness": round(effectiveness, 3),
            "effective": effectiveness > 0.3,
            "adjustment": None,
        }

        # 如果实际效果偏离预测超过 30%，建议调整规则
        if abs(effectiveness - decision.predicted_effect) > 0.30:
            adjustment = {
                "reason": "预测偏差过大，触发规则微调",
                "threshold_shift": round(
                    (decision.predicted_effect - effectiveness) * 0.1, 4
                ),
                "note": "仅做微调，避免过度调整导致规则震荡",
            }
            outcome["adjustment"] = adjustment

        return outcome

    # ─── 报告生成 ────────────────────────────────────────

    def get_governance_report(self) -> dict:
        """
        生成完整治理报告
        """
        return {
            "decisions": [
                {
                    "action": d.action.value,
                    "target_node": d.target_node_id,
                    "target_agent": d.target_agent_id,
                    "rationale": d.rationale,
                    "predicted_effect": d.predicted_effect,
                    "level": d.intervention_level,
                    "rule_update": d.rule_update,
                    "timestamp": d.timestamp.isoformat(),
                }
                for d in self.decisions
            ],
            "whatif_scenarios": [
                {
                    "scenario_id": s.scenario_id,
                    "description": s.description,
                    "hypothetical_change": s.hypothetical_change,
                    "predicted_risk_reduction": s.predicted_risk_reduction,
                    "predicted_new_score": s.predicted_new_score,
                    "confidence": s.confidence,
                    "recommendation": s.recommendation,
                    "timestamp": s.timestamp.isoformat(),
                }
                for s in self.whatif_scenarios
            ],
        }
