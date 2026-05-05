"""
DatabaseShadowSimulator
=======================
数据库影子预演引擎：在真实执行前预测工具调用对数据库的影响

通过 SQL 结构分析 + 启发式规则 估算：
- 涉及的表和字段
- 影响行数
- 是否为敏感数据导出
- 外部传输意图
"""

from dataclasses import dataclass, field
from typing import Optional


# ─── 数据资产敏感度表 ─────────────────────────────────────────
# 表名 → (敏感度权重, 典型敏感字段)
TABLE_SENSITIVITY = {
    "customers":          (0.95, ["phone", "id_card", "address", "email", "bank_account"]),
    "users":              (0.90, ["password", "phone", "email", "name"]),
    "patient_records":    (1.00, ["medical_record", "diagnosis", "treatment", "ssn"]),
    "employee_salary":    (0.98, ["salary", "bank_account", "name", "id_card"]),
    "contracts":          (0.85, ["contract_content", "price", "party_a", "party_b"]),
    "transactions":       (0.88, ["amount", "account", "counterparty", "timestamp"]),
    "orders":             (0.80, ["customer_id", "product", "quantity", "price"]),
    "logs":               (0.20, ["timestamp", "action"]),
}


# ─── 高风险操作模式库 ─────────────────────────────────────────
DANGEROUS_OPERATIONS = [
    # 批量导出
    ("SELECT",  0.95, "BULK_SELECT",  "无限制SELECT全表数据"),
    # 外部传输
    ("SEND_EMAIL", 1.00, "EXTERNAL_TRANSFER", "尝试通过邮件外发数据"),
    # 文件写出
    ("EXPORT_CSV", 0.95, "FILE_EXPORT", "CSV/文件导出敏感数据"),
    # 跨库查询
    ("CROSS_DB", 0.90, "CROSS_DATABASE", "跨数据库访问敏感表"),
]


@dataclass
class ShadowEffect:
    """
    影子预演结果
    """
    predicted_tables: list[str]              # 预测会访问的表
    predicted_columns: list[str]            # 预测会访问的列
    affected_rows_estimate: int            # 估算影响行数
    sensitive_fields_detected: list[str]   # 检测到的敏感字段
    data_volume_mb: float                  # 估算数据量(MB)
    is_external_transfer: bool             # 是否外部传输
    is_bulk_operation: bool               # 是否批量操作
    risk_indicators: list[str]             # 风险指标列表
    summary: str                           # 人类可读摘要


