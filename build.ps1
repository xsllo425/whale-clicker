# 打包单文件 exe：无控制台 + 请求管理员权限（游戏 UIPI 需要）+ 鲸鱼图标
# 产物：dist\鲸鱼连点器.exe（不入 git，由 Release 分发）
# 用法：本机直接跑；CI 里 pwsh -File build.ps1 -Py python
param([string]$Py = "C:\Users\17416\AppData\Local\Programs\Python\Python314\python.exe")
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
# 本机 E:\Work 带低完整性继承，先在同一分区正常目录生成，再移动回 dist。
# 其他环境（包括 CI）继续使用原来的 dist，避免依赖本机目录。
$buildDist = Join-Path $root 'dist'
$useStage = $root.StartsWith('E:\Work\', [StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath 'E:\CODEX')
if ($useStage) {
    $buildDist = Join-Path 'E:\CODEX\_build' ('whale-clicker-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $buildDist -Force | Out-Null
}
& $Py -m PyInstaller --noconfirm --clean --onefile --noconsole --uac-admin `
    --name "鲸鱼连点器" `
    --icon "$root\assets\whale.ico" `
    --add-data "$root\assets;assets" `
    --collect-data sv_ttk `
    --distpath "$buildDist" --workpath build --specpath build `
    src\app.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if ($useStage) {
    Move-Item -LiteralPath (Join-Path $buildDist '鲸鱼连点器.exe') -Destination (Join-Path $root 'dist\鲸鱼连点器.exe') -Force
}
Get-Item "dist\鲸鱼连点器.exe" | Select-Object Name, Length
