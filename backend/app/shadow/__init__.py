"""Shadow Module - AgentShield V2+V3"""
# V2: 影子预演引擎
from .database.sql_analyzer import SQLAnalyzer
from .database.database_shadow_simulator import DatabaseShadowSimulator, ShadowEffect
from .database.database_shadow_risk_scorer import DatabaseShadowRiskScorer

# V3: 行为图 + 因果 + 治理
from .behavior.agent_behavior_graph import AgentBehaviorGraph, BehaviorNode, BehaviorEdge
from .causality.causality_engine import CausalityEngine, RiskAttribution, CausalChain
from .governance.governance_engine import GovernanceEngine, InterventionDecision, WhatIfScenario, GovernanceAction

# V3 Facade
from .v3_facade import AgentShieldV3, ChainAuditRequest, ChainAuditResult

__all__ = [
    # V2
    "SQLAnalyzer",
    "DatabaseShadowSimulator",
    "ShadowEffect",
    "DatabaseShadowRiskScorer",
    # V3
    "AgentBehaviorGraph",
    "BehaviorNode",
    "BehaviorEdge",
    "CausalityEngine",
    "RiskAttribution",
    "CausalChain",
    "GovernanceEngine",
    "InterventionDecision",
    "WhatIfScenario",
    "GovernanceAction",
    "AgentShieldV3",
    "ChainAuditRequest",
    "ChainAuditResult",
]
