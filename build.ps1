# 打包单文件 exe：无控制台 + 请求管理员权限（游戏 UIPI 需要）+ 鲸鱼图标
# 产物：dist\鲸鱼连点器.exe（不入 git，由 Release 分发）
# 用法：本机直接跑；CI 里 pwsh -File build.ps1 -Py python
param([string]$Py = "C:\Users\17416\AppData\Local\Programs\Python\Python314\python.exe")
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
& $Py -m PyInstaller --noconfirm --clean --onefile --noconsole --uac-admin `
    --name "鲸鱼连点器" `
    --icon "$root\assets\whale.ico" `
    --add-data "$root\assets;assets" `
    --collect-data sv_ttk `
    --distpath dist --workpath build --specpath build `
    src\app.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Get-Item "dist\鲸鱼连点器.exe" | Select-Object Name, Length