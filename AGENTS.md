# Agent Instructions — whale-clicker

上级工作区 `E:\Work\` 的管理约定（仓库清单、建仓步骤、跨仓库规矩）见 `../AGENTS.md`。

全局约定见 `~/.dsh/AGENTS.md`（pwsh、脚本先写文件、改后跑验证、不读密钥文件等），这里只写本仓库特有的。

## 待办

- 待办事项统一记在仓库根目录 `TODO.md`（跨会话生效），用户提起其中任何一件时先读它再动手。
- 用户说「记一下 / 记一下待办」就是指**落盘保存**，不要只写会话内的待办清单（重开即丢）。
- 记忆默认记**项目范围**（`.dsh/memory/`），只有用户明说「全局 / 跨项目」时才写全局记忆。

## 本仓库特有约定

- 产品：鲸鱼连点器（WhaleClicker），Windows 鼠标连点器，招牌功能是「真实按住自动让路」。
- 源码在 `src/`（app.py 界面 / core.py 引擎），自测在 `tests/test_basic.py`，图标等素材在 `assets/`。
- 运行/测试一律用系统 Python：`C:\Users\17416\AppData\Local\Programs\Python\Python314\python.exe`。
- 改完代码必须跑 `python tests\test_basic.py` 全绿才算数；该自测无副作用（打桩，不发真实点击）。
- 发布身份只用 xsllo425；README 主文件中文，英文版 `README.en.md`；Release 标题与说明用中文。
- 打包用 PyInstaller（`build.ps1`），产物 `dist/鲸鱼连点器.exe` 不入 git（.gitignore 已挡）。
- 旧目录 `E:\Work\鼠标连点器` 是本仓库前身，保留作回滚备份，不在那里继续开发。