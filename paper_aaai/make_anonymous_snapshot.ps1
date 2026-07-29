param(
    [string]$OutputDirectory = "dist"
)

$ErrorActionPreference = "Stop"
$PaperRoot = (Resolve-Path $PSScriptRoot).Path
$RepoRoot = (Resolve-Path (Join-Path $PaperRoot "..")).Path
$DistRoot = Join-Path $PaperRoot $OutputDirectory
$Stage = Join-Path $DistRoot "anonymous_code_appendix"
$Zip = Join-Path $DistRoot "anonymous_code_appendix.zip"

if ($Stage -notlike "$PaperRoot\*") {
    throw "Refusing to stage outside the paper workspace: $Stage"
}

if (Test-Path $Stage) { Remove-Item -LiteralPath $Stage -Recurse -Force }
if (Test-Path $Zip) { Remove-Item -LiteralPath $Zip -Force }
New-Item -ItemType Directory -Force -Path $Stage | Out-Null

function Copy-Tree($RelativePath) {
    $source = Join-Path $RepoRoot $RelativePath
    $target = Join-Path $Stage $RelativePath
    New-Item -ItemType Directory -Force -Path (Split-Path $target) | Out-Null
    Copy-Item -LiteralPath $source -Destination $target -Recurse -Force
}

function Copy-One($RelativePath) {
    $source = Join-Path $RepoRoot $RelativePath
    $target = Join-Path $Stage $RelativePath
    New-Item -ItemType Directory -Force -Path (Split-Path $target) | Out-Null
    Copy-Item -LiteralPath $source -Destination $target -Force
}

# Acquisition scripts, frozen protocols, implementation, and analysis code.
Copy-Tree "benchmarks"
Copy-Tree "evaluation"
New-Item -ItemType Directory -Force -Path (Join-Path $Stage "experiments") | Out-Null
Get-ChildItem (Join-Path $RepoRoot "experiments") -File | Where-Object {
    $_.Extension -in ".py", ".txt", ".md"
} | ForEach-Object {
    Copy-One ("experiments/" + $_.Name)
}
Copy-Tree "experiments/analytical_bench"

# Reported result artifacts only.
$resultFiles = @(
    "analytical_cases.json",
    "analytical_fc_repl.json", "analytical_uac_v5.json",
    "analytical_full_context.json", "analytical_memmachine.json", "analytical_mem0.json",
    "modularity_cases.json", "modularity_monolithic.json",
    "modularity_modular.json", "modularity_manifest.json",
    "locomo5_uac_v5.json", "locomo5_uac_v5_ablate_no_state.json",
    "locomo5_uac_v5_ablate_no_facts.json", "locomo5_uac_v5_ablate_no_archive.json",
    "lme500_uac_v5.json", "lme500_full_context.json", "lme500_memmachine.json",
    "lme500_hindsight.json", "lme500_evermemos.json", "lme500_a_mem.json", "lme500_mem0.json"
)
foreach ($name in $resultFiles) { Copy-One ("experiments/results/" + $name) }

$systems = @("full_context", "uac_v5", "memmachine", "hindsight", "evermemos", "a_mem", "mem0")
foreach ($panel in @("full_locomo_gpt56_luna", "full_locomo_gemini3_flash_preview")) {
    foreach ($system in $systems) {
        Copy-One ("experiments/results/$panel/$system.json")
    }
}
Copy-Tree "experiments/results/active_service_v2_gpt_5_6_luna"
Copy-Tree "experiments/results/active_service_v3_gpt_5_6_luna"
Copy-Tree "experiments/results/conv30_extraction"

# The manuscript is submitted separately and is intentionally not duplicated
# in the code appendix. Package plot-generation code with the experiment tools.
$plotDir = Join-Path $Stage "experiments/plotting"
New-Item -ItemType Directory -Force -Path $plotDir | Out-Null
Copy-Item -LiteralPath (Join-Path $PaperRoot "figures/analytical_scaling.py") -Destination $plotDir -Force
Copy-Item -LiteralPath (Join-Path $PaperRoot "figures/generate_figures.py") -Destination $plotDir -Force
Copy-One "requirements.txt"

# Anonymous temporary licensing notices. The public release restores the
# copyright-holder names from the main repository.
$license = Get-Content -Raw (Join-Path $RepoRoot "LICENSE")
$license = $license -replace 'Copyright 2026 Bojie Li', 'Copyright 2026 Anonymous Authors'
Set-Content -Encoding utf8 (Join-Path $Stage "LICENSE") $license
$notice = Get-Content -Raw (Join-Path $RepoRoot "NOTICE")
$notice = $notice -replace 'Copyright 2026 Bojie Li \(Pine AI\)', 'Copyright 2026 Anonymous Authors'
Set-Content -Encoding utf8 (Join-Path $Stage "NOTICE") $notice

$readme = @'
# Anonymous code appendix

This archive accompanies an anonymous AAAI submission. It contains the
evaluated implementations, preprocessing and generation scripts, frozen
protocols, per-item result artifacts, and validators.

Start with:

- `experiments/README.md`
- `benchmarks/README.md`

To validate the packaged artifacts and reproduce the reported intervals and
paired tests without model calls, run:

```bash
python experiments/reproduce_reported_summaries.py
```

The evaluated constants are defined in the runners and method implementations;
their comments identify the corresponding named manuscript sections and stable
LaTeX labels. `experiments/plotting/analytical_scaling.py` regenerates the
aggregate-scaling plot from the packaged analytical results.

Third-party benchmark data are not redistributed. Use
`benchmarks/fetch_benchmarks.sh` and comply with the original dataset terms.
Model-backed runs require credentials supplied through environment variables;
the archive contains no credentials. The authors intend to publish the full
artifact under Apache License 2.0 upon publication.
'@
Set-Content -Encoding utf8 (Join-Path $Stage "README.md") $readme

