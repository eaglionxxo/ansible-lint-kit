<#
.SYNOPSIS
  ansible-lint-kit installer for Windows: WSL + Ansible tooling + VS Code extensions.

.DESCRIPTION
  1. Checks that WSL and a Linux distribution are present (offers to install Ubuntu if not;
     this needs an elevated PowerShell and a reboot).
  2. Inside WSL: installs python3, pipx, git, then ansible-core, ansible-lint, yamllint and alk.
  3. Installs the VS Code extensions: Remote - WSL, Ansible, YAML.
  4. Runs `alk doctor` to confirm everything works.

  Nothing is installed without asking, unless -Yes is passed.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\install.ps1
#>
param(
  [switch]$Yes,
  [string]$Distro = 'Ubuntu',
  [string]$Source = ''
)

$ErrorActionPreference = 'Stop'

function Say($msg, $color = 'Cyan') { Write-Host "==> $msg" -ForegroundColor $color }
function Ask($question) {
  if ($Yes) { return $true }
  $answer = Read-Host "$question [o/N]"
  return $answer -match '^(o|oui|y|yes)$'
}
function WslText([string[]]$wslArgs) {
  # wsl.exe prints UTF-16; strip the NULs so PowerShell 5.1 can read it.
  $out = & wsl.exe @wslArgs 2>&1
  return (($out | Out-String) -replace "`0", '').Trim()
}
function IsAdmin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  return (New-Object Security.Principal.WindowsPrincipal $id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# --- 1. WSL ---------------------------------------------------------------
Say 'Checking WSL...'
$hasWsl = [bool](Get-Command wsl.exe -ErrorAction SilentlyContinue)
$distros = @()
if ($hasWsl) {
  $list = WslText @('-l', '-q')
  if ($LASTEXITCODE -eq 0) { $distros = @($list -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ }) }
}

if (-not $distros.Count) {
  Say 'WSL (or a Linux distribution) is not installed. Ansible needs Linux to run.' 'Yellow'
  if (-not (IsAdmin)) {
    Say "Re-run this script from an elevated PowerShell (Run as administrator) to install WSL + $Distro." 'Yellow'
    exit 1
  }
  if (-not (Ask "Install WSL with $Distro now? A reboot will be needed")) { Say 'Cancelled.' 'Yellow'; exit 1 }
  & wsl.exe --install -d $Distro
  Say "Reboot Windows, finish the $Distro first-run (create your Linux user), then run this script again." 'Green'
  exit 0
}
$target = if ($distros -contains $Distro) { $Distro } else { $distros[0] }
Say "Using WSL distribution: $target" 'Green'

# --- 2. Tools inside WSL --------------------------------------------------
if (-not $Source) {
  $here = Split-Path -Parent $MyInvocation.MyCommand.Path
  if (Test-Path (Join-Path $here 'pyproject.toml')) {
    $Source = (WslText @('-d', $target, '--', 'wslpath', '-a', ($here -replace '\\', '/')))
  } else {
    $Source = 'git+https://github.com/eaglionxxo/ansible-lint-kit.git'
  }
}

$bash = @"
set -e
sudo apt-get update -y
sudo apt-get install -y python3 python3-venv pipx git
pipx ensurepath
export PATH="`$HOME/.local/bin:`$PATH"
pipx install --include-deps ansible-core || pipx upgrade ansible-core
pipx install ansible-lint || pipx upgrade ansible-lint
pipx install yamllint || pipx upgrade yamllint
pipx install --force '$Source'
"@

if (Ask "Install python3, pipx, git, ansible-core, ansible-lint, yamllint and alk inside $target (sudo password may be asked)?") {
  & wsl.exe -d $target -- bash -lc ($bash -replace "`r", '')
  if ($LASTEXITCODE -ne 0) { Say 'Tool installation inside WSL failed (see output above).' 'Red'; exit 1 }
} else { Say 'Skipped tool installation.' 'Yellow' }

# --- 3. VS Code -----------------------------------------------------------
$code = Get-Command code -ErrorAction SilentlyContinue
if ($code) {
  if (Ask 'Install VS Code extensions (Remote - WSL, Ansible, YAML)?') {
    foreach ($ext in 'ms-vscode-remote.remote-wsl', 'redhat.ansible', 'redhat.vscode-yaml') {
      & code --install-extension $ext --force | Out-Null
      Say "VS Code extension: $ext" 'Green'
    }
  }
} else {
  Say 'VS Code CLI (code) not found: install VS Code, then re-run to add the extensions.' 'Yellow'
}

# --- 4. Doctor ------------------------------------------------------------
Say 'Running alk doctor inside WSL...'
& wsl.exe -d $target -- bash -lc 'export PATH="$HOME/.local/bin:$PATH"; alk doctor'
Say 'Done. In VS Code: Ctrl+Shift+P > "WSL: Connect to WSL", open your playbooks folder, then run `alk setup-vscode`.' 'Green'
