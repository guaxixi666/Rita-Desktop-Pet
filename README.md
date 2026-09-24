# Codex Usage Pet

一个轻量 Windows 桌面宠物：常驻桌面显示 Codex 5 小时与 weekly 额度，并用宠物姿态表达额度是否充足。

当前版本是 Release Candidate 0.1.0。角色、动画与整套 UI 配色由外置 Skin Pack 驱动，新增角色原则上不需要修改主程序。

## 已实现

- 官方 Codex App Server stdio JSONL 通信；复用本机 Codex 官方登录状态
- `account/read`、`account/rateLimits/read` 与 `account/rateLimits/updated` 事件
- 5h / weekly 的 used、remaining、reset 本地时间与 credits 显示
- `remainingPercent = 100 - usedPercent`，不会把已用与剩余显示反
- 透明、无边框、置顶、`Qt.Tool` 窗口，不显示普通任务栏按钮
- 拖动、锁定位置、位置持久化、跨屏边界钳制、透明度
- NORMAL / LOW / CRITICAL / EMPTY / RECOVERED 状态
- Rita / Umbral Rose 统一配色、轻量悬浮额度气泡与淡入淡出
- 默认 idle 完全静止；Hover、Click、随机待机及额度状态通过 Skin 可配置的动作池选择 Blink、Wave、Tidy Hair、Sleep React、Sit Transition 或无反应，不再固定绑定单一动作
- 人物与额度气泡是两个独立透明窗口；气泡显隐不会改变人物屏幕 anchor，并会按左右可用空间智能展开
- Skin 加载时一次性计算全动作 alpha Union Bounds；动画期间窗口位置与尺寸固定，所有帧映射到统一 232×244 logical canvas，并以脚底中心对齐
- 全中文 Rita 主题互动设置页：折叠事件卡片、Chip 动作选择、皮肤默认/自定义来源提示，以及不改写原配置的安静模式
- 独立 Skin Pack：手动/随机换肤、热扫描、缺帧 fallback、无重复随机
- 自动换肤：每 6/12/24/48 小时，或每天本地固定时间；重启后继续原计时
- 右键菜单与系统托盘：刷新、皮肤、互动/动作设置、额度显隐、置顶、锁定、透明度、刷新间隔、开机启动、桌面快捷方式、日志、关于、退出
- HKCU 用户级开机启动，不需要管理员权限
- 用户级桌面快捷方式创建/更新/删除；自动指向当前冻结版或 Portable EXE，不硬编码用户目录
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

Windows 启动时会先检查 `codex`、`codex.exe` 和 `codex.cmd`，然后检查当前用户的 Codex Desktop 与 npm launcher 目录。因此即使 Explorer 的 PATH 尚未包含最新 Codex 目录，也能发现当前用户安装的官方 executable；`.cmd` launcher 会通过隐藏的 Windows command shell 正确启动。

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

日志单文件最大约 1 MB，保留 3 个备份。配置只包含窗口位置、透明度、刷新间隔、置顶、锁定、额度显隐、皮肤计时、安静模式、各 Skin 的动作启用项与开机启动偏好。

## Skin Pack

程序按顺序扫描：

1. 随发行包提供的内置 `skins/`；
2. portable 模式下 EXE 同级的 `skins/`；
3. `%LOCALAPPDATA%\CodexUsagePet\skins` 用户目录。

同 ID 的后扫描皮肤会覆盖前者，因此可以在用户目录修订内置皮肤而不改安装文件。右键选择“皮肤 → 打开皮肤目录”，把一个完整皮肤文件夹复制进去，再选择“重新扫描皮肤”即可热加载。坏 JSON、越界路径或缺少 idle 的包会被跳过并写入日志，不影响桌宠运行。

每套皮肤至少包含 `skin.json` 和 idle 图片。当前 schema 同时支持单独 PNG 和网格 sprite sheet：

