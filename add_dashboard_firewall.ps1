# Opens inbound TCP 8765 so phones/laptops on the LAN can reach the bulb dashboard.
# Reversible: Remove-NetFirewallRule -DisplayName "bulb dashboard 8765 (lightbulb sniff)"
$name   = "bulb dashboard 8765 (lightbulb sniff)"
$result = "D:\lightbulb sniff\capture\fw_result.txt"
try {
    if (-not (Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -DisplayName $name -Direction Inbound -Action Allow `
            -Protocol TCP -LocalPort 8765 -Profile Any -ErrorAction Stop | Out-Null
        Set-Content -Path $result -Value "ADDED"
    } else {
        Set-Content -Path $result -Value "EXISTS"
    }
} catch {
    Set-Content -Path $result -Value ("ERROR: " + $_.Exception.Message)
}
