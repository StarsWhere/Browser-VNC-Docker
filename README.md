# Browser-VNC-Docker

浏览器VNC容器管理系统

## 项目简介

这是一个基于Docker的VNC浏览器管理系统，允许用户通过Web界面管理多个独立的Firefox浏览器实例。每个浏览器实例都有独立的配置文件，支持代理设置、自动启动等功能，并可通过VNC或noVNC进行远程访问。

## 许可证

该项目采用 MIT 许可证 - 详见 [LICENSE](./LICENSE) 文件

这是一个基于Docker的VNC浏览器多账户管理系统，允许用户通过Web界面管理多个独立的Firefox浏览器实例。每个浏览器实例都有独立的配置文件，支持代理设置、自动启动等功能，并可通过VNC或noVNC进行远程访问。

## 功能特性

- **多浏览器实例**：支持创建和管理多个独立的Firefox浏览器实例
- **独立配置文件**：每个实例拥有独立的Firefox配置文件
- **代理支持**：支持HTTP、HTTPS和SOCKS5代理配置
- **自动启动**：支持设置实例自动启动
- **远程访问**：通过VNC或noVNC进行远程访问
- **Web管理界面**：提供直观的Web界面进行实例管理
- **日志管理**：完善的日志记录和管理功能

## 系统架构

- Docker容器化部署
- VNC服务提供桌面环境
- noVNC提供Web VNC访问
- Supervisor进程管理
- Flask Web管理界面
- Firefox浏览器实例

## 快速开始

### 环境要求

- Docker
- Docker Compose

### 配置

复制环境配置文件：

```bash
cp .env.example .env
```

编辑 `.env` 文件，设置必要的环境变量：

```bash
VNC_PASSWORD=your-vnc-password  # 必填：VNC访问密码
TZ=Asia/Shanghai               # 时区，默认为上海
NOVNC_PORT=6080               # noVNC端口，默认6080
ADMIN_PORT=8080               # 管理界面端口，默认8080
```

### 启动服务

```bash
docker-compose up -d
```

### 访问服务

- **noVNC界面**：`http://localhost:6080` - 用于访问VNC桌面
- **管理界面**：`http://localhost:8080` - 用于管理浏览器账户

## 使用说明

### 管理浏览器实例

通过管理界面可以进行以下操作：

1. **创建实例**：添加新的浏览器实例
2. **编辑实例**：修改实例配置（名称、代理、自动启动等）
3. **启动/停止**：控制浏览器实例的运行状态
4. **删除实例**：移除浏览器实例

### 代理配置

支持以下代理类型：

- HTTP代理
- HTTPS代理
- SOCKS5代理

代理配置会自动应用到Firefox的配置文件中。

### 自动启动

可以设置实例在系统启动时自动运行，方便维护长期运行的浏览器实例。

## 目录结构

```
VNC-Chrome-Docker/
├── Dockerfile              # Docker镜像构建文件
├── docker-compose.yml      # Docker Compose配置
├── .env.example           # 环境变量示例
├── .gitignore             # Git忽略文件配置
├── requirements.txt       # Python依赖
├── app/                   # 应用程序代码
│   ├── admin/             # 管理界面
│   ├── scripts/           # 启动脚本
│   └── supervisor/        # Supervisor配置
├── docs/                  # 文档
└── data/                  # 数据存储目录（挂载卷）
```

## 配置文件说明

### .env 环境变量

- `VNC_PASSWORD`：VNC访问密码（必填）
- `TZ`：时区设置（默认：Asia/Shanghai）
- `LANG`：语言设置（默认：en_US.UTF-8）
- `LC_ALL`：本地化设置（默认：en_US.UTF-8）
- `NOVNC_PORT`：noVNC端口（默认：6080）
- `ADMIN_PORT`：管理界面端口（默认：8080）
- `LOG_MAX_BYTES`：日志文件最大大小（默认：10485760）
- `LOG_BACKUP_COUNT`：日志备份文件数量（默认：5）

### 数据持久化

容器内的 `/data` 目录映射到本地的 `./data` 目录，包含：

- `accounts.json`：实例配置文件
- `logs/`：日志文件
- `profiles/`：Firefox配置文件

## 技术栈

- **容器技术**：Docker, Docker Compose
- **桌面环境**：Fluxbox, TigerVNC
- **Web VNC**：noVNC, websockify
- **Web框架**：Flask
- **进程管理**：Supervisor
- **浏览器**：Firefox ESR
- **后端语言**：Python

## 安全考虑

- VNC访问需要密码保护
- 通过环境变量配置敏感信息
- 隔离的浏览器配置文件
- 适当的文件权限设置

## 开发与贡献

### 本地开发

1. 克隆仓库
2. 修改代码
3. 构建并运行容器进行测试

### 贡献指南

1. Fork项目
2. 创建功能分支
3. 提交更改
4. 发起Pull Request

## 支持与反馈

如遇到问题或有改进建议，请通过以下方式联系：

- 提交Issue
- 发送邮件