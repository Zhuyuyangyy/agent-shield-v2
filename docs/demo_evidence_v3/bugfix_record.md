# AgentShield V3 Bug Fix Record
## 研发过程真实痕迹

---

## Bug 1: What-if 场景数为 0

### 发现场景
运行 demo 时，Layer 3 生成了 2 个治理决策（1 block + 2 allow），但 `whatif_scenarios` 始终为空列表。

### 根因定位
`causality_engine.py` 第 106 行，`_identify_causal_chains()` 方法中：

```python
# 错误代码
has_child = any(e.to_node_id == node.node_id for e in self.graph.edges)
```

问题：`e.to_node_id` 是"指向该节点"的边的起点，不是"该节点指向的"边的起点。

- `to_node_id`：被指向的节点（即子节点）
- `from_node_id`：指向别人的节点（即父节点）

因此 `has_child` 永远为 `False`，所有节点都被识别为 leaf，导致 `critical_chains` 为空，What-if 场景数为 0。

### 修复方案

```python
# 正确代码
has_child = any(e.from_node_id == node.node_id for e in self.graph.edges)
```

含义：只要存在从该节点出发的边，该节点就不是叶子节点（叶子节点 = 没有出边的节点）。

### 修复文件
`backend/app/shadow/causality/causality_engine.py`

### 验证
修复后 demo 输出：
```
What-if scenarios: 2
  whatif_block_early_chain_node_988: 建议采纳（风险降低 97.5%）
  whatif_threshold_raise_chain_node_988: 不建议（风险仅降低 3.1%）
```

---

## Bug 2: WhatIfScenario 实例化报错

### 发现场景
在某些参数组合下，governance_engine 启动时抛出 `TypeError: ... argument has default value` 错误。

### 根因定位
`governance_engine.py` 第 74-75 行，第二次 `WhatIfScenario` 类定义中字段顺序错误：

```python
# 错误代码（字段顺序）
@dataclass
class WhatIfScenario:
    scenario_id: str
    recommendation: str              # ← 无默认值
    confidence: float = 0.7          # ← 有默认值（但写在后面）
    ...
```

Python 要求：无默认值的字段必须在有默认值的字段之前。

### 修复方案

调整字段顺序，将 `confidence` 移至 `recommendation` 之前：

```python
@dataclass
class WhatIfScenario:
    scenario_id: str
    confidence: float = 0.7          # 有默认值在前
    recommendation: str = ""          # 无默认值在后
    ...
```

### 修复文件
`backend/app/shadow/governance/governance_engine.py`

### 验证
修复后所有 WhatIfScenario 实例化正常，2 个 what-if 场景正确生成。

---

## Bug 3: Demo 文件被 WSL 路径写入损坏

### 发现场景
通过 `patch` 工具修改 `tests/test_v3_demo.py` 时，文件被写入 null 字节，内容长度为 0。

### 根因定位
项目路径 `/mnt/d/ZYY Project/agent-shield-v2/` 包含空格（"ZYY Project"）。`patch` 工具在处理含空格路径时产生编码错误。

### 修复方案
使用 Python 脚本 + `write_file` 工具（不走 bash heredoc）重写 demo 文件：

```python
# 全部文件写入改用 write_file 工具
# 不通过 bash 管道或 heredoc
```

### 修复文件
`tests/test_v3_demo.py`（完全重写）

### 教训
含空格路径的项目文件，所有写入操作都用 `write_file` 工具而非 bash heredoc。

---

## Bug 4: Graph 节点字段名不一致

### 发现场景
Demo 打印层读取 `n['status']` 和 `n['shadow_risk_score']` 抛出 KeyError。

### 根因定位
`AgentBehaviorGraph.to_graph_dict()` 实际输出字段为：
- `risk_status`（不是 `status`）
- `risk_score`（不是 `shadow_risk_score`）
- 边字段为 `from`/`to` 节点 ID（不是 `from_agent`/`to_agent`）

### 修复方案
Demo 中使用正确的字段名，并在打印边时用 `node_to_agent` 映射表将节点 ID 转回 agent 名称。

---

## 共同教训

1. **先验证 schema 再用 schema**：所有 dict key 访问前，先用 `python3 -c "import json; print(json.dumps(obj, indent=2))"` 打印实际结构。
2. **含空格路径不用 bash heredoc**：WSL 下路径有空格时，所有文件写入用 `write_file` 工具。
3. **Dataclass 字段顺序**：有默认值的字段不能写在无默认值字段前面。
4. **因果推理关键易错点**：`from_node_id` = 出发方向，`to_node_id` = 到达方向；判断"是否有子节点"用 `from_node_id`。