```json
{
  "id": "my_skin",
  "name": "My Skin",
  "author": "Your Name",
  "version": "1.0",
  "preview": "preview.png",
  "preferred_width": 220,
  "preferred_height": 220,
  "anchor_x": 0,
  "anchor_y": -3,
  "action_policy": {
    "idle_trigger_probability": 0.62,
    "idle_interval_min": 45,
    "idle_interval_max": 150,
    "avoid_immediate_repeat": true,
    "history_size": 3,
    "pools": {
      "hover": [
        {"action": "hover", "weight": 45, "cooldown": [3000, 8000], "allowed_states": ["normal"]},
        {"action": "blink", "weight": 35, "cooldown": [5000, 15000], "allowed_states": ["normal"]},
        {"action": "none", "weight": 20, "allowed_states": ["normal"]}
      ],
      "low_on_enter": [{"action": "sit_transition", "weight": 80, "allowed_states": ["low"]}],
      "low_idle": [{"action": "sit", "weight": 100, "allowed_states": ["low"]}],
      "low_on_exit": [{"action": "none", "weight": 100, "allowed_states": ["low"]}]
    }
  },
  "theme": {
    "panel": "#24222B",
    "progress_track": "#35313A",
    "primary": "#C05A78",
    "highlight": "#DA7892",
    "critical": "#87364E",
    "empty": "#958594",
    "low": "#E8C3CD",
    "text_primary": "#F3ECEE",
    "text_secondary": "#BDAFB5",
    "border": "#87364E",
    "decorator": "✿"
  },
  "states": {
    "idle": "idle.png",
    "blink": {
      "source": "animations/blink.png",
      "grid": [3, 2],
      "frames": 6,
      "fps": 20,
      "frame_durations_ms": [150, 70, 70, 110, 70, 130],
      "loop": false,
      "cooldown": 1500,
      "interruptible": true
    },
    "click": {
      "source": "animations/click.png",
      "grid": [4, 2],
      "frames": [[0, 0], [1, 0], [2, 0], [3, 0], [0, 1], [1, 1], [2, 1], [3, 1]],
      "fps": 10,
      "loop": false,
      "interruptible": false
    },
    "walk": "walk.png",
    "critical": {
      "file": "sheet.png",
      "grid": [3, 2],
      "cell": [1, 1],
      "offset_x": -10,
      "offset_y": 0
    }
  }
}
```

### 动作池与角色性格

动作选择链路为“事件/状态 → Skin Policy → 用户启用项 → 状态、素材与 cooldown 过滤 → 加权选择 → 动画播放器”。支持 `hover`、`click`、`idle_random`、`recovered`、`normal_idle`，以及 LOW / CRITICAL / EMPTY 各自的 `*_on_enter`、`*_idle`、`*_on_exit`。`none` 是合法候选，表示本次保持安静；过滤后为空也会安全回到基础姿态。两套内置 Rita Skin 的默认 Hover/Click 池不再包含 `none`，因此一次真实悬停或点击一定会产生可见反馈；Random Idle 与状态过渡仍可按 Skin 个性保持安静。

`cooldown` 使用毫秒，可写单个数或 `[min, max]`；`allowed_states` 限制动作出现的额度状态。最近 3 次已播放动作只保留在当前运行 session 中，默认避免立即重复；候选只有一个时仍允许重复。系统状态动作、Click、Hover、随机待机和 idle 的优先级依次降低，优先级只决定哪类事件可播放，具体动作仍由池选择。

用户可右键选择“互动设置”，在全中文卡片页中分别启用或禁用当前皮肤的鼠标悬停、点击人物、随机待机、额度较低、额度紧张、额度耗尽与额度恢复候选，也可恢复当前皮肤默认值。安静模式只在运行时暂停悬停和随机待机，点击与额度状态仍照常工作，关闭后原动作配置自动恢复。覆盖配置按 Skin ID 独立保存，不改写 `skin.json`；底层事件和动作 ID 始终保持英文。Skin 可在 `states` 中声明新的动作 ID，并在池中直接引用；没有对应素材的候选会自动过滤。

动画可使用连续帧数或显式 `frames` 坐标，并声明 `fps`、`frame_durations_ms`、`loop`、`cooldown` 和 `interruptible`。逐帧时长存在时优先于 FPS，可用于准备、停顿和恢复节奏。播放器首次使用时缓存帧，切换皮肤会释放旧帧缓存；idle 没有逐帧定时器。`preferred_width` / `preferred_height` 控制角色绘制尺寸。播放器在皮肤加载/重载时扫描一次所有帧，以每帧底部接触中心归一化到统一 logical canvas，再取全动作 alpha Union Bounds 加 4 px 安全边距作为整个 Skin 生命周期内不变的窗口范围；动画播放不再 resize、adjustSize 或移动人物窗口。除 idle 外的状态都是可选项；缺少互动动画时保持基础姿态，critical 仍优先回退 sit，再回退 idle。

内置 Rita 动画参数：

| 动作 | 帧数 | FPS | 时长 | 循环 |
| --- | ---: | ---: | ---: | --- |
| Blink | 6 | 20 | 600 ms | 否 |
| Hover | 6 | 24 | 1100 ms | 否 |
| Click | 8 | 24 | 1500 ms | 否 |
| Wave | 8 | 24 | 2400 ms | 否 |
| Tidy Hair（兼容 `stretch` 状态） | 12 | 24 | 2920 ms | 否 |
| Sleep React | 8 | 20 | 2400 ms | 否 |
| Sit Transition | 10 | 24 | 1600 ms | 否 |

内置 Umbral Rose 的 LOW 默认偏向 Sit Transition 与坐姿，但这些只是可替换的 Skin 默认策略；CRITICAL、EMPTY 与 RECOVERED 同样经各自动作池选择。CRITICAL 和 EMPTY 的内置候选使用专门绘制的疲惫与睡眠姿态，不通过缩放、旋转或整图平移伪造动作；EMPTY 点击池可选择 Sleep React 后回到持续姿态。

