
$ErrorActionPreference = "Stop"

# 1. Determine Paths
$BaseDir = $PSScriptRoot
$BackupScript = Join-Path $BaseDir "db\backup_supabase.py"
$TaskName = "BudgetAmico_Supabase_Backup"

# Verify script exists
if (-not (Test-Path $BackupScript)) {
    Write-Error "Backup script not found at: $BackupScript"
    exit 1
}

# 2. Find Python Interpreter
try {
    $PythonPath = (Get-Command python).Source
} catch {
    try {
        $PythonPath = (Get-Command py).Source
    } catch {
        Write-Error "Python not found in PATH. Please install Python or add it to PATH."
        exit 1
    }
}

# 3. Create Task Action string
# We use cmd /c to ensure window closes or runs properly, but calling python directly works too.
# Running hidden might be preferred, but for now let's keep it visible or standard.
$Action = "`"$PythonPath`" `"$BackupScript`""

Write-Host "Creating Scheduled Task: $TaskName"
Write-Host "Script: $BackupScript"
Write-Host "Schedule: DAILY at 13:00"

# 4. Register Task using schtasks (works on all Windows versions reliably)
# /f forces overwrite if exists
# /rl HIGHEST might be needed if writing to protected folders, but user folder should be fine.
schtasks /create /tn "$TaskName" /tr $Action /sc daily /st 13:00 /f

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n[SUCCESS] Backup scheduled successfully!"
    Write-Host "The backup will run every day at 13:00."
    Write-Host "You can change the time in 'Task Scheduler' (Utilità di pianificazione)."
} else {
    Write-Host "`n[ERROR] Failed to schedule task."
}
