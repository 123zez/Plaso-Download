# plaso-dl

Windows 下的伯索云学堂历史课程下载工具，支持账号密码登录/自动抓 token、按课程或按班级拉视频列表、批量下载、分片自动拼接与时长校验。

## 免责声明

- 仅用于你有权限访问的课程内容。
- 不提供 DRM 解密能力。
- 不提供绕过付费、验证码、平台安全策略的能力。

## 功能

- 中文交互入口（开始菜单、登录后菜单、下载菜单）
- 两种登录方式：
  - 账号密码直登（调用官方登录接口）
  - 自动抓取 token（Electron DevTools）
- 课程视频加载方式：
  - 获取课程目录（按课程主题）
  - 按班级获取课程视频
  - 一键加载全部课程视频（在课程目录选择时输入 `0/A/all/全部`）
- 下载能力：
  - 单个/多个/全部/仅补缺
  - 自动识别多分片流（如 `s1/s101/s201/...`）并合并
  - 下载后时长校验（默认容差 1 分钟）
- 下载展示：
  - 每个视频独立动态进度条
  - 总体进度条
  - 结束后总结：成功/跳过/警告/失败 + 失败详情

## 环境要求

- Windows
- Python `3.10+`（源码运行时）
- `ffmpeg` 和 `ffprobe` 可用（加入 PATH）

验证：

```bash
ffmpeg -version
ffprobe -version
```

## 快速开始（源码运行）

```bash
cd <你的项目目录>
python -m venv .venv
.venv\Scripts\python -m pip install -U pip
.venv\Scripts\python -m pip install -e .[dev]
python start_plaso_dl.py
```

首次建议：

1. 开始菜单先点 `设置`
2. 配置伯索程序路径（每个人安装位置可能不同）
3. 再点 `登录`

## EXE 使用（推荐给普通用户）

已打包入口：

- `dist/plaso-dl-launcher.exe`

直接双击运行即可。

说明：

- 配置文件保存在用户目录（不会跟随 exe 删除）
- 仍需要系统可用 `ffmpeg/ffprobe`

### 自己重新打包

```bash
python -m pip install pyinstaller
pyinstaller --noconfirm --clean --onefile --name plaso-dl-launcher start_plaso_dl.py
```

输出：`dist/plaso-dl-launcher.exe`

## 菜单说明

### 开始菜单

- `登录`
- `设置`
- `退出`

### 登录后菜单

- `获取课程目录`
- `按班级获取课程视频`
- `设置`
- `退出`

### 下载菜单

- `单个下载`：按序号或课程 id 下载
- `多个下载`：逗号分隔输入多个序号/id
- `全部下载`：下载当前列表全部课程视频
- `更新(仅缺失)`：只下载目标目录缺失的视频

### 设置菜单

- `伯索程序路径`
- `下载目录`
- `单视频分片并发`（1-8）
- `批量下载并发`（1-6）

## 命令行用法（高级）

```bash
python -m plaso_dl auth auto-capture --host 127.0.0.1 --port 9222 --timeout 600
python -m plaso_dl courses list
python -m plaso_dl download course --id <course_id>
python -m plaso_dl download all --workers 3
```

## 项目结构

```text
plaso-dl/
  start_plaso_dl.py              # 一键入口脚本
  dist/plaso-dl-launcher.exe     # 打包后的可执行文件
  src/plaso_dl/
    launcher.py                  # 菜单交互与全流程编排
    api.py                       # 登录/班级/课程接口
    auth_capture.py              # DevTools 抓 token
    resolve.py                   # m3u8 分片探测
    download.py                  # 下载/合并/时长校验
    ffmpeg.py                    # ffmpeg/ffprobe 封装
    config.py                    # 配置持久化
    cli.py                       # CLI 命令入口
    models.py                    # 数据模型
    util.py                      # 工具函数
  tests/
```

## 常见问题

- 登录失败：先检查账号密码是否正确，或改用“自动抓取 token”。
- 伯索路径错误：在设置中修改为你机器上的 `plaso-yxt.exe` 实际路径。
- 下载输出太多：已做静默优化；失败时仅显示关键错误摘要。
- 时长异常警告：通常是源端分片不完整或仍有隐藏分片未暴露。
