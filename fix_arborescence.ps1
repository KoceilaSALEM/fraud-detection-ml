# ============================================================
# fix_arborescence.ps1
# Corrige l'arborescence du projet ML Orange Money
# À lancer depuis le dossier racine "ML" dans le terminal VS Code
# Usage : .\fix_arborescence.ps1
# ============================================================

Write-Host ""
Write-Host "=== CORRECTION ARBORESCENCE ML ORANGE MONEY ===" -ForegroundColor Cyan
Write-Host ""

# Vérifier qu'on est au bon endroit
if (-not (Test-Path "data") -and -not (Test-Path "src")) {
    Write-Host "[ERREUR] Lance ce script depuis le dossier racine 'ML'." -ForegroundColor Red
    Write-Host "         (celui qui contient data/, src/, notebook/...)" -ForegroundColor Red
    exit 1
}

# ── 1. Créer les dossiers manquants (ne touche pas aux existants) ──
$dossiers = @(
    "data/raw",
    "data/processed",
    "notebooks",
    "notebooks/M1_fraude",
    "notebooks/M2_mules",
    "notebooks/M4_commissions",
    "notebooks/M5_echec",
    "notebooks/M6_reconciliation",
    "src/features",
    "models/M1_fraude",
    "models/M2_mules",
    "models/M4_commissions",
    "models/M5_echec",
    "models/M6_reconciliation",
    "outputs/M1_fraude",
    "outputs/M2_mules",
    "outputs/M4_commissions",
    "outputs/M5_echec",
    "outputs/M6_reconciliation",
    "dashboard/pages",
    "dashboard/components",
    "dashboard/.streamlit"
)

Write-Host "1. Creation des dossiers manquants..." -ForegroundColor Yellow
foreach ($d in $dossiers) {
    if (-not (Test-Path $d)) {
        New-Item -ItemType Directory -Path $d -Force | Out-Null
        Write-Host "   [CREE]  $d" -ForegroundColor Green
    } else {
        Write-Host "   [OK]    $d" -ForegroundColor DarkGray
    }
}

# ── 2. Renommer "notebook" -> "notebooks" si besoin ──
Write-Host ""
Write-Host "2. Verification dossier notebooks..." -ForegroundColor Yellow
if ((Test-Path "notebook") -and -not (Test-Path "notebooks/.keep")) {
    Write-Host "   Dossier 'notebook' (singulier) detecte." -ForegroundColor Yellow
    Write-Host "   Deplacement de son contenu vers 'notebooks/'..." -ForegroundColor Yellow
    Get-ChildItem "notebook" -Force | ForEach-Object {
        Move-Item $_.FullName -Destination "notebooks/" -Force
        Write-Host "      deplace : $($_.Name)" -ForegroundColor Green
    }
    Remove-Item "notebook" -Force
    Write-Host "   'notebook' supprime (vide)." -ForegroundColor Green
}

# ── 3. Deplacer les notebooks a la racine de notebooks/ vers leurs sous-dossiers ──
Write-Host ""
Write-Host "3. Rangement des notebooks par modele..." -ForegroundColor Yellow
$regles = @{
    "M1" = "notebooks/M1_fraude"
    "M2" = "notebooks/M2_mules"
    "M4" = "notebooks/M4_commissions"
    "M5" = "notebooks/M5_echec"
    "M6" = "notebooks/M6_reconciliation"
}
Get-ChildItem "notebooks" -Filter "*.ipynb" -File -ErrorAction SilentlyContinue | ForEach-Object {
    $nom = $_.Name
    $deplace = $false
    foreach ($cle in $regles.Keys) {
        if ($nom -match "_$cle" -or $nom -match "^$cle" -or $nom -match "${cle}_") {
            Move-Item $_.FullName -Destination "$($regles[$cle])/" -Force
            Write-Host "   $nom -> $($regles[$cle])/" -ForegroundColor Green
            $deplace = $true
            break
        }
    }
    if (-not $deplace) {
        Write-Host "   $nom -> reste a la racine notebooks/ (00, 01...)" -ForegroundColor DarkGray
    }
}

# ── 4. Signaler les dossiers residuels (SANS les supprimer) ──
Write-Host ""
Write-Host "4. Dossiers residuels a verifier manuellement :" -ForegroundColor Yellow
foreach ($res in @("outputs_modele4", "streamlit_M1")) {
    if (Test-Path $res) {
        Write-Host "   [A RANGER] '$res' existe encore." -ForegroundColor Magenta
        if ($res -eq "streamlit_M1") {
            Write-Host "              -> deplace son contenu utile vers 'dashboard/'" -ForegroundColor DarkGray
        }
        if ($res -eq "outputs_modele4") {
            Write-Host "              -> deplace son contenu vers 'outputs/M4_commissions/'" -ForegroundColor DarkGray
        }
    }
}

# ── 5. Resume final ──
Write-Host ""
Write-Host "=== ARBORESCENCE ACTUELLE ===" -ForegroundColor Cyan
Get-ChildItem -Directory | Select-Object -ExpandProperty Name | Sort-Object | ForEach-Object {
    Write-Host "  $_/" -ForegroundColor White
}

Write-Host ""
Write-Host "[TERMINE] Structure corrigee." -ForegroundColor Green
Write-Host "Les dossiers residuels (s'il y en a) n'ont PAS ete supprimes par securite." -ForegroundColor Yellow
Write-Host ""
