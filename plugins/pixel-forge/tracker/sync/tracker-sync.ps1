<#
  Idea to Launch sync helper (Windows PowerShell 5.1+). A cross-platform twin is tracker_sync.py.

  Prints one JSON object {now, setups[], repos[]} describing every project folder in the projects root:
  git push state, commit counts, the last 30 days of activity and the last 14 days of commit messages.
  Existing projects are only read, never changed.

  -Root <dir>            The projects root. Required unless tracker.config.json (next to this script,
                         or -Config) has "root". Folders starting with "_" or "." are not projects.
  -Config <file>         tracker.config.json to read. Default: the one next to this script.
                         { "root": "...", "gitignoreTemplate": "godot|node|generic", "iconsDir": "icons/auto" }
  -Req "<records>"       Optional. Projects to set up, as one string so the command never needs a temp
                         file. Records are separated by ";;" and fields by "|":
                           id|folder|name|create|github|note
                         create: 1 = make <root>\<folder> with README.md, .gitignore, git init and a
                           first commit (an existing folder is never touched); 0 = folder already exists.
                         github: private | public | none. Creates a GitHub repo with the gh CLI and
                           pushes. Only for a git repo with commits and no remote yet. Name = kebab-case
                           project name, with -2, -3... if taken.
                         note: free text for the README (no "|", ";;" or quotes).
  -Requests <file.json>  Same requests as a JSON array of {id, folder, name, note, create, github}.
  -Gitignore <name>      .gitignore for new folders: godot | node | generic. Default: the config's
                         gitignoreTemplate, else generic.
  -Icons                 Also find each project's icon and save a <=192 px copy in the icons folder,
                         reported as icon {file, pixelArt, source}.
  -IconsDir <dir>        Where -Icons saves copies. Default: the config's iconsDir, else icons\auto
                         next to this script.
  -DryRun                Create nothing: no folders, no commits, no GitHub repos. Setups report what
                         would happen. (-Icons still writes its copies, which live in the tracker's folder.)

  Usage: powershell -NoProfile -ExecutionPolicy Bypass -File tracker-sync.ps1 [-Root DIR] [-Req "..."] [-Icons] [-DryRun]
#>
param(
  [string]$Req = "",
  [string]$Requests = "",
  [string]$Root = "",
  [string]$Config = "",
  [string]$Gitignore = "",
  [switch]$Icons,
  [string]$IconsDir = "",
  [switch]$DryRun
)
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
$utf8 = New-Object System.Text.UTF8Encoding $false

function Stop-WithError([string]$Message) {
  [Console]::Error.WriteLine("tracker-sync: $Message")
  exit 2
}

# ---- 0. settings: -Root / -Gitignore / -IconsDir win over tracker.config.json ----
$cfg = $null
if (-not $Config) { $Config = Join-Path $PSScriptRoot 'tracker.config.json' }
if (Test-Path -LiteralPath $Config) {
  try { $cfg = Get-Content -LiteralPath $Config -Raw -Encoding UTF8 | ConvertFrom-Json }
  catch { Stop-WithError "Can't read $Config as JSON: $($_.Exception.Message)" }
}
$cfgDir = if ($cfg) { Split-Path -Parent (Resolve-Path -LiteralPath $Config).Path } else { $PSScriptRoot }
if (-not $Root -and $cfg -and $cfg.root) { $Root = [string]$cfg.root; if (-not [IO.Path]::IsPathRooted($Root)) { $Root = Join-Path $cfgDir $Root } }
if (-not $Root) { Stop-WithError "No projects root. Pass -Root <dir> or put {""root"": ""...""} in $Config." }
if (-not (Test-Path -LiteralPath $Root -PathType Container)) { Stop-WithError "The projects root '$Root' doesn't exist." }
$Root = (Resolve-Path -LiteralPath $Root).Path
$rootName = Split-Path -Leaf $Root
if (-not $Gitignore -and $cfg -and $cfg.gitignoreTemplate) { $Gitignore = [string]$cfg.gitignoreTemplate }
$Gitignore = if ($Gitignore) { $Gitignore.ToLower() } else { 'generic' }
if ($Gitignore -notin @('godot', 'node', 'generic')) { Stop-WithError "gitignoreTemplate must be godot, node or generic (got '$Gitignore')." }
if (-not $IconsDir -and $cfg -and $cfg.iconsDir) { $IconsDir = [string]$cfg.iconsDir; if (-not [IO.Path]::IsPathRooted($IconsDir)) { $IconsDir = Join-Path $cfgDir $IconsDir } }
if (-not $IconsDir) { $IconsDir = Join-Path $PSScriptRoot 'icons\auto' }

$GitignoreTemplates = @{
  godot   = "# Godot 4`n.godot/`n/android/`n`n# Builds and signing keys`n*.apk`n*.aab`n*.keystore`n`n# OS and editor files`nThumbs.db`n.DS_Store`n*.tmp`n"
  node    = "node_modules/`ndist/`nbuild/`ncoverage/`n.env`n.env.*`n!.env.example`nnpm-debug.log*`n`n# OS and editor files`nThumbs.db`n.DS_Store`n*.tmp`n"
  generic = "# OS and editor files`nThumbs.db`n.DS_Store`n*.tmp`n*.log`n.env`n"
}

function Invoke-Git([string]$Path, [string[]]$GitArgs) {
  $out = & git -C $Path @GitArgs 2>$null
  if ($LASTEXITCODE -ne 0) { return $null }
  return $out
}

function Get-RepoStats([string]$Path, [string]$Rel) {
  $s = [ordered]@{ folder = $Rel; isRepo = $true }
  $count = Invoke-Git $Path @('rev-list', '--count', 'HEAD')
  $s.commitsTotal = if ($count) { [int]$count } else { 0 }
  $s.branch = Invoke-Git $Path @('symbolic-ref', '--short', 'HEAD')
  $remotes = @(Invoke-Git $Path @('remote') | Where-Object { $_ })
  $remote = if ($remotes -contains 'origin') { 'origin' } elseif ($remotes.Count -gt 0) { $remotes[0] } else { $null }
  $s.remoteUrl = if ($remote) { Invoke-Git $Path @('remote', 'get-url', $remote) } else { $null }
  $up = Invoke-Git $Path @('rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}')
  $s.upstream = $up
  if ($s.commitsTotal -gt 0) {
    if ($up) {
      $s.ahead = [int](Invoke-Git $Path @('rev-list', '--count', '@{u}..HEAD'))
      $s.behind = [int](Invoke-Git $Path @('rev-list', '--count', 'HEAD..@{u}'))
    } elseif ($remote) {
      $s.ahead = [int](Invoke-Git $Path @('rev-list', '--count', 'HEAD', '--not', '--remotes'))
      $s.behind = 0
    } else {
      $s.ahead = $s.commitsTotal
      $s.behind = 0
    }
    $s.lastCommitAt = Invoke-Git $Path @('log', '-1', '--format=%cI')
    $s.firstCommitAt = Invoke-Git $Path @('log', '--reverse', '--format=%cI') | Select-Object -First 1
    $s.commits7d = [int](Invoke-Git $Path @('rev-list', '--count', '--since=7 days ago', 'HEAD'))
    $act = [ordered]@{}
    $days = Invoke-Git $Path @('log', '--since=30 days ago', '--format=%cd', '--date=short')
    if ($days) { $days | Group-Object | Sort-Object Name | ForEach-Object { $act[$_.Name] = $_.Count } }
    $s.activity = $act
    $s.recentCommits = @(Invoke-Git $Path @('log', '--since=14 days ago', '-n', '40', '--format=%cI|%s') | Where-Object { $_ } | ForEach-Object {
      $i = $_.IndexOf('|'); [ordered]@{ at = $_.Substring(0, $i); subject = $_.Substring($i + 1) }
    })
  } else {
    $s.ahead = 0; $s.behind = 0; $s.lastCommitAt = $null; $s.firstCommitAt = $null
    $s.commits7d = 0; $s.activity = [ordered]@{}; $s.recentCommits = @()
  }
  # --no-optional-locks: read the status without refreshing the index, so a sync never writes into a repo.
  $st = Invoke-Git $Path @('--no-optional-locks', 'status', '--porcelain')
  $s.dirty = if ($st) { @($st).Count } else { 0 }
  return $s
}

function Get-FolderStats([string]$Path, [string]$Rel) {
  $newest = Get-ChildItem $Path -Recurse -File -Depth 3 -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch '\\(node_modules|\.godot)\\' } |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
  return [ordered]@{
    folder = $Rel; isRepo = $false
    lastModifiedAt = if ($newest) { $newest.LastWriteTime.ToString('o') } else { $null }
  }
}

