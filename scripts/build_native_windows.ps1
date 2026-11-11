$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root
$agent = Join-Path $root 'dist\deviceshare-agent-windows-x64.exe'
$hub = Join-Path $root 'dist\deviceshare-hub-windows-x64.exe'
if (-not (Test-Path $agent) -or -not (Test-Path $hub)) {
  throw 'Frozen executables missing; build portable binaries first.'
}
New-Item -ItemType Directory -Force -Path 'release-assets' | Out-Null
dotnet tool install --global wix --version 5.0.2
if ($LASTEXITCODE -ne 0) { throw 'WiX installation failed.' }
$wix = Join-Path $env:USERPROFILE '.dotnet\tools\wix.exe'
if (-not (Test-Path $wix)) { throw 'WiX executable missing.' }
& $wix --version
& $wix build 'installers/windows/DeviceShare.wxs' -arch x64 -d "SourceRoot=$root" -o 'release-assets\DeviceShare-windows-x64.msi'
if ($LASTEXITCODE -ne 0) { throw 'WiX MSI build failed.' }
choco install innosetup --no-progress -y
if ($LASTEXITCODE -ne 0) { throw 'Inno Setup installation failed.' }
$inno = Join-Path ([Environment]::GetFolderPath('ProgramFilesX86')) 'Inno Setup 6\ISCC.exe'
if (-not (Test-Path $inno)) { throw "Inno Setup compiler not found at $inno" }
& $inno "/DSourceRoot=$root" '/DAppVersion=0.2.0-alpha.5' 'installers/windows/DeviceShare.iss'
if ($LASTEXITCODE -ne 0) { throw 'Inno Setup EXE build failed.' }
$msi = Join-Path $root 'release-assets\DeviceShare-windows-x64.msi'
$setup = Join-Path $root 'release-assets\DeviceShare-Setup-windows-x64.exe'
foreach ($file in @($msi, $setup)) {
  if (-not (Test-Path $file) -or (Get-Item $file).Length -lt 1000000) {
    throw "Installer missing or unexpectedly small: $file"
  }
}
$msiExtract = Join-Path $env:TEMP ('DeviceShare-MSI-check-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $msiExtract | Out-Null
$q = [char]34
$arguments = '/a ' + $q + $msi + $q + ' /qn TARGETDIR=' + $q + $msiExtract + $q
$proc = Start-Process 'msiexec.exe' -ArgumentList $arguments -Wait -PassThru
if ($proc.ExitCode -ne 0) { throw "MSI administrative extraction failed: $($proc.ExitCode)" }
$extractedAgent = Get-ChildItem -Path $msiExtract -Filter 'deviceshare-agent-windows-x64.exe' -File -Recurse | Select-Object -First 1
$extractedHub = Get-ChildItem -Path $msiExtract -Filter 'deviceshare-hub-windows-x64.exe' -File -Recurse | Select-Object -First 1
if (-not $extractedAgent -or -not $extractedHub) { throw 'MSI did not contain both executables' }
& $extractedAgent.FullName --version
if ($LASTEXITCODE -ne 0) { throw 'MSI agent CLI failed' }
& $extractedHub.FullName --version
if ($LASTEXITCODE -ne 0) { throw 'MSI hub CLI failed' }
Remove-Item -Path $msiExtract -Recurse -Force
Write-Host "Native Windows MSI and Inno Setup EXE verified."
