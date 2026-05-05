"""
AgentShield V2 - Tool Call Audit Engine
=====================================
数据库工具调用审计：财务Agent敏感数据外泄拦截
最小Demo目标：识别 customers 表敏感字段导出的风险并触发熔断
"""

__version__ = "2.0.0"
__author__ = "Alice"

# ─── 核心模块 ───────────────────────────────────────────────────
from .tool_call import ToolCallRequest, ToolCallAuditEngine
from .shadow.database.database_shadow_simulator import DatabaseShadowSimulator
from .shadow.database.database_shadow_risk_scorer import DatabaseShadowRiskScorer
from .shadow.database.sql_analyzer import SQLAnalyzer

__all__ = [
    "ToolCallRequest",
    "ToolCallAuditEngine",
    "DatabaseShadowSimulator",
    "DatabaseShadowRiskScorer",
    "SQLAnalyzer",
]