class DatabaseShadowSimulator:
    """
    数据库影子预演器
    通过启发式分析预测工具调用效果，不依赖真实数据库连接
    """

    def simulate(
        self,
        tool_name: str,
        params: dict,
        sql_info,  # SQLInfo from SQLAnalyzer
    ) -> ShadowEffect:
        """
        主模拟入口
        """
        sql = params.get("sql", "")
        tables = sql_info.tables if sql_info else []
        operation = sql_info.operation if sql_info else "UNKNOWN"
        selected_cols = sql_info.selected_columns if sql_info else []
        is_bulk = sql_info.is_bulk_query if sql_info else False
        sensitive_fields = sql_info.sensitive_fields_detected if sql_info else []

        # ─── 1. 基础预测 ───────────────────────────────────
        predicted_tables = tables or self._guess_tables_from_sql(sql)
        predicted_columns = selected_cols or self._guess_columns_from_sql(sql)

        # ─── 2. 影响行数估算 ─────────────────────────────────
        affected_rows = self._estimate_affected_rows(sql, is_bulk, operation)

        # ─── 3. 敏感字段检测 ─────────────────────────────────
        detected_sensitive = self._merge_sensitive(
            sensitive_fields,
            predicted_columns,
            predicted_tables,
        )

        # ─── 4. 数据量估算 ───────────────────────────────────
        data_volume = self._estimate_data_volume(
            affected_rows, predicted_columns, predicted_tables
        )

        # ─── 5. 外部传输检测 ─────────────────────────────────
        is_external = self._detect_external_transfer(tool_name, params)

        # ─── 6. 风险指标收集 ─────────────────────────────────
        risk_indicators = self._collect_risk_indicators(
            tool_name, operation, is_bulk, detected_sensitive,
            is_external, affected_rows, predicted_tables,
        )

        # ─── 7. 摘要生成 ─────────────────────────────────────
        summary = self._generate_summary(
            operation, predicted_tables, affected_rows,
            detected_sensitive, is_external,
        )

        return ShadowEffect(
            predicted_tables=predicted_tables,
            predicted_columns=predicted_columns,
            affected_rows_estimate=affected_rows,
            sensitive_fields_detected=detected_sensitive,
            data_volume_mb=data_volume,
            is_external_transfer=is_external,
            is_bulk_operation=is_bulk or affected_rows > 100,
            risk_indicators=risk_indicators,
            summary=summary,
        )

    def _guess_tables_from_sql(self, sql: str) -> list[str]:
        """从SQL推断表名"""
        import re
        tables = []
        for m in re.finditer(r'\bFROM\b\s+([\w]+)', sql, re.IGNORECASE):
            tables.append(m.group(1))
        return tables

    def _guess_columns_from_sql(self, sql: str) -> list[str]:
        """从SQL推断列名"""
        import re
        cols = []
        m = re.search(r'\bSELECT\s+(.+?)\s+\bFROM\b', sql, re.IGNORECASE)
        if m:
            cols = [c.strip() for c in m.group(1).split(",")]
        return cols

    def _estimate_affected_rows(
        self, sql: str, is_bulk: bool, operation: str
    ) -> int:
        """估算影响行数"""
        import re
        if is_bulk or "WHERE" not in sql.upper():
            return 100_000  # 全表估算
        # 有LIMIT的情况
        m = re.search(r'\bLIMIT\s+(\d+)', sql, re.IGNORECASE)
        if m:
            return min(int(m.group(1)), 10_000)
        # SELECT 无 WHERE → 全表
        if "SELECT" in sql.upper() and "WHERE" not in sql.upper():
            return 50_000
        # 有 WHERE 但 LIMIT 未指定 → 保守估算1000行
        return 1_000

    def _merge_sensitive(
        self,
        sql_detected: list[str],
        columns: list[str],
        tables: list[str],
    ) -> list[str]:
        """
        合并多源敏感字段检测结果
        核心原则：只对敏感表（TABLE_SENSITIVITY中的表）的字段做敏感标记
        """
        all_sensitive = set()

        # 来自SQL分析器的结果（仅当格式为"table.column"时才采纳）
        for item in sql_detected:
            if "." in item:
                # 有表名前缀，可信
                all_sensitive.add(item)
            # 无表名/无category前缀 → 不可信，由表×字段交叉检测补充

        # 通过表名×字段名交叉检测（唯一可信路径）
        sensitive_tables = {t.lower() for t in TABLE_SENSITIVITY}
        for table in tables:
            table_lower = table.lower()
            if table_lower not in sensitive_tables:
                continue  # 非敏感表，跳过
            _, sensitive_fields = TABLE_SENSITIVITY[table_lower]
            for col in columns:
                col_lower = col.lower()
                for sf in sensitive_fields:
                    if sf in col_lower or col_lower in sf:
                        all_sensitive.add(f"{table}.{sf}")

        return sorted(list(all_sensitive))

    def _estimate_data_volume(
        self, rows: int, columns: list[str], tables: list[str]
    ) -> float:
        """估算数据量(MB)，平均每行1KB"""
        if not columns:
            col_count = len(tables) * 5  # 默认每表5列
        else:
            col_count = len(columns)
        bytes_per_row = col_count * 50  # 平均每字段50字节
        total_bytes = rows * bytes_per_row
        return round(total_bytes / (1024 * 1024), 3)

    def _detect_external_transfer(self, tool_name: str, params: dict) -> bool:
        """检测是否为外部传输（高风险指标）"""
        external_markers = [
            "email", "mailto", "smtp", "send", "webhook",
            "upload", "external", "ftp", "sftp", "remote",
        ]
        tool_lower = tool_name.lower()
        params_str = str(params).lower()
        return any(m in tool_lower or m in params_str for m in external_markers)

    def _collect_risk_indicators(
        self,
        tool_name: str,
        operation: str,
        is_bulk: bool,
        sensitive_fields: list[str],
        is_external: bool,
        affected_rows: int,
        tables: list[str],
    ) -> list[str]:
        """收集所有风险指标"""
        indicators = []
        if is_bulk:
            indicators.append("BULK_QUERY")
        if is_external:
            indicators.append("EXTERNAL_TRANSFER")
        if sensitive_fields:
            indicators.append(f"SENSITIVE_FIELDS:{len(sensitive_fields)}")
        if affected_rows > 1000:
            indicators.append(f"BULK_EXPORT:{affected_rows}_rows")
        if "customers" in [t.lower() for t in tables]:
            indicators.append("CUSTOMER_TABLE_ACCESS")
        if "salary" in str(sensitive_fields).lower() or "bank" in str(sensitive_fields).lower():
            indicators.append("FINANCIAL_DATA_ACCESS")
        return indicators

    def _generate_summary(
        self,
        operation: str,
        tables: list[str],
        affected_rows: int,
        sensitive: list[str],
        is_external: bool,
    ) -> str:
        """生成人类可读摘要"""
        table_str = ",".join(tables) if tables else "unknown"
        sensitive_str = f"[{','.join(sensitive[:3])}]" if sensitive else ""
        external_str = " [EXTERNAL]" if is_external else ""
        return (
            f"{operation} on {table_str} "
            f"~{affected_rows:,} rows {sensitive_str}{external_str}"
        )
