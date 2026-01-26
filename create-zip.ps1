$ErrorActionPreference = "Stop"

Set-Location "C:\AI\gaming-content-agent"

# Clean up
if (Test-Path "gameinfo-terminal.zip") { Remove-Item "gameinfo-terminal.zip" -Force }
if (Test-Path "gameinfo-terminal") { Remove-Item "gameinfo-terminal" -Recurse -Force }

# Copy theme to folder with correct name
Copy-Item "wp-theme-gameinfo" "gameinfo-terminal" -Recurse

# Create ZIP
Compress-Archive -Path "gameinfo-terminal" -DestinationPath "gameinfo-terminal.zip" -Force

# Clean up temp folder
Remove-Item "gameinfo-terminal" -Recurse -Force

Write-Host "ZIP created successfully!"
