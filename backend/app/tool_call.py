"""
ToolCallRequest & ToolCallAuditEngine
====================================
标准化工具调用请求 + 审计引擎门面
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class RiskLevel(Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ToolCallRequest:
    """
    标准化工具调用请求
    """
    tool_name: str                           # e.g. "cursor.execute", "send_email"
    params: dict                             # 调用参数
    agent_id: str = "unknown"                # 调用Agent ID
    session_id: str = "unknown"              # 会话ID
    timestamp: datetime = field(default_factory=datetime.now)

    # ─── 工具类型标记 ───────────────────────────────────────────
    is_database_tool: bool = False          # 是否数据库工具
    is_network_tool: bool = False           # 是否网络工具
    is_file_tool: bool = False             # 是否文件工具

    # ─── 影子模拟结果（由AuditEngine填充） ───────────────────────
    shadow_risk_score: Optional[float] = None   # 0.0~1.0
    simulated_effect: Optional[dict] = None     # 影子预演效果
    risk_level: RiskLevel = RiskLevel.SAFE

    # ─── 熔断决策 ───────────────────────────────────────────────
    fuse_action: str = "allow"               # allow | block | human_review
    fuse_reason: str = ""
    audit_log_id: Optional[str] = None


@dataclass
class AuditLogEntry:
    """
    审计日志条目
    """
    log_id: str
    timestamp: datetime
    tool_call: ToolCallRequest
    risk_score: float
    risk_level: RiskLevel
    fuse_action: str
    fuse_reason: str
    session_id: str
    agent_id: str


class ToolCallAuditEngine:
    """
    工具调用审计引擎门面
    协调 SQLAnalyzer → DatabaseShadowSimulator → DatabaseShadowRiskScorer → FuseController
    """

    def __init__(self):
        from .shadow.database.sql_analyzer import SQLAnalyzer
        from .shadow.database.database_shadow_simulator import DatabaseShadowSimulator
        from .shadow.database.database_shadow_risk_scorer import DatabaseShadowRiskScorer

        self.sql_analyzer = SQLAnalyzer()
        self.shadow_simulator = DatabaseShadowSimulator()
        self.risk_scorer = DatabaseShadowRiskScorer()
        self.audit_log: list[AuditLogEntry] = []

    def audit(self, request: ToolCallRequest) -> ToolCallRequest:
        """
        主审计流程：
        1. 判断是否为数据库工具
        2. SQL解析 → 影子预演 → 风险评分 → 熔断决策
        3. 写入审计日志
        """
        # ─── 1. 入口判断 ─────────────────────────────────────────
        if not request.is_database_tool:
            # 非数据库工具，直接放行
            request.fuse_action = "allow"
            request.fuse_reason = "non_database_tool"
            return request

        # ─── 2. SQL解析 ─────────────────────────────────────────
        sql_info = self.sql_analyzer.analyze(request.params.get("sql", ""))

        # ─── 3. 影子预演 ───────────────────────────────────────
        request.simulated_effect = self.shadow_simulator.simulate(
            tool_name=request.tool_name,
            params=request.params,
            sql_info=sql_info,
        )

        # ─── 4. 风险评分 ───────────────────────────────────────
        request.shadow_risk_score = self.risk_scorer.score(
            tool_name=request.tool_name,
            params=request.params,
            sql_info=sql_info,
            simulated_effect=request.simulated_effect,
        )

        # ─── 5. 风险等级映射 ────────────────────────────────────
        request.risk_level = self._score_to_level(request.shadow_risk_score)

        # ─── 6. 熔断决策 ───────────────────────────────────────
        request.fuse_action, request.fuse_reason = self._fuse_decision(
            request.shadow_risk_score,
            request.simulated_effect,
            sql_info,
        )

        # ─── 7. 审计留痕 ───────────────────────────────────────
        log_entry = AuditLogEntry(
            log_id=f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
            timestamp=datetime.now(),
            tool_call=request,
            risk_score=request.shadow_risk_score,
            risk_level=request.risk_level,
            fuse_action=request.fuse_action,
            fuse_reason=request.fuse_reason,
            session_id=request.session_id,
            agent_id=request.agent_id,
        )
        self.audit_log.append(log_entry)
        request.audit_log_id = log_entry.log_id

        return request

    def _score_to_level(self, score: float) -> RiskLevel:
        if score >= 0.90:
            return RiskLevel.CRITICAL
        elif score >= 0.70:
            return RiskLevel.HIGH
        elif score >= 0.50:
            return RiskLevel.MEDIUM
        elif score >= 0.20:
            return RiskLevel.LOW
        return RiskLevel.SAFE

    def _fuse_decision(
        self, score: float, effect, sql_info
    ) -> tuple[str, str]:
        """
        熔断决策逻辑
        Demo目标：shadow_risk_score >= 0.90 → human_review 或 block
        """
        if score >= 0.90:
            # 数据外泄高风险 → 熔断
            return "block", f"HIGH_RISK_SCORE={score:.2f} score>=0.90 data_exposure"

        if effect.affected_rows_estimate > 1000:
            return "human_review", f"BULK_EXPORT detected: {effect.affected_rows_estimate} rows"

        # 检查是否命中敏感表/字段
        sensitive_hit = effect.sensitive_fields_detected
        if sensitive_hit:
            return "block", f"SENSITIVE_FIELDS={sensitive_hit} data_leakage"

        if score >= 0.70:
            return "human_review", f"MEDIUM_RISK score={score:.2f}"

        return "allow", "pass"

    def get_audit_trail(self, session_id: str) -> list[AuditLogEntry]:
        """获取指定会话的审计轨迹"""
        return [e for e in self.audit_log if e.session_id == session_id]
