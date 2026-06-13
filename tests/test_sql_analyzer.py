"""
test_sql_analyzer.py
====================
Comprehensive unit tests for SQLAnalyzer.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
from app.shadow.database.sql_analyzer import SQLAnalyzer, SQLInfo, SENSITIVE_FIELD_PATTERNS


@pytest.fixture
def analyzer():
    return SQLAnalyzer()


class TestSQLAnalyzerBasicParsing:
    """Test basic SQL parsing functionality."""

    def test_analyze_select_simple(self, analyzer):
        sql = "SELECT name, email FROM users WHERE id = 1"
        result = analyzer.analyze(sql)
        assert result.operation == "SELECT"
        assert "users" in result.tables
        assert "name" in result.selected_columns
        assert "email" in result.selected_columns

    def test_analyze_insert(self, analyzer):
        sql = "INSERT INTO orders (product_id, quantity, price) VALUES (1, 10, 99.9)"
        result = analyzer.analyze(sql)
        assert result.operation == "INSERT"
        assert "orders" in result.tables

    def test_analyze_update(self, analyzer):
        sql = "UPDATE customers SET phone = '123' WHERE id = 5"
        result = analyzer.analyze(sql)
        assert result.operation == "UPDATE"
        assert "customers" in result.tables

    def test_analyze_delete(self, analyzer):
        sql = "DELETE FROM logs WHERE timestamp < '2024-01-01'"
        result = analyzer.analyze(sql)
        assert result.operation == "DELETE"
        assert "logs" in result.tables

    def test_analyze_unknown_operation(self, analyzer):
        sql = "DROP TABLE users"
        result = analyzer.analyze(sql)
        assert result.operation == "UNKNOWN"

    def test_analyze_empty_string(self, analyzer):
        result = analyzer.analyze("")
        assert result.operation == "UNKNOWN"
        assert result.tables == []
        assert result.selected_columns == []

    def test_analyze_none(self, analyzer):
        result = analyzer.analyze(None)
        assert result.operation == "UNKNOWN"
        assert result.tables == []

    def test_analyze_non_string(self, analyzer):
        result = analyzer.analyze(12345)
        assert result.operation == "UNKNOWN"


class TestSQLAnalyzerTableExtraction:
    """Test table name extraction."""

    def test_extract_single_table(self, analyzer):
        sql = "SELECT * FROM customers"
        result = analyzer.analyze(sql)
        assert "customers" in result.tables

    def test_extract_multiple_tables_from_join(self, analyzer):
        sql = "SELECT a.name, b.order_id FROM customers a JOIN orders b ON a.id = b.customer_id"
        result = analyzer.analyze(sql)
        assert "customers" in result.tables
        assert "orders" in result.tables

    def test_extract_insert_into(self, analyzer):
        sql = "INSERT INTO transactions (amount, account) VALUES (100, 'ACC001')"
        result = analyzer.analyze(sql)
        assert "transactions" in result.tables

    def test_extract_update_table(self, analyzer):
        sql = "UPDATE employee_salary SET salary = 5000 WHERE id = 1"
        result = analyzer.analyze(sql)
        assert "employee_salary" in result.tables

    def test_extract_delete_from(self, analyzer):
        sql = "DELETE FROM patient_records WHERE id = 100"
        result = analyzer.analyze(sql)
        assert "patient_records" in result.tables


class TestSQLAnalyzerColumnExtraction:
    """Test column name extraction."""

    def test_extract_specific_columns(self, analyzer):
        sql = "SELECT phone, id_card, address FROM customers"
        result = analyzer.analyze(sql)
        assert "phone" in result.selected_columns
        assert "id_card" in result.selected_columns
        assert "address" in result.selected_columns

    def test_extract_star_excluded(self, analyzer):
        sql = "SELECT * FROM customers"
        result = analyzer.analyze(sql)
        assert "*" not in result.selected_columns

    def test_extract_columns_with_aggregation(self, analyzer):
        sql = "SELECT COUNT(*) as cnt, name FROM users GROUP BY name"
        result = analyzer.analyze(sql)
        assert "name" in result.selected_columns
        assert "COUNT" not in result.selected_columns

    def test_no_columns_for_insert(self, analyzer):
        sql = "INSERT INTO orders (product_id) VALUES (1)"
        result = analyzer.analyze(sql)
        # INSERT doesn't have SELECT columns
        assert result.selected_columns == []


class TestSQLAnalyzerWhereConditions:
    """Test WHERE condition extraction."""

    def test_extract_simple_where(self, analyzer):
        sql = "SELECT * FROM users WHERE id = 1"
        result = analyzer.analyze(sql)
        assert len(result.where_conditions) > 0

    def test_extract_compound_where(self, analyzer):
        sql = "SELECT * FROM users WHERE id = 1 AND status = 'active'"
        result = analyzer.analyze(sql)
        assert len(result.where_conditions) >= 2

    def test_no_where_clause(self, analyzer):
        sql = "SELECT * FROM users"
        result = analyzer.analyze(sql)
        assert result.where_conditions == []

    def test_where_with_or(self, analyzer):
        sql = "SELECT * FROM users WHERE id = 1 OR id = 2"
        result = analyzer.analyze(sql)
        assert len(result.where_conditions) >= 2


class TestSQLAnalyzerBulkDetection:
    """Test bulk query detection."""

    def test_bulk_no_where(self, analyzer):
        sql = "SELECT * FROM customers"
        result = analyzer.analyze(sql)
        assert result.is_bulk_query is True

    def test_not_bulk_with_where(self, analyzer):
        sql = "SELECT * FROM customers WHERE id = 1"
        result = analyzer.analyze(sql)
        assert result.is_bulk_query is False

    def test_not_bulk_with_small_limit(self, analyzer):
        sql = "SELECT * FROM customers LIMIT 50"
        result = analyzer.analyze(sql)
        assert result.is_bulk_query is False

    def test_bulk_with_large_limit(self, analyzer):
        sql = "SELECT * FROM customers LIMIT 500"
        result = analyzer.analyze(sql)
        assert result.is_bulk_query is True


class TestSQLAnalyzerSensitiveFields:
    """Test sensitive field detection."""

    def test_detect_phone_field(self, analyzer):
        sql = "SELECT phone, name FROM customers WHERE id = 1"
        result = analyzer.analyze(sql)
        assert any("phone" in s for s in result.sensitive_fields_detected)

    def test_detect_id_card_field(self, analyzer):
        sql = "SELECT id_card FROM customers WHERE id = 1"
        result = analyzer.analyze(sql)
        assert any("id_card" in s for s in result.sensitive_fields_detected)

    def test_detect_bank_account(self, analyzer):
        sql = "SELECT bank_account FROM customers WHERE id = 1"
        result = analyzer.analyze(sql)
        assert any("bank" in s for s in result.sensitive_fields_detected)

    def test_no_sensitive_in_non_sensitive_table(self, analyzer):
        sql = "SELECT name FROM products WHERE id = 1"
        result = analyzer.analyze(sql)
        assert result.sensitive_fields_detected == []

    def test_sensitive_field_patterns_exist(self):
        """Verify sensitive field patterns are defined."""
        assert "phone" in SENSITIVE_FIELD_PATTERNS
        assert "id_card" in SENSITIVE_FIELD_PATTERNS
        assert "bank_account" in SENSITIVE_FIELD_PATTERNS
        assert "password" in SENSITIVE_FIELD_PATTERNS
        assert "salary" in SENSITIVE_FIELD_PATTERNS
        assert "medical_record" in SENSITIVE_FIELD_PATTERNS


class TestSQLAnalyzerAggregation:
    """Test aggregation detection."""

    def test_detect_count(self, analyzer):
        sql = "SELECT COUNT(*) FROM customers"
        result = analyzer.analyze(sql)
        assert result.has_aggregation is True

    def test_detect_sum(self, analyzer):
        sql = "SELECT SUM(amount) FROM transactions"
        result = analyzer.analyze(sql)
        assert result.has_aggregation is True

    def test_no_aggregation(self, analyzer):
        sql = "SELECT name FROM customers"
        result = analyzer.analyze(sql)
        assert result.has_aggregation is False


class TestSQLAnalyzerJoin:
    """Test JOIN detection."""

    def test_detect_inner_join(self, analyzer):
        sql = "SELECT * FROM customers JOIN orders ON customers.id = orders.customer_id"
        result = analyzer.analyze(sql)
        assert result.has_join is True

    def test_detect_left_join(self, analyzer):
        sql = "SELECT * FROM customers LEFT JOIN orders ON customers.id = orders.customer_id"
        result = analyzer.analyze(sql)
        assert result.has_join is True

    def test_no_join(self, analyzer):
        sql = "SELECT * FROM customers"
        result = analyzer.analyze(sql)
        assert result.has_join is False


class TestSQLInfoDataclass:
    """Test SQLInfo dataclass structure."""

    def test_sqlinfo_fields(self, analyzer):
        sql = "SELECT phone FROM customers WHERE id = 1"
        result = analyzer.analyze(sql)
        assert hasattr(result, 'tables')
        assert hasattr(result, 'operation')
        assert hasattr(result, 'selected_columns')
        assert hasattr(result, 'where_conditions')
        assert hasattr(result, 'has_aggregation')
        assert hasattr(result, 'has_join')
        assert hasattr(result, 'is_bulk_query')
        assert hasattr(result, 'sensitive_fields_detected')
