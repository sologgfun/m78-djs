.PHONY: help install start clean update-cookie frontend-install frontend-dev frontend-build

help:
	@echo "白马梯级轮动策略 - 回测系统"
	@echo ""
	@echo "使用方法："
	@echo "  make dev           - [推荐] 一键启动后端 + 前端开发服务"
	@echo "  make install       - 安装所有依赖 (Python + Node.js)"
	@echo "  make start-backend - 仅启动后端服务器"
	@echo "  make start-frontend- 仅启动前端开发服务器"
	@echo "  make build         - 构建前端产物"
	@echo "  make clean         - 清理缓存"
	@echo "  make update-cookie - 更新东方财富Cookie"
	@echo "  make help          - 显示帮助"
	@echo ""

install:
	@echo "1. 创建Python虚拟环境..."
	python3 -m venv venv
	@echo "2. 安装后端依赖..."
	@bash -c "source venv/bin/activate && pip install -r requirements.txt"
	@echo "3. 安装前端依赖..."
	@cd frontend-vite && npm install
	@echo "✓ 所有安装完成"
	@echo "现在可以使用 'make dev' 启动系统"

# 开发模式：同时启动前后端
dev:
	@echo "正在启动双端服务 (Ctrl+C 退出)..."
	@echo "后端: http://127.0.0.1:8000"
	@echo "前端: http://127.0.0.1:5173"
	@trap 'kill 0' EXIT; \
	(source venv/bin/activate && python backend/app.py) & \
	(cd frontend-vite && npm run dev) & \
	wait