function Get-ProjectIcon([string]$Path, [string]$Rel) {
  $cands = @()
  $pg = Join-Path $Path 'project.godot'
  if (Test-Path $pg) {
    $m = Select-String -Path $pg -Pattern '^config/icon="res://(.+)"' | Select-Object -First 1
    if ($m) { $cands += Get-Item (Join-Path $Path ($m.Matches[0].Groups[1].Value -replace '/', '\')) -ErrorAction SilentlyContinue }
  }
  $prefix = $Path.TrimEnd('\').Length
  $cands += Get-ChildItem $Path -Recurse -File -Depth 4 -Include *.png, *.jpg, *.webp -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName.Substring($prefix) -notmatch '\\(\.godot|\.git|node_modules|raw[^\\]*|videos?|capture)\\' -and $_.BaseName -match '^(icon|app[_-]?icon|logo)([-_ ]?\d+)?$|^icon[-_]\d+$|-icon-\d+$' } |
    Sort-Object @{ e = { if ($_.BaseName -match '^icon$') { 0 } elseif ($_.BaseName -match 'icon') { 1 } else { 2 } } }, @{ e = { $_.Length }; Descending = $true }
  $src = $cands | Where-Object { $_ } | Select-Object -First 1
  if (-not $src) { return $null }
  Add-Type -AssemblyName System.Drawing
  New-Item -ItemType Directory -Force $IconsDir | Out-Null
  $slug = (($Rel -split '[\\/]')[0].ToLower() -replace '[^a-z0-9]+', '-').Trim('-')
  $out = Join-Path $IconsDir "$slug.png"
  try {
    $img = [System.Drawing.Image]::FromFile($src.FullName)
    $max = [Math]::Max($img.Width, $img.Height)
    $pixel = $max -le 64
    if ($max -le 192) {
      $img.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
    } else {
      $k = 192 / $max; $w = [int]($img.Width * $k); $h = [int]($img.Height * $k)
      $bmp = New-Object System.Drawing.Bitmap $w, $h
      $g = [System.Drawing.Graphics]::FromImage($bmp); $g.InterpolationMode = 'HighQualityBicubic'; $g.DrawImage($img, 0, 0, $w, $h)
      $bmp.Save($out, [System.Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $bmp.Dispose()
    }
    $img.Dispose()
    return [ordered]@{ file = $out; pixelArt = $pixel; source = $src.FullName }
  } catch { return $null }
}

function ConvertTo-RepoName([string]$Text) {
  $n = ($Text.ToLower() -replace '[^a-z0-9]+', '-').Trim('-')
  if ($n.Length -gt 60) { $n = $n.Substring(0, 60).Trim('-') }
  if (-not $n) { $n = 'new-project' }
  return $n
}

$script:ghOwner = $null
function New-GitHubRepo([string]$Path, [string]$Name, [string]$Visibility, [string]$Description, [bool]$Planned = $false) {
  $g = [ordered]@{ ok = $false; visibility = $Visibility; name = $null; url = $null; error = $null }
  if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { $g.error = "The GitHub CLI (gh) isn't installed on this computer."; return $g }
  if (-not $script:ghOwner) {
    $script:ghOwner = (& gh api user --jq .login 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $script:ghOwner) { $script:ghOwner = $null; $g.error = "gh isn't signed in to GitHub. Run 'gh auth login' once."; return $g }
  }
  if (-not $Planned) {
    if (-not (Test-Path (Join-Path $Path '.git'))) { $g.error = "This folder isn't a git repo yet."; return $g }
    if (-not (Invoke-Git $Path @('rev-parse', '--verify', 'HEAD'))) { $g.error = "The repo has no commits to push yet."; return $g }
    $remotes = @(Invoke-Git $Path @('remote') | Where-Object { $_ })
    if ($remotes.Count -gt 0) { $g.error = "This repo already has a remote ($($remotes -join ', '))."; return $g }
  }
  $base = ConvertTo-RepoName $Name
  $pick = $null
  foreach ($suffix in @('', '-2', '-3', '-4', '-5')) {
    $cand = $base + $suffix
    & gh repo view "$($script:ghOwner)/$cand" --json name 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { $pick = $cand; break }
  }
  if (-not $pick) { $g.error = "GitHub repos named $base to $base-5 already exist."; return $g }
  $g.name = $pick
  $g.url = "https://github.com/$($script:ghOwner)/$pick"
  if ($DryRun) { $g.ok = $true; $g.dryRun = $true; return $g }
  $flag = if ($Visibility -eq 'public') { '--public' } else { '--private' }
  $desc = ([string]$Description -split "`n")[0].Trim()
  if ($desc.Length -gt 100) { $desc = $desc.Substring(0, 100) }
  $ghArgs = @('repo', 'create', $pick, $flag, '--source', $Path, '--remote', 'origin', '--push')
  if ($desc) { $ghArgs += @('--description', $desc) }
  $out = & gh @ghArgs 2>&1 | Out-String
  if ($LASTEXITCODE -ne 0) { $g.error = "gh repo create failed: " + $out.Trim(); return $g }
  & git -C $Path push -u origin HEAD 2>$null | Out-Null
  $g.ok = $true
  return $g
}

# ---- 1. create requested projects and GitHub repos ----
$setups = @()
$reqs = @()
if ($Req) {
  foreach ($rec in ($Req -split ';;')) {
    if (-not $rec.Trim()) { continue }
    $f = $rec.Split('|')
    if ($f.Count -lt 3) { $setups += [ordered]@{ id = $null; folder = $null; ok = $false; error = "Unreadable request: $rec"; warning = $null; github = $null }; continue }
    $reqs += [pscustomobject]@{
      id = $f[0].Trim(); folder = $f[1].Trim(); name = $f[2].Trim()
      create = -not ($f.Count -gt 3 -and $f[3].Trim() -eq '0')
      github = if ($f.Count -gt 4) { $f[4].Trim().ToLower() } else { 'none' }
      note = if ($f.Count -gt 5) { ($f[5..($f.Count - 1)] -join '|').Trim() } else { '' }
    }
  }
} elseif ($Requests -and (Test-Path $Requests)) {
  $reqs = @(Get-Content $Requests -Raw -Encoding UTF8 | ConvertFrom-Json)
}
if ($reqs.Count -gt 0) {
  foreach ($r in $reqs) {
    $res = [ordered]@{ id = $r.id; folder = $r.folder; ok = $false; error = $null; warning = $null; github = $null }
    $folder = [string]$r.folder
    $create = -not ($r.PSObject.Properties.Name -contains 'create' -and $r.create -eq $false)
    $name = if ($r.name) { [string]$r.name } else { $folder }
    $planned = $false
    if ($folder -notmatch '^[A-Za-z0-9][A-Za-z0-9 _\\/-]{0,119}$' -or $folder -match '\.\.') {
      $res.error = "Folder names can use letters, numbers, spaces, hyphens and underscores (60 characters at most)."
    } elseif ($create) {
      $path = Join-Path $Root $folder
      if ($folder -match '[\\/]') {
        $res.error = "Folder names can use letters, numbers, spaces, hyphens and underscores (60 characters at most)."
      } elseif (Test-Path $path) {
        $res.error = "A folder named $folder already exists in $rootName. Pick another name."
      } elseif ($DryRun) {
        $res.ok = $true; $res.dryRun = $true; $planned = $true
        $res.warning = "Dry run: would create $folder with README.md, a $Gitignore .gitignore, git init and a first commit."
      } else {
        New-Item -ItemType Directory -Path $path | Out-Null
        $date = Get-Date -Format 'yyyy-MM-dd'
        $readme = "# $name`n`n$([string]$r.note)`n`nStarted $date from the Idea to Launch brain dump.`n"
        [IO.File]::WriteAllText((Join-Path $path 'README.md'), $readme, $utf8)
        [IO.File]::WriteAllText((Join-Path $path '.gitignore'), $GitignoreTemplates[$Gitignore], $utf8)
        & git -C $path init -b main 2>$null | Out-Null
        & git -C $path add -A 2>$null | Out-Null
        & git -C $path commit -m "Start $name" 2>$null | Out-Null
        $res.ok = $true
        if ($LASTEXITCODE -ne 0) { $res.warning = "Folder and repo created, but the first commit failed. Check git user.name and user.email." }
      }
    } else {
      $path = Join-Path $Root ($folder -replace '/', '\')
      if (Test-Path $path) { $res.ok = $true } else { $res.error = "$rootName\$folder doesn't exist." }
    }
    if ($res.ok -and ($r.github -eq 'private' -or $r.github -eq 'public')) {
      $res.github = New-GitHubRepo $path $name ([string]$r.github) ([string]$r.note) $planned
    }
    $setups += $res
  }
}

# ---- 2. describe every project folder ----
$repos = @()
Get-ChildItem $Root -Directory | Where-Object { $_.Name -notmatch '^[_.]' } | ForEach-Object {
  $top = $_
  $found = @()
  if (Test-Path (Join-Path $top.FullName '.git')) {
    $found += , @($top.FullName, (Get-RepoStats $top.FullName $top.Name))
  } else {
    $subs = @(Get-ChildItem $top.FullName -Directory -Force -ErrorAction SilentlyContinue |
      Where-Object { Test-Path (Join-Path $_.FullName '.git') })
    if ($subs.Count -gt 0) {
      foreach ($d in $subs) { $found += , @($d.FullName, (Get-RepoStats $d.FullName ($top.Name + '\' + $d.Name))) }
    } else {
      $found += , @($top.FullName, (Get-FolderStats $top.FullName $top.Name))
    }
  }
  foreach ($pair in $found) {
    $rec = $pair[1]
    if ($Icons) { $rec.icon = Get-ProjectIcon $pair[0] $rec.folder }
    $repos += $rec
  }
}

[ordered]@{ now = (Get-Date).ToString('o'); setups = $setups; repos = $repos } | ConvertTo-Json -Depth 6
