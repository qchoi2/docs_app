param(
    [Parameter(Mandatory=$true)][string]$InputJson,
    [Parameter(Mandatory=$true)][string]$OutputJson
)

$ErrorActionPreference = "Stop"
$jobs = Get-Content -LiteralPath $InputJson -Raw | ConvertFrom-Json
$results = New-Object System.Collections.ArrayList
$word = $null

try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    try {
        $word.AutomationSecurity = 3
    } catch {
        # Older Word versions may not expose this property.
    }
    $converterVersion = "Microsoft Word " + [string]$word.Version

    foreach ($job in $jobs) {
        $document = $null
        try {
            $source = [string]$job.source
            $target = [string]$job.target
            $targetDir = Split-Path -Parent $target
            if (-not (Test-Path -LiteralPath $targetDir)) {
                New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
            }
            try {
                $document = $word.Documents.Open(
                    $source,
                    $false,
                    $true,
                    $false,
                    "__codex_dummy_password__",
                    "__codex_dummy_password__",
                    $false,
                    "__codex_dummy_password__",
                    "__codex_dummy_password__",
                    0,
                    $false,
                    $true,
                    $false,
                    $false,
                    $false,
                    $false
                )
            } catch {
                # Some Word COM builds reject the long optional-argument form.
                # Keep ReadOnly=True and ConfirmConversions=False as a fallback.
                $document = $word.Documents.Open($source, $false, $true)
            }
            $document.SaveAs2($target, 16)
            [void]$results.Add([ordered]@{
                source = $source
                target = $target
                status = "ok"
                error_reason = $null
                converter_version = $converterVersion
            })
        } catch {
            [void]$results.Add([ordered]@{
                source = [string]$job.source
                target = [string]$job.target
                status = "error"
                error_reason = [string]$_.Exception.Message
                converter_version = $converterVersion
            })
        } finally {
            if ($document -ne $null) {
                try { $document.Close($false) } catch {}
            }
        }
    }
} catch {
    [void]$results.Add([ordered]@{
        source = $null
        target = $null
        status = "fatal"
        error_reason = [string]$_.Exception.Message
        converter_version = $null
    })
} finally {
    if ($word -ne $null) {
        try { $word.Quit() } catch {}
    }
}

$results | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $OutputJson -Encoding UTF8
