.PHONY: help install dev build deploy deploy-frontend deploy-backend deploy-full \
       push gh-pages server-restart server-logs server-status

# ========== 配置 ==========
SERVER_HOST  := root@49.234.192.249
SERVER_PASS  := 1Root@tooR1
SERVER_DIR   := /opt/m78-djs
SSH_CMD      := sshpass -p '$(SERVER_PASS)' ssh -o StrictHostKeyChecking=no -o PubkeyAuthentication=no $(SERVER_HOST)
SCP_CMD      := sshpass -p '$(SERVER_PASS)' scp -o StrictHostKeyChecking=no -o PubkeyAuthentication=no

help:
	@echo "白马梯级轮动策略 - 回测系统"
	@echo ""
	@echo "本地开发："
	@echo "  make install          安装所有依赖 (Python + Node.js)"
	@echo "  make dev              一键启动后端 + 前端开发服务"
	@echo "  make build            构建前端 (GitHub Pages, base=/m78-djs/)"
	@echo ""
	@echo "代码推送："
	@echo "  make push             git add + commit + push 到 GitHub"
	@echo "  make gh-pages         部署前端到 GitHub Pages"
	@echo ""
	@echo "腾讯云部署："
	@echo "  make deploy           一键更新: 构建 + 推送 + 上传 + 重启"
	@echo "  make deploy-frontend  仅更新前端 (本地构建 → 上传 dist → 重启)"
	@echo "  make deploy-backend   仅更新后端 (上传 py 文件 → 重启)"
	@echo "  make deploy-full      全量部署 (代码+依赖+前端+重启)"
	@echo ""
	@echo "服务器管理："
	@echo "  make server-status    查看服务状态"
	@echo "  make server-logs      查看最近日志"
	@echo "  make server-restart   重启后端服务"
	@echo ""

# ========== 本地开发 ==========

install:
	@echo "1. 创建Python虚拟环境..."
	python3 -m venv venv
	@echo "2. 安装后端依赖..."
	@bash -c "source venv/bin/activate && pip install -r requirements.txt"
	@echo "3. 安装前端依赖..."
	@cd frontend-vite && npm install
	@echo "✓ 所有安装完成，使用 'make dev' 启动系统"

dev:
	@echo "正在启动双端服务 (Ctrl+C 退出)..."
	@echo "后端: http://127.0.0.1:8000"
	@echo "前端: http://127.0.0.1:5173"
	@trap 'kill 0' EXIT; \
	(source venv/bin/activate && python backend/app.py) & \
	(cd frontend-vite && npm run dev) & \
	wait

build:
	@cd frontend-vite && npm run build
	@echo "✓ 前端构建完成 (GitHub Pages 模式, base=/m78-djs/)"

# 腾讯云构建: base=/ 因为 Flask 直接在根路径托管
build-server:
	@cd frontend-vite && npx vite build --base=/
	@echo "✓ 前端构建完成 (服务器模式, base=/)"

# ========== 代码推送 ==========

push:
	@git add -A
	@git diff --cached --quiet && echo "没有需要提交的变更" && exit 0 || true
	@read -p "提交信息: " msg && git commit -m "$$msg"
	@git push origin main
	@echo "✓ 已推送到 GitHub"

gh-pages:
	@cd frontend-vite && npm run deploy
	@echo "✓ 已部署到 GitHub Pages"

# ========== 腾讯云部署 ==========

