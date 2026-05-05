# AgentShield V2 - 数据库工具调用审计

> **V1 已封版** = AI 输出合规审计基座  
> **V2 目标** = 数据库工具调用审计扩展

## 核心定位

在数据库工具调用**真正执行前**，通过影子预演预测数据外泄风险并触发熔断。

## 最小 Demo 场景

```
财务Agent 试图执行：
  cursor.execute("SELECT phone, id_card, address FROM customers")
  send_email(to="external@company.com", attachment=data)

预期结果：
  shadow_risk_score >= 0.90 → fuse_action = "block"
```

## 演进路线

```
V1：输出审计基座（幻觉检测 + RAG溯源 + 风险熵 + 硬门控）
V2：工具调用审计（数据库影子预演 + 数据资产识别 + 熔断）
V3：多Agent行为链治理平台（输出 + 工具 + 全链路）
```

## 目录结构

```
agent-shield-v2/
├── backend/
│   └── app/
│       ├── __init__.py
│       ├── tool_call.py                    # 标准化请求 + 审计引擎门面
│       └── shadow/
│           └── database/
│               ├── sql_analyzer.py          # SQL解析（表/列/WHERE/敏感字段）
│               ├── database_shadow_simulator.py  # 影子预演引擎
│               └── database_shadow_risk_scorer.py # 风险评分（0.0~1.0）
├── tests/
│   └── test_database_shadow.py              # 核心测试套件
└── README.md
```

## 核心能力目标

| 能力 | 目标 |
|------|------|
| 工具调用拦截 | `ToolCallRequest` 标准化 |
| 数据库影子预演 | 识别表、字段、导出、影响行数 |
| 数据资产识别 | `customers` / `phone` / `id_card` / `address` / `bank_account` |
| 风险评分 | `shadow_risk_score >= 0.90` → 触发熔断 |
| 熔断动作 | `block` 或 `human_review` |
| 审计记录 | 写入完整 `RiskProfile`（AuditLogEntry） |

## 风险评分维度

| 因子 | 权重 | 说明 |
|------|------|------|
| 敏感数据 | 30% | 命中的敏感字段×表组合 |
| 数据量 | 20% | 影响行数、数据体积 |
| 批量操作 | 20% | 无WHERE / LIMIT>100 |
| 外部传输 | 25% | email/webhook/ftp等外发 |
| 操作类型 | 5% | SELECT/INSERT/UPDATE/DELETE |

## 运行测试

```bash
cd D:\ZYY Project\agent-shield-v2
python -m pytest tests/test_database_shadow.py -v
```

## V2 封版基座（5个核心文件）

1. **`app/tool_call.py`** - 审计引擎门面，协调全流程
2. **`app/shadow/database/sql_analyzer.py`** - SQL结构解析
3. **`app/shadow/database/database_shadow_simulator.py`** - 影子预演引擎
4. **`app/shadow/database/database_shadow_risk_scorer.py`** - 风险评分器
5. **`tests/test_database_shadow.py`** - 核心测试用例

---

**下一步**：V2 前端页面（财务Agent敏感数据导出拦截可视化）
