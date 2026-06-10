# ============================================================
# finaliser_arborescence.ps1
# Termine la réorganisation (collisions, notebooks racine, config)
# À lancer depuis le dossier racine "ML"
# ============================================================

Write-Host ""
Write-Host "=== FINALISATION ARBORESCENCE ===" -ForegroundColor Cyan
Write-Host ""

# ── 1. Ranger les notebooks de la RACINE vers notebooks/<modele> ──
Write-Host "1. Rangement des notebooks de la racine..." -ForegroundColor Yellow

# Regles : motif -> dossier cible
$regles = @(
    @{ motif = "_M1|01_M1|02_M1"; cible = "notebooks/M1_fraude" },
    @{ motif = "_M2|03_M2";        cible = "notebooks/M2_mules" },
    @{ motif = "commission|_M4|04_M4"; cible = "notebooks/M4_commissions" },
    @{ motif = "_M5|05_M5";        cible = "notebooks/M5_echec" },
    @{ motif = "_M6|06_M6";        cible = "notebooks/M6_reconciliation" },
    @{ motif = "00_diagnostic|01_conversion"; cible = "notebooks" },
    @{ motif = "01_data_exploration|notebook_02|02_notebook"; cible = "notebooks/_archives" }
)

# Dossier d'archives pour les vieux notebooks exploratoires
if (-not (Test-Path "notebooks/_archives")) {
    New-Item -ItemType Directory -Path "notebooks/_archives" -Force | Out-Null
}

Get-ChildItem -Path "." -Filter "*.ipynb" -File | ForEach-Object {
    $nom = $_.Name
    $range = $false
    foreach ($regle in $regles) {
        if ($nom -match $regle.motif) {
            Move-Item $_.FullName -Destination "$($regle.cible)/" -Force
            Write-Host "   $nom -> $($regle.cible)/" -ForegroundColor Green
            $range = $true
            break
        }
    }
    if (-not $range) {
        Move-Item $_.FullName -Destination "notebooks/_archives/" -Force
        Write-Host "   $nom -> notebooks/_archives/ (non classe)" -ForegroundColor DarkGray
    }
}

# ── 2. Resoudre la collision streamlit_M1\pages ──
Write-Host ""
Write-Host "2. Resolution streamlit_M1..." -ForegroundColor Yellow
if (Test-Path "streamlit_M1") {

    # 2a. Pages : deplacer fichier par fichier (la collision etait sur le DOSSIER)
    if (Test-Path "streamlit_M1/pages") {
        Get-ChildItem "streamlit_M1/pages" -File | ForEach-Object {
            Move-Item $_.FullName -Destination "dashboard/pages/" -Force
            Write-Host "   page : $($_.Name) -> dashboard/pages/" -ForegroundColor Green
        }
    }

    # 2b. Outputs de streamlit_M1 -> outputs/ (fusion)
    if (Test-Path "streamlit_M1/outputs/M1_fraude") {
        Get-ChildItem "streamlit_M1/outputs/M1_fraude" -File | ForEach-Object {
            Move-Item $_.FullName -Destination "outputs/M1_fraude/" -Force
        }
        Write-Host "   outputs M1_fraude fusionnes" -ForegroundColor Green
    }
    if (Test-Path "streamlit_M1/outputs/M1_fraude_v2") {
        if (-not (Test-Path "outputs/M1_fraude_v2")) {
            New-Item -ItemType Directory -Path "outputs/M1_fraude_v2" -Force | Out-Null
        }
        Get-ChildItem "streamlit_M1/outputs/M1_fraude_v2" -File | ForEach-Object {
            Move-Item $_.FullName -Destination "outputs/M1_fraude_v2/" -Force
        }
        Write-Host "   outputs M1_fraude_v2 fusionnes" -ForegroundColor Green
    }

    # 2c. Reste des fichiers a la racine de streamlit_M1
    Get-ChildItem "streamlit_M1" -File | ForEach-Object {
        if (-not (Test-Path "dashboard/$($_.Name)")) {
            Move-Item $_.FullName -Destination "dashboard/" -Force
            Write-Host "   $($_.Name) -> dashboard/" -ForegroundColor Green
        } else {
            Write-Host "   $($_.Name) existe deja dans dashboard/ (ignore)" -ForegroundColor DarkGray
        }
    }

    # 2d. Supprimer streamlit_M1 s'il est vide
    $reste = Get-ChildItem "streamlit_M1" -Recurse -File
    if ($reste.Count -eq 0) {
        Remove-Item "streamlit_M1" -Recurse -Force
        Write-Host "   streamlit_M1 supprime (vide)." -ForegroundColor Green
    } else {
        Write-Host "   streamlit_M1 garde $($reste.Count) fichier(s) - a verifier." -ForegroundColor Magenta
    }
}

# ── 3. Ranger config.toml dans .streamlit/ ──
Write-Host ""
Write-Host "3. Rangement config.toml..." -ForegroundColor Yellow
if (Test-Path "dashboard/config.toml") {
    Move-Item "dashboard/config.toml" -Destination "dashboard/.streamlit/" -Force
    Write-Host "   config.toml -> dashboard/.streamlit/" -ForegroundColor Green
}

# ── 4. Resume ──
Write-Host ""
Write-Host "=== ARBORESCENCE FINALE ===" -ForegroundColor Cyan
Get-ChildItem -Directory | Select-Object -ExpandProperty Name | Sort-Object | ForEach-Object {
    Write-Host "  $_/" -ForegroundColor White
}
Write-Host ""
Write-Host "Notebooks ranges :" -ForegroundColor Yellow
Get-ChildItem "notebooks" -Recurse -Filter "*.ipynb" | ForEach-Object {
    $rel = $_.FullName.Replace((Get-Location).Path + "\", "")
    Write-Host "  $rel" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "[TERMINE]" -ForegroundColor Green
