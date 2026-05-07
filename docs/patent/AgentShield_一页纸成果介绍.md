# AgentShield 一页纸成果介绍

---

## 项目名称

**AgentShield** — AI Agent 多通道风险治理平台

---

## 一句话定位

> AgentShield 是面向 AI Agent 的"输出—工具—行为链"三通道安全治理系统，实现从"说什么"到"做什么"再到"多个 Agent 如何共同导致风险"的全链路审计与干预。

---

## 核心创新（4 项）

| # | 创新点 | 技术定位 |
|---|---|---|
| 1 | **输出—工具双通道审计框架** | V1+V2，Prompt/Response 审计 + 工具调用影子预演 |
| 2 | **Hard-Gate Override** | 避免高风险输出被普通加权评分误放行的硬门控机制 |
| 3 | **Tool-Call Shadow Simulation** | 在真实执行前预测 SQL/邮件/API 调用的风险后果 |
| 4 | **Behavior-Chain Governance** | V3：多 Agent 行为链图 + 因果归因 + What-if 反事实治理 |

---

## 技术架构（三代演进）

```
V1 输出审计     V2 工具调用影子模拟    V3 行为链治理
[Prompt]        [SQL/Email/API]        [Multi-Agent Graph]
   ↓                ↓                      ↓
[Output Audit]  [Shadow Simulation]     [Causal Attribution]
   ↓                ↓                      ↓
[Hard-Gate]     [Risk Score + Fuse]     [What-if Simulation]
                                                  ↓
                                           [Governance Decision]
                                                  ↓
                                           [BLOCK/ALLOW/MONITOR]
```

---

## 核心指标

| 指标 | 数值 | 说明 |
|---|---|---|
| 高风险 SQL 拦截率 | 100% | sensitive_customer_query: 0.901 blocked |
| 安全 SQL 放行率 | 100% | safe_product_query: 0.051 allowed |
| 外部邮件拦截 | 1/1 | 含客户数据的外部发送行为被阻断 |
| 批量操作预警 | 触发 | bulk SELECT 触发 human_review |
| 因果链识别 | 1 条 | FinancialAgent → CustomerDataAgent → EmailAgent |
| What-if 推演 | 2 场景 | 1 建议采纳（早期阻断降低风险 97.5%） |

---

## 适用场景

| 行业 | 场景 | AgentShield 价值 |
|---|---|---|
| 政务大模型 | 政策查询 + 数据调取 | 防止敏感数据通过 Agent 工具调用外泄 |
| 金融 | 基金分析 + 报表生成 | 防止 SQL 注入和客户数据导出 |
| 医疗 | 病历查询 + 处方生成 | 防止患者隐私数据通过 Agent 行为链泄露 |
| 企业办公 | 邮件发送 + 文件导出 | 防止内部数据被 Agent 批量发送到外部 |
| 数据分析 | SQL 查询 + 报告导出 | 防止分析 Agent 执行高风险数据操作 |

---

## 成果状态

| 成果类型 | 状态 | 说明 |
|---|---|---|
| V1+V2 专利交底书 | ✅ 完成 | 843行，含权要书/证据索引/实施例 |
| V3 扩展专利 | 🔄 证据已封版 | 待写交底书 |
| 代码基线 | ✅ 已 tag | agentshield-v3-evidence-baseline |
| V1 证据 | ✅ 2 条 | 输出幻觉拦截/放行 |
| V2 证据 | ✅ 5 条 | SQL/邮件/批量操作拦截 |
| V3 证据 | ✅ 7 条 | 行为图/因果归因/What-if/统一报告 |
| SCI 论文 | 🔄 框架已定 | 待扩 Benchmark 到 100 条 |
| 产品 Demo | 🔄 可演示 | 5 面板治理平台 |

---

## 竞品对比

| 维度 | 传统风控 | 现有 Agent 框架 | AgentShield |
|---|---|---|---|
| 审计时机 | 事后 | 事前（弱） | **事前预演 + 事中拦截** |
| 审计粒度 | API 级别 | 单次工具调用 | **行为链级别** |
| 高风险误放行 | 常见 | 可能 | **Hard-Gate 兜底** |
| 多 Agent 风险 | 无法处理 | 无 | **行为链图 + 因果归因** |
| 反事实推演 | 无 | 无 | **What-if 治理模拟** |

---

## 学术价值

- **论文方向：** Agent Governance / AI Safety / Responsible AI
- **发表目标：** SCI / EI 期刊或会议
- **核心贡献：** 提出首个覆盖"输出—工具—行为链"三通道的 AI Agent 风险治理框架

---

## 下一步里程碑

```
当前 → 专利提交代理人（本周）
     → V3 扩展专利交底书（下周）
     → Benchmark 扩至 100 条
     → SCI Abstract + Introduction 初稿
     → 产品 Demo 5 面板完成
```

---

## 联系方式

**项目：** AgentShield
**版本：** V1 + V2 已封版，V3 证据已封版
**Git tag：** agentshield-v3-evidence-baseline
**专利申请日：** 2026-05-05

---
