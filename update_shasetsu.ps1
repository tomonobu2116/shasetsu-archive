# Shasetsu archive updater
# pull -> fetch -> (if changed) commit/push -> log

# ==== settings (edit here) ====
$RepoDir   = "C:\Scripts\shasetsu-archive"
$PythonExe = "python"
# ==============================

$ErrorActionPreference = "Stop"

$LogDir = Join-Path $RepoDir "log"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
$LogFile = Join-Path $LogDir ("update_{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"))

function Log($msg) {
    $line = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    Write-Output $line
    Add-Content -Path $LogFile -Value $line
}

try {
    Log "=== start ==="

    if (-not (Test-Path $RepoDir)) {
        throw "Repo not found: $RepoDir"
    }
    Set-Location $RepoDir

    Log "git pull ..."
    git pull --quiet
    if ($LASTEXITCODE -ne 0) { throw "git pull failed" }

    Log "python fetch_shasetsu.py ..."
    & $PythonExe "fetch_shasetsu.py" 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) { throw "fetch_shasetsu.py failed" }

    $changed = git status --porcelain "data/articles.json"
    $changed = "$changed".Trim()
    if ($changed -eq "") {
        Log "no change (no new editorial). skip push."
        Log "=== done ==="
        exit 0
    }

    Log "changes found. commit / push."
    git add "data/articles.json"
    git commit -m ("update articles ({0})" -f (Get-Date -Format "yyyy-MM-dd")) --quiet
    git push --quiet
    if ($LASTEXITCODE -ne 0) { throw "git push failed" }

    Log "push done."
    Log "=== done ==="
    exit 0
}
catch {
    Log ("[ERROR] " + $_.Exception.Message)
    Log "=== failed ==="
    exit 1
}