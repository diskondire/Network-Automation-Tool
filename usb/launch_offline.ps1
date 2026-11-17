# Console Capture USB launcher (offline, Windows x64)
# An installer is started only after the user explicitly clicks Yes.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
$wheelhouse = Join-Path $root 'offline\wheels'
$installer = Join-Path $root 'offline\python\python-3.13.17-amd64.exe'

function Find-CompatiblePython {
    $candidates = @()
    foreach ($version in @('3.14','3.13','3.12','3.11','3.10')) {
        if (Get-Command py -ErrorAction SilentlyContinue) {
            $candidates += ,@('py', "-$version")
        }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $candidates += ,@('python')
    }
    $candidates += ,@((Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'))
    foreach ($candidate in $candidates) {
        try {
            $exe = $candidate[0]
            $args = @()
            if ($candidate.Count -gt 1) { $args += $candidate[1] }
            $args += @('-c', 'import sys, struct; raise SystemExit(0 if (3,10) <= sys.version_info[:2] <= (3,14) and struct.calcsize("P") == 8 else 1)')
            & $exe @args *> $null
            if ($LASTEXITCODE -eq 0) { return ,$candidate }
        } catch { }
    }
    return $null
}

function Stop-WithMessage($message) {
    Write-Host ''
    Write-Host $message -ForegroundColor Yellow
    Read-Host 'Press Enter to close'
    exit 1
}

Write-Host 'Console Capture - Offline USB Setup' -ForegroundColor Cyan
Write-Host 'Checking for a compatible 64-bit Python installation (3.10-3.14)...'
$python = Find-CompatiblePython
if (-not $python) {
    Add-Type -AssemblyName System.Windows.Forms
    $choice = [System.Windows.Forms.MessageBox]::Show(
        'Python 3.10-3.14 (64-bit) is not installed. Install bundled Python 3.13.17 for the current user? Nothing will be installed if you choose No.',
        'Console Capture - Python required',
        [System.Windows.Forms.MessageBoxButtons]::YesNo,
        [System.Windows.Forms.MessageBoxIcon]::Question)
    if ($choice -ne [System.Windows.Forms.DialogResult]::Yes) {
        Stop-WithMessage 'Python installation declined. No changes have been made.'
    }
    if (-not (Test-Path -LiteralPath $installer)) {
        Stop-WithMessage 'Offline Python installer is missing. Use the USB release ZIP, not the source-only ZIP.'
    }
    # Validate Microsoft's Authenticode trust chain on the official installer.
    $signature = Get-AuthenticodeSignature -FilePath $installer
    if ($signature.Status -ne 'Valid' -or
        $signature.SignerCertificate.Subject -notmatch 'Python Software Foundation') {
        Stop-WithMessage "Python installer signature is not trusted ($($signature.Status)). Installation cancelled."
    }
    Write-Host 'Launching the signed Python installer (per-user installation)...'
    $process = Start-Process -FilePath $installer -ArgumentList @(
        '/passive', 'InstallAllUsers=0', 'Include_pip=1',
        'Include_tcltk=1', 'Include_launcher=1', 'PrependPath=0'
    ) -Wait -PassThru
    if ($process.ExitCode -notin @(0,3010)) {
        Stop-WithMessage "Python installer exited with code $($process.ExitCode)."
    }
    $python = Find-CompatiblePython
    if (-not $python) {
        Stop-WithMessage 'Python was installed but cannot be detected. Restart this launcher, or check the installation.'
    }
} else {
    Write-Host 'Compatible Python found. Skipping Python installation.' -ForegroundColor Green
}

if (-not (Test-Path -LiteralPath $wheelhouse)) {
    Stop-WithMessage 'Offline wheelhouse missing. Download the full USB release ZIP.'
}
$exe = $python[0]
$pythonArgs = @()
if ($python.Count -gt 1) { $pythonArgs += $python[1] }

# Virtual environments embed interpreter locations. Rebuild a broken USB venv.
$venv = Join-Path $root '.venv'
$venvPython = Join-Path $venv 'Scripts\python.exe'
if (Test-Path -LiteralPath $venvPython) {
    & $venvPython -c 'import sys; print(sys.executable)' *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Recreating an invalid virtual environment.'
        Remove-Item -LiteralPath $venv -Force -Recurse
    }
}
if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host 'Creating a local environment on the USB drive...'
    & $exe @pythonArgs -m venv $venv
    if ($LASTEXITCODE -ne 0) { Stop-WithMessage 'Could not create Python environment.' }
}
Write-Host 'Installing dependencies from USB (network disabled)...'
& $venvPython -m pip install --disable-pip-version-check --no-index --find-links $wheelhouse -r (Join-Path $root 'requirements.txt')
if ($LASTEXITCODE -ne 0) {
    Stop-WithMessage 'Offline dependency installation failed. Check wheelhouse/Windows architecture.'
}
& $venvPython -c 'import serial, docx, tkinter; from PIL import Image'
if ($LASTEXITCODE -ne 0) {
    Stop-WithMessage 'Some dependencies could not be imported.'
}
Write-Host 'Starting Console Capture...' -ForegroundColor Green
& $venvPython (Join-Path $root 'console_capture.py')
if ($LASTEXITCODE -ne 0) { Stop-WithMessage 'Console Capture exited with an error.' }