内置皮肤：

- `rita_umbral_rose`：默认玫瑰主题与完整六状态素材。
- `rita_moonlit_rose`：独立打包的冷紫主题示例，演示整套气泡、进度条、菜单与装饰元素切换；当前复用同一套原创角色画面。

### 自动换肤计时

“每 24 小时”等间隔模式以 `last_skin_change` 的 UTC 时间为基准，而不是以程序启动时间为基准。关机或休眠超过间隔后，下次启动只立即随机一次，然后以当前时间开始下一周期，不会补换多次。

“每天固定时间”按当前 Windows 本地时区判断最近一个时间边界，支持 00:00、08:00、12:00、18:00 和自定义 `HH:MM`。随机候选在存在多套皮肤时排除当前皮肤；只有一套时保持原样且不会报错。

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

测试覆盖正常响应、服务不可用、JSON-RPC 错误、字段缺失、5h/weekly 映射、0/100%、remaining 方向、Unix 秒/毫秒时间戳、reset 状态变化、子进程清理、配置损坏、日志凭据脱敏、开机启动、Skin Pack 扫描与 fallback、手动/随机/定时换肤、重启续时、固定时间、热加载、自定义动作 ID、动作池权重/过滤/cooldown/防重复/none/用户覆盖、状态进入/持续/退出、动作优先级、状态保持、统一 logical canvas、全 Skin Union Bounds、逐帧顺序与时长优先级、hold frame、帧缓存与释放、窗口 geometry、脚底 0 px anchor、安静模式、中文映射安全 fallback、气泡跟随，以及反复显隐时人物 0 像素漂移。

动画回归诊断可运行：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
.\.venv\Scripts\python.exe .\tools\animation_regression_qa.py
```

它通过真实 Qt renderer 和 QTimer 验证逐帧像素差异、Timer 推进、统一 Canvas 与脚底 anchor，并在 `artifacts\regression\` 生成 Blink、Click、Wave、Sit GIF 和诊断文本。

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
5. 需要桌面入口时，右键选择“创建桌面快捷方式”。如果 Portable 文件夹以后移动，再执行一次即可更新同一个 `Codex Usage Pet.lnk`；也可从菜单删除。
6. 需要随 Windows 启动时，在右键菜单勾选“开机启动”。退出时使用宠物或托盘菜单的“退出”；关闭桌宠窗口只会隐藏到托盘。

Portable 包不依赖源码目录或 Python 环境，但仍依赖目标电脑上可执行且已登录的官方 Codex CLI。
快捷方式使用当前 EXE 自带图标，Working Directory 为 EXE 所在目录，不需要管理员权限。源码开发模式会禁用快捷方式菜单，避免错误地创建指向 `python.exe` 的链接。

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

日志会把失败明确标为 `discover_codex`、`spawn_app_server`、`initialize_request`、`initialized_notification`、`account_read`、`rate_limits_read` 或 `response_parse`，并保留脱敏后的原始异常、退出码、stderr 摘要与 JSON-RPC 错误。日志不会记录 token、Cookie、Authorization 或 session credential。

### weekly 或 credits 没显示

App Server 对不同账户可能返回不同字段。缺失值按“不可用”处理，不猜测为 0。如果只返回一个 7 天窗口，它会正确映射到 weekly。

### 关闭窗口后程序还在

点击窗口关闭只隐藏到托盘；使用右键菜单“退出”才会停止 App Server 子进程并退出。

### 如何增加新角色

复制一份 `skins/rita_umbral_rose/`，修改目录名、`skin.json` 的唯一 ID、素材和主题即可。状态图片应使用真实透明 alpha；不要求固定网格，也可以让每个状态指向单独 PNG。完成后右键“重新扫描皮肤”，无需重启或重新打包。

## 项目结构

```text
src/codex_usage_pet/
  app.py
  codex/        # App Server 客户端、额度模型和解析
  pet/          # 状态机
  skins/        # Skin Pack 扫描、schema 与自动换肤
  services/     # 刷新、配置、日志、启动项
  ui/           # 桌宠、额度气泡、托盘
skins/          # 可独立分发的内置皮肤包
tests/
packaging/
assets/
```

## 开源研究与许可证

项目本身采用 MIT 许可证。研究记录见 [OPEN_SOURCE_RESEARCH.md](OPEN_SOURCE_RESEARCH.md)，attribution 见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。四个指定参考项目均为 MIT；本仓库没有复制它们的源码模块或素材，而是重新实现通信、UI 与状态逻辑。

Rita 风格 sprite sheet 是根据[视觉研究记录](RITA_VISUAL_RESEARCH.md)中的文字简报重新生成的原创 fan-art 素材，没有下载、裁剪或嵌入官方立绘、游戏纹理或第三方同人图。

运行时使用 PySide6 Essentials / Qt。发布目录包含运行时许可说明，Qt 动态库保持独立可替换。

