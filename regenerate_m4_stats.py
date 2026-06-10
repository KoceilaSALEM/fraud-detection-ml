import pandas as pd
from pathlib import Path

MODEL_DIR = Path("models/M4_commissions")
OUTPUT_DIR = Path("outputs/M4_commissions")

agg = pd.read_parquet(OUTPUT_DIR / "scored.parquet")

COL_SERVICE = "SERVICE_TYPE"
METRIQUES_Z = ["taux_comm_paid", "comm_par_tx", "scharge_par_tx"]

metriques_dispo = [m for m in METRIQUES_Z if m in agg.columns]

stats = agg.groupby(COL_SERVICE)[metriques_dispo].agg(["mean", "std"])

stats.columns = [f"{m}_{s}" for m, s in stats.columns]

for c in stats.columns:
    if c.endswith("_std"):
        stats[c] = stats[c].replace(0, 1e-9).fillna(1e-9)

MODEL_DIR.mkdir(parents=True, exist_ok=True)

stats.to_json(MODEL_DIR / "stats_par_service.json", orient="index", indent=2)
stats.to_csv(MODEL_DIR / "stats_par_service.csv", encoding="utf-8-sig")

print("OK stats_par_service régénéré")
print("Shape :", stats.shape)
print("Services :", list(stats.index))
print("Colonnes :", list(stats.columns))
