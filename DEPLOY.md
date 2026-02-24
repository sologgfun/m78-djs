# 部署说明

## 线上地址

| 服务 | 地址 |
|------|------|
| 前端（GitHub Pages） | https://sologgfun.github.io/m78-djs/ |
| 后端（Render） | https://m78-djs.onrender.com |

---

## 架构说明

```
用户浏览器
    ↓
GitHub Pages（前端静态页面）
    ↓ /api/* 请求
Render（Python Flask 后端）
    ↓
SQLite 数据库 / AkShare 数据源
```

---

## 日常更新

### 更新前端

修改 `frontend-vite/src/` 下的代码后，在项目根目录执行：

```bash
cd frontend-vite
npm run deploy
```

这条命令会自动完成：构建 → 发布到 GitHub Pages。发布后约 1 分钟生效。

### 更新后端

修改 `backend/` 下的代码后，推送到 GitHub，Render 会自动重新部署：

```bash
git add .
git commit -m "你的修改说明"
git push https://<your-token>@github.com/sologgfun/m78-djs.git main
```

Render 检测到 `main` 分支有新提交后会自动触发部署，约 3~5 分钟完成。

---

## 首次部署步骤（从零开始）

如果需要在新环境重新部署，按以下顺序操作：

### 1. 后端部署到 Render

1. 打开 https://dashboard.render.com/new/web
2. 连接 GitHub 仓库 `sologgfun/m78-djs`
3. 填写配置：
   - **Runtime**：Python 3
   - **Build Command**：`pip install -r requirements.txt`
   - **Start Command**：`python backend/app.py`
   - **Instance Type**：Free
4. 点击 Create Web Service，等待部署完成
5. 记录 Render 分配的域名，格式为 `https://xxx.onrender.com`

### 2. 配置前端后端地址

编辑 `frontend-vite/.env.production`：

```
VITE_API_BASE_URL=https://xxx.onrender.com
```

### 3. 部署前端到 GitHub Pages

```bash
# 1. 推送代码到 GitHub
git push ...

# 2. 部署前端
cd frontend-vite
npm install
npm run deploy
```

4. 打开 GitHub 仓库 Settings → Pages，选择 Branch: `gh-pages`，保存。

---

## 注意事项

**Render 免费套餐冷启动**

免费服务在 15 分钟无请求后会休眠，下次访问需等待约 30~60 秒冷启动。
这是正常现象，等待后功能完全正常。

**SQLite 数据持久化**

Render 免费套餐的磁盘是临时的，每次重新部署后数据库会重置（回测记录会丢失）。
如需持久化数据，可升级 Render 付费套餐或迁移到 PostgreSQL。

**GitHub Token**

推送代码时需要 GitHub Personal Access Token。
生成地址：https://github.com/settings/tokens
建议定期更换，不要把 Token 明文保存在代码里。

**本地开发**

本地开发不受以上限制，直接使用：

```bash
make dev
```

后端运行在 http://127.0.0.1:8000，前端运行在 http://127.0.0.1:5173。
