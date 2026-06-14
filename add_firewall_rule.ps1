# Adds an inbound firewall rule so the phone can reach mitmproxy on TCP 8080.
# Runs elevated (UAC). Reversible:  Remove-NetFirewallRule -DisplayName "mitmproxy 8080 (lightbulb sniff)"
$name   = "mitmproxy 8080 (lightbulb sniff)"
$result = "D:\lightbulb sniff\capture\fw_result.txt"
try {
    if (-not (Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -DisplayName $name -Direction Inbound -Action Allow `
            -Protocol TCP -LocalPort 8080 -Profile Any -ErrorAction Stop | Out-Null
        Set-Content -Path $result -Value "ADDED"
    } else {
        Set-Content -Path $result -Value "EXISTS"
    }
} catch {
    Set-Content -Path $result -Value ("ERROR: " + $_.Exception.Message)
}