# Remove transient files copied from nested directories.
Get-ChildItem $Stage -Recurse -Force | Where-Object {
    $_.Name -in @("__pycache__", ".pytest_cache", ".DS_Store") -or
    $_.Extension -in @(".pyc", ".log") -or
    $_.Name -match '\.(bak|invalid)$'
} | Sort-Object FullName -Descending | Remove-Item -Recurse -Force

# Sanitize historical absolute paths in the staged copy without modifying the
# research repository. These files are retained because they document the
# historical LongMemEval implementation.
$lme = Join-Path $Stage "experiments/full_longmemeval_comparison.py"
if (Test-Path $lme) {
    $text = Get-Content -Raw $lme
    $text = $text -replace 'sys\.path\.insert\(0, "/Users/boj/UserAsCode/experiments"\)', '# repository-relative imports are configured by the runner'
    $text = $text -replace '"/Users/boj/UserAsCode/benchmarks/longmemeval/data/longmemeval_oracle\.json"', 'str(Path(__file__).resolve().parent.parent / "benchmarks/longmemeval/data/longmemeval_oracle.json")'
    $text = $text -replace '"/Users/boj/UserAsCode/experiments/results/full_longmemeval_comparison\.json"', 'str(Path(__file__).resolve().parent / "results/full_longmemeval_comparison.json")'
    Set-Content -Encoding utf8 $lme $text
}

# This legacy all-in-one driver is not used by any reported result and embeds
# a historical machine path, so omit it from the anonymous appendix.
$legacy = Join-Path $Stage "experiments/final_evaluation.py"
if (Test-Path $legacy) { Remove-Item -LiteralPath $legacy -Force }

# Public commit hashes can identify the authors' repository. Preserve the
# field shape for provenance readers while removing the resolvable identifier.
Get-ChildItem $Stage -Recurse -File -Include *.json,*.jsonl | ForEach-Object {
    $text = Get-Content -Raw -LiteralPath $_.FullName
    $clean = $text -replace '("git_commit"\s*:\s*")[0-9a-fA-F]{40}("\s*)', '${1}ANONYMIZED_FOR_REVIEW${2}'
    if ($clean -ne $text) { Set-Content -Encoding utf8 -LiteralPath $_.FullName $clean }
}

# Fail closed on common identity, credential, VCS, and absolute-path leaks.
$patterns = @(
    'Bojie Li', 'Pine AI', '01\.me', '/Users/boj', 'C:\\Users\\noahs',
    '"git_commit"\s*:\s*"[0-9a-fA-F]{40}"',
    'BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY',
    'sk-(proj-)?[A-Za-z0-9_-]{20,}', 'AIza[A-Za-z0-9_-]{20,}'
)
$hits = @()
Get-ChildItem $Stage -Recurse -File | Where-Object { $_.Length -lt 25MB } | ForEach-Object {
    $path = $_.FullName
    foreach ($pattern in $patterns) {
        $match = Select-String -LiteralPath $path -Pattern $pattern -AllMatches -ErrorAction SilentlyContinue
        if ($match) { $hits += "$path :: $pattern" }
    }
}
if (Get-ChildItem $Stage -Recurse -Force | Where-Object { $_.Name -eq '.git' }) {
    $hits += "A .git directory is present"
}
if ($hits.Count -gt 0) {
    $hits | Sort-Object -Unique | ForEach-Object { Write-Error $_ }
    throw "Anonymity scan failed. Archive was not created."
}

# Deterministic inventory and integrity hashes (excluding the hash file itself).
$manifest = Get-ChildItem $Stage -Recurse -File | Sort-Object FullName | ForEach-Object {
    $relative = $_.FullName.Substring($Stage.Length + 1).Replace('\', '/')
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLower()
    "$hash  $relative"
}
Set-Content -Encoding ascii (Join-Path $Stage "SHA256SUMS.txt") $manifest

# Build the ZIP directly with normalized entry times. Scientific execution
# timestamps inside result JSON remain intact.
Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.IO.Compression
$zipStream = [System.IO.File]::Open($Zip, [System.IO.FileMode]::CreateNew)
$archive = [System.IO.Compression.ZipArchive]::new(
    $zipStream, [System.IO.Compression.ZipArchiveMode]::Create, $false
)
$fixedTime = [DateTimeOffset]::new(2000, 1, 1, 0, 0, 0, [TimeSpan]::Zero)
foreach ($file in (Get-ChildItem $Stage -Recurse -File | Sort-Object FullName)) {
    $relative = $file.FullName.Substring($DistRoot.Length + 1).Replace('\', '/')
    $entry = $archive.CreateEntry($relative, [System.IO.Compression.CompressionLevel]::Optimal)
    $entry.LastWriteTime = $fixedTime
    $sourceStream = [System.IO.File]::OpenRead($file.FullName)
    $entryStream = $entry.Open()
    $sourceStream.CopyTo($entryStream)
    $entryStream.Dispose()
    $sourceStream.Dispose()
}
$archive.Dispose()
$zipStream.Dispose()
$zipHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Zip).Hash.ToLower()
$fileCount = (Get-ChildItem $Stage -Recurse -File).Count
$zipSize = (Get-Item $Zip).Length

# The unpacked tree is only a build staging area. Remove it after the archive
# has been finalized and inspected so dist contains only the submission ZIP.
Remove-Item -LiteralPath $Stage -Recurse -Force

Write-Output "STAGE=$Stage"
Write-Output "ZIP=$Zip"
Write-Output "FILES=$fileCount"
Write-Output "BYTES=$zipSize"
Write-Output "SHA256=$zipHash"
