# Codex Usage Pet

一个轻量 Windows 桌面宠物：常驻桌面显示 Codex 5 小时与 weekly 额度，并用宠物姿态表达额度是否充足。

当前版本是可运行 MVP。宠物由程序原创绘制，不依赖外部图片素材，后续可替换为 sprite sheet。

## 已实现

- 官方 Codex App Server stdio JSONL 通信；复用本机 Codex 官方登录状态
- `account/read`、`account/rateLimits/read` 与 `account/rateLimits/updated` 事件
- 5h / weekly 的 used、remaining、reset 本地时间与 credits 显示
- `remainingPercent = 100 - usedPercent`，不会把已用与剩余显示反
- 透明、无边框、置顶、`Qt.Tool` 窗口，不显示普通任务栏按钮
- 拖动、锁定位置、位置持久化、跨屏边界钳制、透明度
- NORMAL / LOW / CRITICAL / EMPTY / RECOVERED 状态
- 低频原创 QPainter 动画（idle、walk、sit、stretch、critical、sleep）
- 右键菜单与系统托盘：刷新、额度显隐、置顶、锁定、透明度、刷新间隔、开机启动、日志、关于、退出
- HKCU 用户级开机启动，不需要管理员权限
- 60 秒默认轮询、事件触发刷新、失败退避、自动恢复、进程退出清理
- JSON 配置与 rotating log；不保存或记录 token、Cookie、密码
- PyInstaller `onedir` 打包

## 数据来源与隐私

程序启动一个长期复用的本机子进程：

```text
codex app-server --listen stdio://
```

连接后按官方协议发送一次 `initialize` 和 `initialized`，再读取：

- `account/read`：账户类型和套餐（UI 不显示邮箱）
- `account/rateLimits/read`：5h / weekly、重置时间、credits
- `account/rateLimits/updated`：额度变化事件；收到后重新读取完整快照

协议依据：[官方 Codex App Server 文档](https://learn.chatgpt.com/docs/app-server)。开发时还用本机 `codex app-server generate-json-schema` 核对过当前安装版本的字段。

程序不会抓取 ChatGPT 网页，不读取浏览器 Cookie，不要求粘贴 session token，也不会把凭据写入配置或日志。认证的保存与刷新完全由官方 Codex CLI/App Server 处理。

## 环境

- Windows 10/11
- Python 3.11 或 3.12（推荐）；当前开发机也通过 Python 3.13 测试
- 已安装可执行的 `codex` CLI，并已通过官方流程登录

先确认：

```powershell
codex --version
codex login
```

如果你已在 Codex 桌面应用或 CLI 中登录，通常不需要再次提供凭据。

## 开发环境运行

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe main.py
```

只安装运行依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

首次启动会立即读取一次额度。默认每 60 秒兜底刷新，同时监听 App Server 更新事件。右键宠物或托盘图标可立即刷新。

## 配置和日志

用户数据位于：

```text
%LOCALAPPDATA%\CodexUsagePet\config.json
%LOCALAPPDATA%\CodexUsagePet\logs\app.log
```

日志单文件最大约 1 MB，保留 3 个备份。配置只包含窗口位置、透明度、刷新间隔、置顶、锁定、额度显隐与开机启动偏好。

开机启动写入当前用户的：

```text
HKCU\Software\Microsoft\Windows\CurrentVersion\Run\CodexUsagePet
```

推荐在打包后开启启动项，这样路径稳定。源码模式也可用，但移动项目目录后应重新切换一次开机启动。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe main.py --smoke-test
```

测试覆盖正常响应、服务不可用、JSON-RPC 错误、字段缺失、5h/weekly 映射、0/100%、remaining 方向、Unix 秒/毫秒时间戳、reset 状态变化、子进程清理、配置损坏、配置不存在、日志凭据脱敏、开机启动和窗口核心属性。

## 打包

稳定优先，默认生成 `onedir`，避免单文件模式每次启动解包 Qt：

```powershell
.\build.ps1
```

或手动执行：

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm .\packaging\CodexUsagePet.spec
```

输出：

```text
dist\CodexUsagePet\CodexUsagePet.exe
dist\CodexUsagePet-portable.zip
```

目标电脑仍需安装并登录 Codex CLI；应用本身不捆绑或复制 Codex 凭据。当前构建未进行代码签名，因此首次运行可能出现 Windows SmartScreen 提示。

### Portable 使用

1. 将 `CodexUsagePet-portable.zip` 完整解压到任意可写目录；不要直接在 ZIP 内运行。
2. 确认目标电脑上的 `codex --version` 可用，并已通过官方 Codex 登录流程登录。
3. 双击解压目录中的 `CodexUsagePet\CodexUsagePet.exe`。
4. 额度会在启动后的首次 App Server 读取完成后出现；右键宠物可立即刷新。
5. 需要随 Windows 启动时，在右键菜单勾选“开机启动”。退出时使用宠物或托盘菜单的“退出”；关闭桌宠窗口只会隐藏到托盘。

Portable 包不依赖源码目录或 Python 环境，但仍依赖目标电脑上可执行且已登录的官方 Codex CLI。

### 可选安装器

安装 Inno Setup 6 后运行：

```powershell
.\build-installer.ps1
```

预期输出为 `dist\CodexUsagePet-Setup-0.1.0.exe`。安装器使用当前用户目录和 HKCU，
不要求管理员权限；桌面快捷方式和开机启动均为可选项。当前开发机没有安装
Inno Setup，因此安装器定义已提供，但安装器二进制尚未在本机编译验证。

## 常见问题

### 显示“暂时无法读取额度”

先在 PowerShell 运行 `codex --version`，确认 `codex.exe` 在 PATH 中；再打开 Codex CLI 检查登录状态。应用会进行有上限的指数退避并自动恢复，不需要频繁重启。

### weekly 或 credits 没显示

App Server 对不同账户可能返回不同字段。缺失值按“不可用”处理，不猜测为 0。如果只返回一个 7 天窗口，它会正确映射到 weekly。

### 关闭窗口后程序还在

点击窗口关闭只隐藏到托盘；使用右键菜单“退出”才会停止 App Server 子进程并退出。

### 如何替换宠物图片

当前宠物在 `src/codex_usage_pet/ui/pet_widget.py` 中使用 QPainter 绘制。`assets/` 已预留；后续可保持状态接口不变，替换成低帧率 sprite sheet。

## 项目结构

```text
src/codex_usage_pet/
  app.py
  codex/        # App Server 客户端、额度模型和解析
  pet/          # 状态机
  services/     # 刷新、配置、日志、启动项
  ui/           # 桌宠、额度气泡、托盘
tests/
packaging/
assets/
```

## 开源研究与许可证

项目本身采用 MIT 许可证。研究记录见 [OPEN_SOURCE_RESEARCH.md](OPEN_SOURCE_RESEARCH.md)，attribution 见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。四个指定参考项目均为 MIT；本仓库没有复制它们的源码模块或素材，而是重新实现通信、UI 与状态逻辑。

运行时使用 PySide6 Essentials / Qt。发布目录包含运行时许可说明，Qt 动态库保持独立可替换。

