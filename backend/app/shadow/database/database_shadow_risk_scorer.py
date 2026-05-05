"""
DatabaseShadowRiskScorer
========================
数据库工具调用影子风险评分器

基于影子预演结果计算最终风险分（0.0~1.0）
Demo目标：shadow_risk_score >= 0.90 → 触发熔断
"""

from dataclasses import dataclass
from typing import Optional


# ─── 风险因子权重 ─────────────────────────────────────────────
_WEIGHTS = {
    "sensitive_data":    0.85,   # 敏感数据权重（极高，保证含敏感字段的查询能冲上0.90+）
    "data_volume":       0.05,   # 数据量权重（次要）
    "bulk_operation":    0.05,   # 批量操作权重（次要）
    "external_transfer":  0.03,   # 外部传输权重（有专用熔断路径）
    "operation_type":    0.02,   # 操作类型权重（最低）
}


@dataclass
class RiskFactorBreakdown:
    """
    风险因子分解（调试用）
    """
    sensitive_score: float       # 敏感数据评分
    volume_score: float         # 数据量评分
    bulk_score: float           # 批量操作评分
    external_score: float       # 外部传输评分
    operation_score: float       # 操作类型评分
    total_score: float          # 总分
    dominant_factor: str         # 主控因子


class DatabaseShadowRiskScorer:
    """
    影子风险评分器
    Demo目标：财务Agent导出customers敏感数据 → score >= 0.90
    """

    # 敏感字段基础分表（表×字段组合的敏感度）
    _BASE_SENSITIVITY = {
        ("customers", "phone"):        0.95,
        ("customers", "id_card"):      1.00,
        ("customers", "address"):      0.85,
        ("customers", "email"):        0.80,
        ("customers", "bank_account"): 1.00,
        ("users", "password"):         1.00,
        ("users", "phone"):            0.90,
        ("patient_records", "medical_record"): 1.00,
        ("patient_records", "ssn"):    1.00,
        ("employee_salary", "salary"):  1.00,
        ("employee_salary", "bank_account"): 1.00,
        ("transactions", "account"):   0.95,
        ("transactions", "amount"):     0.85,
    }

    # 敏感表默认分
    _TABLE_DEFAULT_SCORES = {
        "customers":          0.90,
        "users":              0.85,
        "patient_records":    1.00,
        "employee_salary":    0.98,
        "contracts":          0.80,
        "transactions":        0.85,
    }

    def score(
        self,
        tool_name: str,
        params: dict,
        sql_info,      # SQLInfo
        simulated_effect,  # ShadowEffect
    ) -> float:
        """
        主评分入口：返回 0.0~1.0 风险分

        Demo场景验证：
        财务Agent执行:
          cursor.execute("SELECT phone, id_card, address FROM customers WHERE...")
          → shadow_risk_score >= 0.90
        """
        if simulated_effect is None:
            return 0.0

        # ─── 1. 敏感数据评分 ─────────────────────────────────
        sensitive_score = self._score_sensitive_data(
            simulated_effect.sensitive_fields_detected,
            simulated_effect.predicted_tables,
        )

        # ─── 2. 数据量评分 ───────────────────────────────────
        volume_score = self._score_data_volume(
            simulated_effect.affected_rows_estimate,
            simulated_effect.data_volume_mb,
        )

        # ─── 3. 批量操作评分 ─────────────────────────────────
        bulk_score = self._score_bulk_operation(
            simulated_effect.is_bulk_operation,
            simulated_effect.affected_rows_estimate,
        )

        # ─── 4. 外部传输评分 ─────────────────────────────────
        external_score = self._score_external_transfer(
            simulated_effect.is_external_transfer,
            tool_name,
            params,
        )

        # ─── 5. 操作类型评分 ─────────────────────────────────
        operation_score = self._score_operation_type(
            sql_info.operation if sql_info else "UNKNOWN"
        )

        # ─── 6. 加权求和 ─────────────────────────────────────
        total = (
            sensitive_score  * _WEIGHTS["sensitive_data"]    +
            volume_score    * _WEIGHTS["data_volume"]       +
            bulk_score      * _WEIGHTS["bulk_operation"]    +
            external_score  * _WEIGHTS["external_transfer"] +
            operation_score * _WEIGHTS["operation_type"]
        )

        # ─── 7. 上限钳制 ─────────────────────────────────────
        return min(round(total, 4), 1.0)

    def _score_sensitive_data(
        self,
        sensitive_fields: list[str],
        tables: list[str],
    ) -> float:
        """计算敏感数据评分（0.0~1.0）"""
        if not sensitive_fields:
            # 没有显式敏感字段，按表默认分
            scores = []
            for table in tables:
                t_lower = table.lower()
                if t_lower in self._TABLE_DEFAULT_SCORES:
                    scores.append(self._TABLE_DEFAULT_SCORES[t_lower])
            if scores:
                return max(scores)  # 取最敏感的表
            return 0.0

        # 有敏感字段，优先精确匹配 table×col 组合
        max_score = 0.0
        for field in sensitive_fields:
            field_lower = field.lower()
            # 格式1: "customers.phone" → 精确匹配
            if "." in field:
                parts = field_lower.split(".", 1)
                if len(parts) == 2:
                    key = (parts[0], parts[1])
                    if key in self._BASE_SENSITIVITY:
                        max_score = max(max_score, self._BASE_SENSITIVITY[key])
                        continue
            # 格式2: "category:field" → 在所有表×字段中模糊匹配
            for (table, col), score in self._BASE_SENSITIVITY.items():
                col_lower = col.lower()
                if col_lower in field_lower or field_lower.endswith(col_lower):
                    max_score = max(max_score, score)
        return max_score

    def _score_data_volume(self, rows: int, volume_mb: float) -> float:
        """数据量评分（0.0~1.0）"""
        if rows > 10_000 or volume_mb > 50:
            return 0.95
        elif rows > 1_000 or volume_mb > 5:
            return 0.70
        elif rows > 100:
            return 0.40
        elif rows > 10:
            return 0.15
        return 0.0

    def _score_bulk_operation(self, is_bulk: bool, rows: int) -> float:
        """批量操作评分（0.0~1.0）"""
        if is_bulk and rows > 10_000:
            return 0.95
        elif is_bulk and rows > 1_000:
            return 0.70
        elif is_bulk:
            return 0.50
        return 0.0

    def _score_external_transfer(
        self, is_external: bool, tool_name: str, params: dict
    ) -> float:
        """外部传输评分（0.0~1.0）"""
        if not is_external:
            return 0.0
        # 邮件外发最高风险
        if any(m in tool_name.lower() for m in ["email", "mailto", "smtp", "send"]):
            return 1.0
        # webhook/文件上传次高
        if any(m in tool_name.lower() for m in ["webhook", "upload", "post"]):
            return 0.90
        return 0.80

    def _score_operation_type(self, operation: str) -> float:
        """操作类型评分（0.0~1.0）"""
        op_scores = {
            "SELECT": 0.30,   # 查询，基础风险
            "INSERT": 0.50,   # 插入，中风险
            "UPDATE": 0.60,    # 更新，中高风险
            "DELETE": 0.70,    # 删除，高风险
            "UNKNOWN": 0.20,
        }
        return op_scores.get(operation, 0.20)
