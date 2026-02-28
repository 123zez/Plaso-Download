# plaso-dl

一个面向 Windows 的伯索云学堂历史课程下载工具，支持从桌面端自动抓取 token、列课、批量下载、分片自动拼接和时长校验。

## 免责声明

- 仅用于你有权限访问的课程内容。
- 不提供 DRM 解密能力。
- 不提供绕过付费、验证码、平台安全策略的能力。

## 功能概览

- 自动启动伯索桌面端并开启 `--remote-debugging-port=9222`
- 自动抓取 `access-token`（无需手工复制）
- 拉取历史课程列表并展示
- 支持单个/多个/全部/仅补缺下载
- 自动识别并合并多分片播放流（如 `s1/s101/s201/...`）
- 下载后自动做时长校验（与课程时长比较，默认容差 1 分钟）
- 可配置下载目录和单视频分片并发数

## 环境要求

- Python `3.10+`
- `ffmpeg` 和 `ffprobe` 可用（加入 PATH）
- Windows 桌面端：安装位置因人而异，可在启动器“设置”中配置伯索程序路径

## 安装

```bash
cd <你的项目目录>
python -m venv .venv
.venv\Scripts\python -m pip install -U pip
.venv\Scripts\python -m pip install -e .[dev]
```

验证 ffmpeg：

```bash
ffmpeg -version
ffprobe -version
```

## 推荐用法：一键入口（中文菜单）

直接运行：

```bash
python start_plaso_dl.py
```

完整流程：

1. 运行 `python start_plaso_dl.py`
2. 在开始菜单选择 `设置`，配置伯索程序路径（每台机器都可能不同）
3. 回到开始菜单选择 `登录`
4. 登录后在伯索中进入“课程/实时课堂/历史课堂”触发请求，程序自动抓取 token
5. 登录成功后进入“登录后菜单”，选择 `获取课程目录`
6. 先看到账号下课程数，再选择某一门课程并拉取该课程视频列表
7. 进入下载菜单执行下载操作

图文：

1. ![屏幕截图 2026-02-28 083305](https://raw.githubusercontent.com/123zez/my-images/main/images/屏幕截图 2026-02-28 083305.png)
2. ![image-20260228085150570](https://raw.githubusercontent.com/123zez/my-images/main/images/image-20260228085150570.png)
3. 输入1登陆后弹出界面登陆![image-20260228085225681](https://raw.githubusercontent.com/123zez/my-images/main/images/image-20260228085225681.png)
4. 正在监听点击实时课程![image-20260228085353900](https://raw.githubusercontent.com/123zez/my-images/main/images/image-20260228085353900.png)
5. 再点击历史课堂即可![image-20260228085550621](https://raw.githubusercontent.com/123zez/my-images/main/images/image-20260228085550621.png)

开始菜单：

- `登录`
- `设置`
- `退出`

登录后菜单：

- `获取课程目录`
- `按班级获取课程视频`
- `设置`
- `退出`

下载菜单：

- `单个下载`：按序号或课程 id 下载一节
- `多个下载`：逗号分隔输入多个序号/id
- `全部下载`：下载当前课程列表全部课程
- `更新(仅缺失)`：只下载目标目录里还不存在的课程

设置菜单：

- `下载目录`
- `单视频分片并发`（1-8）
- `批量下载并发`（1-6）

## 命令行用法（高级用户）

### 1) 启动桌面端（手动）

```powershell
Start-Process "<你的伯索程序路径>" -ArgumentList "--remote-debugging-port=9222"
```

### 2) 抓取 token

```bash
python -m plaso_dl auth auto-capture --host 127.0.0.1 --port 9222 --timeout 600
```

或手工设置 token：

```bash
python -m plaso_dl auth set-token "<your-token>"
```

### 3) 查看课程列表

```bash
python -m plaso_dl courses list
python -m plaso_dl courses list --limit 20
```

### 4) 下载课程

```bash
python -m plaso_dl download course --id <course_id>
python -m plaso_dl download all --limit 5
python -m plaso_dl download all --workers 3
```

## 项目结构

```text
plaso-dl/
  start_plaso_dl.py              # 一键入口脚本（中文交互）
  src/plaso_dl/
    launcher.py                  # 全流程编排：启动、抓 token、菜单、下载
    cli.py                       # Typer 命令行入口
    api.py                       # 课程列表 API 请求与解析
    auth_capture.py              # DevTools 协议抓 access-token
    resolve.py                   # m3u8 规则探测与分片选择
    download.py                  # 下载、拼接、时长校验
    ffmpeg.py                    # ffmpeg/ffprobe 命令封装
    config.py                    # token + 下载设置持久化
    models.py                    # 课程数据模型
    util.py                      # 通用工具（文件名清洗、时长格式化）
  tests/                         # 单元测试
```

## 关键技术说明

- `Typer`：CLI 命令组织
- `Rich`：课程表格、进度条、交互输出
- `httpx`：调用课程接口、探测 m3u8
- `websocket-client`：连接 Electron DevTools 抓取请求头 token
- `ffmpeg`：HLS 下载与封装
- `ffprobe`：下载后时长校验
- `ThreadPoolExecutor`：批量下载并发与分片并发

## 常见问题

- 看到客户端日志 `Module not found fluent-ffmpeg`：通常是伯索客户端自身日志，不是本工具核心错误。
- 提示卡住：多数是正在等待 token；请确认已进入伯索历史课程页以触发网络请求。
- 下载后时长差异较大：工具会报警 `mismatch`，通常表示仍有分片未被平台暴露或源端不完整。
