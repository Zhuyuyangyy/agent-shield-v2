"""
SQLAnalyzer
===========
解析 SQL 语句，识别表名、字段名、操作类型、WHERE条件
用于 DatabaseShadowSimulator 的输入分析
"""

import re
from dataclasses import dataclass
from re import compile as re_compile
from typing import Optional

# 延迟导入避免循环依赖
from .database_shadow_simulator import TABLE_SENSITIVITY


# ─── 正则表达式 ─────────────────────────────────────────────────
_RE_SELECT_FROM = re_compile(
    r'\bSELECT\b\s+(.+?)\s+\bFROM\b\s+(\w+)', re.IGNORECASE
)
_RE_INSERT_INTO = re_compile(
    r'\bINSERT\s+INTO\b\s+(\w+)', re.IGNORECASE
)
_RE_UPDATE = re_compile(
    r'\bUPDATE\b\s+(\w+)', re.IGNORECASE
)
_RE_DELETE_FROM = re_compile(
    r'\bDELETE\s+FROM\b\s+(\w+)', re.IGNORECASE
)
_RE_SELECT_COLUMNS = re_compile(
    r'\bSELECT\b\s+(.+?)\s+\bFROM\b', re.IGNORECASE
)
_RE_WHERE = re_compile(
    r'\bWHERE\b\s+(.+?)(?:\bGROUP BY\b|\bHAVING\b|\bORDER BY\b|\bLIMIT\b|$)',
    re.IGNORECASE
)
_RE_TABLE_ALIAS = re_compile(
    r'\bFROM\b\s+(\w+)\s+(?:AS\s+)?(\w+)', re.IGNORECASE
)


# ─── 敏感字段模式库 ─────────────────────────────────────────────
SENSITIVE_FIELD_PATTERNS = {
    # 客户数据
    "phone":          ["phone", "tel", "mobile", "telephone"],
    "id_card":        ["id_card", "idcard", "identity", "身份证"],
    "address":        ["address", "location", "addr", "地址"],
    "name":           ["name", "username", "real_name", "realname", "姓名"],
    "email":          ["email", "mail", "邮箱"],
    "bank_account":   ["bank", "account", "card", "账号", "银行卡"],
    "password":       ["password", "pwd", "passwd", "secret"],
    # 财务数据
    "salary":         ["salary", "wage", "pay", "工资", "薪资"],
    "revenue":        ["revenue", "income", "profit", "收入", "营业额"],
    "contract":       ["contract", "agreement", "合同"],
    # 医疗数据
    "medical_record": ["medical", "diagnosis", "treatment", "病历", "诊断"],
    "social_security":["ssn", "social_security", "社保"],
}


@dataclass
class SQLInfo:
    """
    SQL解析结果数据结构
    """
    tables: list[str]                       # 涉及的表名列表
    operation: str                          # SELECT | INSERT | UPDATE | DELETE | UNKNOWN
    selected_columns: list[str]              # SELECT 选取的列名
    where_conditions: list[str]              # WHERE 条件片段
    has_aggregation: bool                  # 是否有聚合函数
    has_join: bool                          # 是否有JOIN
    is_bulk_query: bool                     # 是否批量查询（无WHERE / LIMIT>100）
    sensitive_fields_detected: list[str]     # 检测到的敏感字段


