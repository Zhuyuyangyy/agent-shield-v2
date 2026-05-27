#!/bin/bash
# agent-shield-v2 启动脚本
# AI安全工具调用审计引擎 - 运行测试套件

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=============================================="
echo "  AgentShield-v2 - 工具调用审计引擎"
echo "  Database Shadow Architecture"
echo "=============================================="
echo

# 虚拟环境
VENV_DIR="$SCRIPT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

pip install -q pytest pyyaml 2>/dev/null

echo "[启动] 运行测试套件..."
echo
python3 -m pytest tests/ -v --tb=short