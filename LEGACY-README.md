# X-Matrix 全自动化测试环境

> **隔离版本**：与生产环境完全独立，用于测试新的架构优化�?
---

## 目录结构

```
全自动测�?
├── .env                          # 全局配置中心（唯一需要改的地方）
├── README.md                     # 本文�?�?├── x_matrix_nas/                 # NAS 后端（仅 Flask，无探针�?�?  ├── server.py                 # Flask 主服务（读取 .env 端口�?�?  ├── Dockerfile
�?  ├── docker-compose.yml        # 单容�?+ 资源限制
�?  ├── requirements.txt
�?  ├── .dockerignore
�?  ├── start.sh
�?  ├── targets.txt               # 目标账号（空或测试数据）
�?  ├── tags.json                 # 账号标签
�?  ├── templates/
�?  �?  └── index.html            # Dashboard 大屏
�?  ├── logs_chat/                # 聊天日志目录
�?  └── logs_follow/              # 关注日志目录
�?├── probe/                        # Playwright 探针（独立运行）
�?  ├── probe.py                  # 探针脚本
�?  ├── requirements.txt
�?  ├── probe_config.txt          # 探针任务配置
�?  ├── run-probe.bat             # Windows 一键启�?�?  └── run-probe.sh              # Linux/Mac 一键启�?�?├── X-Matrix-Bot/                 # Chrome 扩展
�?  ├── manifest.json
�?  ├── background.js
�?  ├── config.js
�?  ├── content_chat.js
�?  ├── content_follow.js
�?  ├── content_repost.js
�?  ├── content_id_extractor.js
�?  └── icon*.png
�?└── scripts/
    └── deploy.ps1                # 一键部署脚本（笔记本运行）
```

---

## 核心改进（与生产环境对比�?
| 改进�?| 生产环境 | 测试环境 |
|--------|---------|---------|
| 配置管理 | 6+ 文件硬编�?| **`.env` 单一配置中心** |
| NAS 容器 | server + probe�?个） | **�?server�?个）** |
| NAS 资源限制 | �?| **CPU 1�?/ 内存 512MB** |
| 探针位置 | NAS Docker | **台式机原生运�?* |
| 部署方式 | 手工 11 �?| **一键脚�?* |
| 探针启动 | Docker �?| **bat/sh 一键启�?* |

---

## 快速开�?
### 1. 修改配置

编辑 `.env` 文件�?
```bash
# 网络
NAS_IP=192.168.0.100          # 你的 NAS IP
NAS_PORT=5678                 # 服务端口（如与生产冲突可�?5001�?
# 代理
PROXY_IP=192.168.0.111        # 你的代理 IP
PROXY_PORT=7890               # 你的代理端口

# 探针上报地址（探针在台式机，上报�?NAS�?PROBE_NAS_URL=http://192.168.0.100:5678/api/probe_report
```

### 2. 部署 NAS 后端

**方式 A：笔记本通过 SSH 部署�?NAS**
```powershell
cd scripts
.\deploy.ps1 -NasIP "192.168.0.100" -NasUser "admin"
```

**方式 B：直接在 NAS 上操�?*
```bash
cd x_matrix_nas
docker-compose up -d --build
```

验证�?```bash
curl http://192.168.0.100:5678/api/dashboard_data
```

### 3. 启动探针（台式机�?
**Windows:**
```powershell
cd probe
.\run-probe.bat
```

**Linux/Mac:**
```bash
cd probe
chmod +x run-probe.sh
./run-probe.sh
```

探针会自动：
- 读取 `../.env` 配置
- 使用台式机的代理访问 SCRM
- 抓取数据后上报到 NAS

### 4. 加载 Chrome 扩展

1. 打开 Chrome �?`chrome://extensions/`
2. 开�?开发者模�?
3. 点击"加载已解压的扩展程序"
4. 选择 `X-Matrix-Bot` 文件�?
### 5. 查看大屏

浏览器打开：`http://192.168.0.100:5678`

---

## 设备分工

| 设备 | 职责 |
|------|------|
| **NAS** | 仅运�?`matrix_server` 容器（Flask + SQLite�?|
| **台式�?* | 运行探针 + BitBrowser + Chrome 扩展 |
| **笔记�?* | 代码开�?+ 运行部署脚本 |

---

## 生产环境迁移指南

测试验证通过后，迁移到生产环境：

1. 复制 `.env` 中的配置到生产目�?2. 复制 `probe_config.txt` 到生产探针目�?3. �?NAS 上用同样�?`docker-compose.yml` 启动
4. 在台式机上用同样�?`run-probe.bat` 启动探针
5. 更新 Chrome 扩展（加载新�?`X-Matrix-Bot` 目录�?
---

## 故障排查

| 现象 | 排查 |
|------|------|
| NAS 服务无法访问 | `docker logs xmatrix_test_server` |
| 探针无法启动 | 检�?`.env` �?PROXY_IP 是否正确 |
| 探针无法上报 NAS | 检�?NAS 防火墙是否放�?5678 端口 |
| 扩展无法连接 NAS | 检�?background.js 中的地址 |
| 大屏无数�?| 确认探针已启动并有抓取输�?|

---

*本环境完全隔离，可随时删�?`全自动测试` 文件夹而不影响生产�?
