# ============================================================
# installer_src.ps1
# Copie le socle src/ depuis ML_Orange_Money.zip vers le projet
# À lancer depuis le dossier racine "ML"
# Prérequis : avoir ML_Orange_Money.zip dans le dossier ML/
# ============================================================

Write-Host ""
Write-Host "=== INSTALLATION DU SOCLE src/ ===" -ForegroundColor Cyan
Write-Host ""

$zip = "ML_Orange_Money.zip"

if (-not (Test-Path $zip)) {
    Write-Host "[ERREUR] $zip introuvable dans le dossier courant." -ForegroundColor Red
    Write-Host "         Place le zip ici puis relance." -ForegroundColor Red
    exit 1
}

# 1. Extraire dans un dossier temporaire
$tmp = "_tmp_extract"
if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
Write-Host "1. Extraction du zip..." -ForegroundColor Yellow
Expand-Archive -Path $zip -DestinationPath $tmp -Force

$source = Join-Path $tmp "ML_Orange_Money"

# 2. Copier src/ (le socle réutilisable)
Write-Host "2. Copie de src/..." -ForegroundColor Yellow
if (Test-Path "$source/src") {
    Copy-Item "$source/src/*" -Destination "src/" -Recurse -Force
    Write-Host "   src/config.py" -ForegroundColor Green
    Write-Host "   src/data_loader.py" -ForegroundColor Green
    Write-Host "   src/utils.py" -ForegroundColor Green
    Write-Host "   src/features/ (4 blocs + __init__)" -ForegroundColor Green
}

# 3. Copier les composants dashboard manquants (sans ecraser app.py existant)
Write-Host "3. Composants dashboard..." -ForegroundColor Yellow
if (Test-Path "$source/dashboard/components") {
    Copy-Item "$source/dashboard/components/*" -Destination "dashboard/components/" -Recurse -Force
    Write-Host "   dashboard/components/ (theme, kpi, charts)" -ForegroundColor Green
}

# 4. Copier README et requirements s'ils n'existent pas
Write-Host "4. Fichiers racine..." -ForegroundColor Yellow
foreach ($f in @("README.md", "requirements.txt", ".gitignore")) {
    if (-not (Test-Path $f) -and (Test-Path "$source/$f")) {
        Copy-Item "$source/$f" -Destination "." -Force
        Write-Host "   $f" -ForegroundColor Green
    } else {
        Write-Host "   $f existe deja (ignore)" -ForegroundColor DarkGray
    }
}

# 5. Notebook de conversion Parquet
if ((Test-Path "$source/notebooks/01_conversion_parquet.ipynb") -and -not (Test-Path "notebooks/01_conversion_parquet.ipynb")) {
    Copy-Item "$source/notebooks/01_conversion_parquet.ipynb" -Destination "notebooks/" -Force
    Write-Host "   notebooks/01_conversion_parquet.ipynb" -ForegroundColor Green
}

# 6. Nettoyer le temporaire
Remove-Item $tmp -Recurse -Force
Write-Host ""
Write-Host "5. Verification import..." -ForegroundColor Yellow
python -c "import sys; sys.path.insert(0,'.'); from src import config; print('   OK : config.py importe, COL_MONTANT =', config.COL_MONTANT)"

Write-Host ""
Write-Host "=== CONTENU src/ ===" -ForegroundColor Cyan
Get-ChildItem "src" -Recurse -File | Where-Object { $_.Name -notlike "*.pyc" } | ForEach-Object {
    $rel = $_.FullName.Replace((Get-Location).Path + "\", "")
    Write-Host "  $rel" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "[TERMINE] Socle src/ installe." -ForegroundColor Green