class SQLAnalyzer:
    """
    SQL语句解析器
    识别表名、操作类型、字段名、WHERE条件、敏感字段
    """

    def __init__(self):
        self._sensitive_patterns = self._build_patterns()

    def _build_patterns(self) -> dict[str, list[str]]:
        return SENSITIVE_FIELD_PATTERNS

    def analyze(self, sql: str) -> SQLInfo:
        """
        主解析入口
        """
        if not sql or not isinstance(sql, str):
            return SQLInfo(
                tables=[],
                operation="UNKNOWN",
                selected_columns=[],
                where_conditions=[],
                has_aggregation=False,
                has_join=False,
                is_bulk_query=False,
                sensitive_fields_detected=[],
            )

        sql_upper = sql.upper()

        # ─── 1. 识别操作类型 ─────────────────────────────────
        operation = self._detect_operation(sql_upper)

        # ─── 2. 提取表名 ───────────────────────────────────────
        tables = self._extract_tables(sql)

        # ─── 3. 提取SELECT列名 ────────────────────────────────
        selected_columns = self._extract_columns(sql)

        # ─── 4. 提取WHERE条件 ────────────────────────────────
        where_conditions = self._extract_where(sql)

        # ─── 5. 是否有聚合 ────────────────────────────────────
        has_aggregation = any(
            kw in sql_upper for kw in ["COUNT(", "SUM(", "AVG(", "MAX(", "MIN("]
        )

        # ─── 6. 是否有JOIN ───────────────────────────────────
        has_join = any(
            kw in sql_upper for kw in [" JOIN ", " LEFT JOIN ", " RIGHT JOIN ", " INNER JOIN "]
        )

        # ─── 7. 是否批量查询 ─────────────────────────────────
        is_bulk = self._is_bulk_query(sql_upper, where_conditions)
        is_bulk_query = is_bulk or len(tables) > 3  # 跨3张表以上视为批量

        # ─── 8. 敏感字段检测 ─────────────────────────────────
        sensitive_fields = self._detect_sensitive_fields(
            selected_columns + where_conditions,
            tables,
        )

        return SQLInfo(
            tables=tables,
            operation=operation,
            selected_columns=selected_columns,
            where_conditions=where_conditions,
            has_aggregation=has_aggregation,
            has_join=has_join,
            is_bulk_query=is_bulk_query,
            sensitive_fields_detected=sensitive_fields,
        )

    def _detect_operation(self, sql_upper: str) -> str:
        if "SELECT" in sql_upper:
            return "SELECT"
        if "INSERT" in sql_upper:
            return "INSERT"
        if "UPDATE" in sql_upper:
            return "UPDATE"
        if "DELETE" in sql_upper:
            return "DELETE"
        return "UNKNOWN"

    def _extract_tables(self, sql: str) -> list[str]:
        tables = []
        # FROM clause
        for m in re_compile(r'\bFROM\b\s+([\w,\s]+?)(?:\bWHERE\b|\bJOIN\b|\bLEFT\b|\bGROUP\b|\bORDER\b|\bLIMIT\b)', re.IGNORECASE).finditer(sql):
            for t in re_compile(r'\b(\w+)\b').findall(m.group(1)):
                if t.upper() not in ["WHERE", "SELECT", "ORDER", "GROUP", "HAVING"]:
                    tables.append(t)
        # INSERT INTO
        for m in re_compile(r'\bINSERT\s+INTO\b\s+([\w,\s]+?)(?:\s*[\(])', re.IGNORECASE).finditer(sql):
            for t in re_compile(r'\b(\w+)\b').findall(m.group(1)):
                tables.append(t)
        # UPDATE
        for m in re_compile(r'\bUPDATE\b\s+(\w+)', re.IGNORECASE).finditer(sql):
            tables.append(m.group(1))
        return list(dict.fromkeys(tables))  # 去重保留顺序

    def _extract_columns(self, sql: str) -> list[str]:
        """提取 SELECT 子句的列名"""
        match = re_compile(r'\bSELECT\b\s+(.+?)\s+\bFROM\b', re.IGNORECASE).search(sql)
        if not match:
            return []
        cols_str = match.group(1)
        # 去除聚合函数
        cols = re_compile(r'[\w\*]+').findall(cols_str)
        # 过滤掉 * 和聚合关键字
        return [
            c for c in cols
            if c.upper() not in ["", "*", "COUNT", "SUM", "AVG", "MAX", "MIN"]
        ]

    def _extract_where(self, sql: str) -> list[str]:
        """提取 WHERE 条件片段"""
        conditions = []
        match = re_compile(
            r'\bWHERE\b\s+(.+?)(?:\bGROUP BY\b|\bHAVING\b|\bORDER BY\b|\bLIMIT\b|$)',
            re.IGNORECASE
        ).search(sql)
        if match:
            # 简单分割AND/OR条件
            parts = re_compile(r'\b(AND|OR)\b').split(match.group(1))
            conditions = [p.strip() for p in parts if p.strip().upper() not in ["AND", "OR"]]
        return conditions

    def _is_bulk_query(self, sql_upper: str, where_conditions: list[str]) -> bool:
        """判断是否为批量查询（高风险）"""
        if "LIMIT" in sql_upper:
            # 检查 LIMIT 数量
            m = re_compile(r'\bLIMIT\s+(\d+)', re.IGNORECASE).search(sql_upper)
            if m and int(m.group(1)) <= 100:
                return False
        # 无 WHERE 条件 → 全表扫描
        if not where_conditions and "SELECT" in sql_upper:
            return True
        return False

    def _detect_sensitive_fields(
        self, columns: list[str], tables: list[str]
    ) -> list[str]:
        """
        检测敏感字段（仅限敏感表中的字段）
        只有当字段所属的表在 TABLE_SENSITIVITY 中时，才对其做字段名模式匹配
        """
        detected = []
        sensitive_tables = {t.lower() for t in TABLE_SENSITIVITY}

        # 检查是否涉及敏感表
        tables_lower = [t.lower() for t in tables]
        if not any(t in sensitive_tables for t in tables_lower):
            return []  # 无敏感表 → 不做字段名模式匹配

        all_fields = set(columns)
        for category, patterns in self._sensitive_patterns.items():
            for pattern in patterns:
                for field in all_fields:
                    field_lower = field.lower()
                    if (pattern in field_lower or
                        field_lower.endswith(pattern) or
                        pattern in field_lower.replace("_", "")):
                        detected.append(f"{category}:{field}")
        return list(set(detected))