deploy: build-server push
	@echo ">>> 上传前端构建产物..."
	@tar czf /tmp/_m78_dist.tar.gz -C frontend-vite dist
	@$(SCP_CMD) /tmp/_m78_dist.tar.gz $(SERVER_HOST):/tmp/
	@echo ">>> 上传后端代码..."
	@tar czf /tmp/_m78_backend.tar.gz \
		--exclude='__pycache__' --exclude='*.pyc' \
		backend/ requirements.txt backtest_engine.py strategy.py \
		portfolio.py config.py data_fetcher.py indicators.py
	@$(SCP_CMD) /tmp/_m78_backend.tar.gz $(SERVER_HOST):/tmp/
	@echo ">>> 在服务器上解压并重启..."
	@$(SSH_CMD) '\
		cd $(SERVER_DIR) && \
		tar xzf /tmp/_m78_backend.tar.gz && \
		cd frontend-vite && tar xzf /tmp/_m78_dist.tar.gz && \
		cd $(SERVER_DIR) && source venv/bin/activate && \
		pip install -r requirements.txt -q 2>&1 | tail -1 && \
		systemctl restart m78-djs && \
		sleep 2 && systemctl is-active m78-djs'
	@echo "✓ 腾讯云部署完成: http://49.234.192.249:8000"

deploy-frontend: build-server
	@echo ">>> 上传前端..."
	@tar czf /tmp/_m78_dist.tar.gz -C frontend-vite dist
	@$(SCP_CMD) /tmp/_m78_dist.tar.gz $(SERVER_HOST):/tmp/
	@$(SSH_CMD) 'cd $(SERVER_DIR)/frontend-vite && tar xzf /tmp/_m78_dist.tar.gz && systemctl restart m78-djs'
	@echo "✓ 前端已更新并重启"

deploy-backend:
	@echo ">>> 上传后端代码..."
	@tar czf /tmp/_m78_backend.tar.gz \
		--exclude='__pycache__' --exclude='*.pyc' \
		backend/ requirements.txt backtest_engine.py strategy.py \
		portfolio.py config.py data_fetcher.py indicators.py
	@$(SCP_CMD) /tmp/_m78_backend.tar.gz $(SERVER_HOST):/tmp/
	@$(SSH_CMD) '\
		cd $(SERVER_DIR) && tar xzf /tmp/_m78_backend.tar.gz && \
		source venv/bin/activate && pip install -r requirements.txt -q 2>&1 | tail -1 && \
		systemctl restart m78-djs && sleep 2 && systemctl is-active m78-djs'
	@echo "✓ 后端已更新并重启"

deploy-full:
	@echo ">>> 打包全量代码（不含 db / node_modules / venv）..."
	@tar czf /tmp/_m78_full.tar.gz \
		--exclude='node_modules' --exclude='.git' --exclude='__pycache__' \
		--exclude='*.pyc' --exclude='backend/backtest.db' \
		--exclude='venv' --exclude='.venv' --exclude='results' \
		--exclude='*.xlsx' --exclude='*.csv' .
	@$(SCP_CMD) /tmp/_m78_full.tar.gz $(SERVER_HOST):/tmp/
	@echo ">>> 本地构建前端 (base=/)..."
	@cd frontend-vite && npx vite build --base=/
	@tar czf /tmp/_m78_dist.tar.gz -C frontend-vite dist
	@$(SCP_CMD) /tmp/_m78_dist.tar.gz $(SERVER_HOST):/tmp/
	@echo ">>> 服务器上解压、装依赖、重启..."
	@$(SSH_CMD) '\
		mkdir -p $(SERVER_DIR) && cd $(SERVER_DIR) && \
		tar xzf /tmp/_m78_full.tar.gz && \
		cd frontend-vite && tar xzf /tmp/_m78_dist.tar.gz && \
		cd $(SERVER_DIR) && \
		python3 -m venv venv && source venv/bin/activate && \
		pip install -r requirements.txt -q 2>&1 | tail -1 && \
		systemctl restart m78-djs && sleep 2 && systemctl is-active m78-djs'
	@echo "✓ 全量部署完成"

# ========== 服务器管理 ==========

server-status:
	@$(SSH_CMD) 'systemctl status m78-djs --no-pager | head -12'

server-logs:
	@$(SSH_CMD) 'journalctl -u m78-djs --no-pager -n 50'

server-restart:
	@$(SSH_CMD) 'systemctl restart m78-djs && sleep 2 && systemctl is-active m78-djs'
	@echo "✓ 服务已重启"
