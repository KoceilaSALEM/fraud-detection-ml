"""Test de bout en bout du pipeline d'inférence (5 modèles)."""
import sys
sys.path.insert(0, '.')
import pandas as pd, numpy as np, joblib, json, tempfile, shutil
from pathlib import Path
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler
import lightgbm as lgb

from src import config as cfg

TMP = Path(tempfile.mkdtemp())
(TMP / 'models').mkdir()
(TMP / 'outputs').mkdir()
(TMP / 'config').mkdir()
shutil.copy('config/config.yaml', TMP / 'config/config.yaml')


def gen_donnees(n=30000, seed=42):
    np.random.seed(seed)
    comptes = []
    for i in range(800):
        comptes += [f'P{i}'] * np.random.randint(1, 12)
    for i in range(60):
        comptes += [f'M{i}'] * np.random.randint(50, 200)
    for i in range(5):
        comptes += [f'PT{i}'] * np.random.randint(1500, 3000)
    comptes = (comptes * 3)[:n]
    np.random.shuffle(comptes)
    dates = pd.to_datetime('2025-10-01') + pd.to_timedelta(
        np.random.randint(0, 30 * 86400, n), unit='s')
    prefs = np.random.choice(['RC', 'MP', 'CO', 'CI', 'PP'], n)
    tid = [f'{p}{d:%y%m%d}.{np.random.randint(1, 500):04d}.A{i:06d}'
           for i, (p, d) in enumerate(zip(prefs, dates))]
    df = pd.DataFrame({
        cfg.COL_TRANSFER_ID: tid,
        cfg.COL_SENDER_ID: np.array(comptes, dtype=object),
        cfg.COL_RECVR_ID: np.random.choice([f'R{i}' for i in range(800)], n),
        cfg.COL_MONTANT: np.random.exponential(50000, n).astype('float32'),
        cfg.COL_S_AVANT: np.random.exponential(2e5, n).astype('float32'),
        cfg.COL_S_APRES: np.random.exponential(15e4, n).astype('float32'),
        cfg.COL_R_AVANT: np.random.exponential(1e5, n).astype('float32'),
        cfg.COL_R_APRES: np.random.exponential(12e4, n).astype('float32'),
        cfg.COL_STATUT: np.random.choice(['TS', 'TF'], n, p=[0.92, 0.08]),
        cfg.COL_SERVICE: np.random.choice(['RC', 'P2P', 'CASHOUT'], n),
        cfg.COL_SUBTYPE: np.random.choice(['RC', 'P2P'], n),
        cfg.COL_ERREUR: np.where(np.random.random(n) < 0.05, 60019, np.nan).astype('float32'),
        cfg.COL_DATE: dates,
        cfg.COL_VILLE: np.random.choice(['ANTANANARIVO', 'NOSY BE'], n),
        cfg.COL_GATEWAY: np.random.choice(['USSD', 'WEB'], n),
        cfg.COL_TAG: np.random.choice(['TOP UP', 'TRANSFER'], n),
        cfg.COL_ATTEMPT: np.random.choice(['Request Confirmed', 'No Response'], n),
        cfg.COL_S_TYPE: np.random.choice(['SUBSCRIBER', 'MERCHANT'], n),
        cfg.COL_R_TYPE: np.random.choice(['SUBSCRIBER', 'MERCHANT'], n),
        cfg.COL_COMM_PAID: np.random.exponential(100, n).astype('float32'),
        cfg.COL_COMM_RECV: np.random.exponential(150, n).astype('float32'),
        cfg.COL_SCHARGE_RCV: np.random.exponential(50, n).astype('float32'),
        cfg.COL_SCHARGE_PAID: np.random.exponential(30, n).astype('float32'),
        cfg.COL_RECON_FOR: pd.Series([None] * n, dtype=object),
    })
    for i in range(0, 200, 2):
        df.loc[i, cfg.COL_RECON_FOR] = df.loc[i + 1, cfg.COL_TRANSFER_ID]
    return df


# ════════ Phase 1 : artefacts d'entraînement ════════
print('--- Phase 1 : artefacts entrainement ---')
df_train = gen_donnees(n=30000, seed=1)
from src.features import (bloc_a_transaction, bloc_b_temporel,
                          bloc_c_comportemental, bloc_d_contextuel)
dft = df_train.sort_values([cfg.COL_SENDER_ID, cfg.COL_DATE]).reset_index(drop=True)
dft = bloc_a_transaction.build(dft)
dft = bloc_b_temporel.build(dft)
dft = bloc_c_comportemental.build(dft, verbose=False)
dft = bloc_d_contextuel.build(dft)

all_feats = [c for c in dft.columns if c.startswith('f_')]
FUITE = [c for c in all_feats if any(k in c for k in
         ['incoherence', 'delta_solde', 'solde_apres', 'statut', 'has_error', 'attempt'])]
FEAT = [c for c in all_feats if c not in FUITE]

m1_dir = TMP / 'models/M1_fraude'
m1_dir.mkdir()
vol = dft.groupby(cfg.COL_SENDER_ID, observed=True).size().rename('vol')
dft = dft.merge(vol, left_on=cfg.COL_SENDER_ID, right_index=True, how='left')


def seg(v):
    return ('faible' if v <= 10 else 'moyen' if v <= 100
            else 'eleve' if v <= 1000 else 'technique')


dft['SEG'] = dft['vol'].apply(seg)
X = dft[FEAT].apply(pd.to_numeric, errors='coerce').astype('float32')
X = X.fillna(X.median(numeric_only=True))
const = [c for c in FEAT if X[c].std() == 0]
FEAT = [c for c in FEAT if c not in const]
X = X[FEAT]
segs_ok = []
for s in dft['SEG'].unique():
    m = (dft['SEG'] == s).values
    if m.sum() < 100:
        continue
    sc = RobustScaler()
    Xs = sc.fit_transform(X[m])
    iso = IsolationForest(n_estimators=50, contamination=0.02, random_state=42).fit(Xs)
    joblib.dump(iso, m1_dir / f'iforest_{s}.pkl')
    joblib.dump(sc, m1_dir / f'scaler_{s}.pkl')
    segs_ok.append(s)
json.dump({'FEATURE_COLS': FEAT, 'segments': segs_ok, 'budget_jour': 50,
           'poids_ensemble': {'iso': 0.7, 'ecart_pairs': 0.3}},
          open(m1_dir / 'params_v2.json', 'w'))
print(f'M1 : {len(segs_ok)} segments')

m2_dir = TMP / 'models/M2_mules'
m2_dir.mkdir()
joblib.dump(RobustScaler().fit(np.random.randn(1000, 7)), m2_dir / 'scaler.pkl')
json.dump({'poids': {'transit': 0.35, 'diversite': 0.25, 'pagerank': 0.20, 'cluster': 0.20},
           'budget_mules': 100, 'dbscan_eps': 1.5, 'dbscan_min_samples': 5},
          open(m2_dir / 'params_v2.json', 'w'))
print('M2 : ok')

m5_dir = TMP / 'models/M5_echec'
m5_dir.mkdir()
y = (dft[cfg.COL_STATUT] == 'TF').astype(int)
lgbm = lgb.LGBMClassifier(n_estimators=30, verbose=-1).fit(X, y)
joblib.dump(lgbm, m5_dir / 'lgbm_model.pkl')
json.dump({'FEATURE_COLS': FEAT}, open(m5_dir / 'params.json', 'w'))
print('M5 : ok')

m6_dir = TMP / 'models/M6_reconciliation'
m6_dir.mkdir()
json.dump({'complementaires': {'TC': 'CO', 'XX': 'RC'}, 'precision_reelle': 0.866},
          open(m6_dir / 'params_v3.json', 'w'))
print('M6 : ok')

m4_dir = TMP / 'models/M4_commissions'
m4_dir.mkdir()
d4 = df_train[df_train[cfg.COL_STATUT] == 'TS'].copy()
d4['_jour'] = d4[cfg.COL_DATE].dt.date
agg = d4.groupby(['_jour', cfg.COL_SERVICE], observed=True).agg(
    volume=(cfg.COL_MONTANT, 'count'), montant=(cfg.COL_MONTANT, 'sum'),
    comm_paid=(cfg.COL_COMM_PAID, 'sum'), comm_recv=(cfg.COL_COMM_RECV, 'sum')).reset_index()
agg['taux_comm_paid'] = agg['comm_paid'] / (agg['montant'] + 1)
agg['taux_comm_recv'] = agg['comm_recv'] / (agg['montant'] + 1)
agg['comm_par_tx'] = (agg['comm_paid'] + agg['comm_recv']) / (agg['volume'] + 1)
stats = agg.groupby(cfg.COL_SERVICE, observed=True).agg(
    **{f'{m}_{s}': (m, s) for m in ['taux_comm_paid', 'taux_comm_recv', 'comm_par_tx']
       for s in ['mean', 'std']})
stats.to_pickle(m4_dir / 'stats_par_service.pkl')
json.dump({'contamination': 0.05}, open(m4_dir / 'params.json', 'w'))
print('M4 : ok')

from src.monitoring.drift import construire_reference
refs = {cfg.COL_MONTANT: construire_reference(df_train[cfg.COL_MONTANT]),
        '_volume': len(df_train)}
(TMP / 'models/drift_references.json').write_text(json.dumps(refs))
print('Drift refs : ok')

# ════════ Phase 2 : inférence sur nouveau lot ════════
print()
print('--- Phase 2 : PIPELINE INFERENCE sur nouveau lot ---')
df_nouveau = gen_donnees(n=25000, seed=99)

from src.inference.pipeline import PipelineInference
pipeline = PipelineInference(TMP)
rapport = pipeline.executer(df_nouveau)

print()
print('--- RESULTAT ---')
print('Modeles OK :', rapport['modeles_ok'])
print('Modeles KO :', rapport['modeles_ko'])
for m, stats in rapport['modeles'].items():
    print(f"  {m}: {stats.get('n_alertes', '?')} alertes en {stats.get('duree_s', '?')}s")
print('Drift :', rapport.get('drift', {}).get('verdict_global', 'N/A'))

rep_run = Path(rapport['repertoire_exports'])
exports = sorted(f.name for f in rep_run.iterdir())
print(f'Exports ({len(exports)}) : {exports}')

assert len(rapport['modeles_ok']) == 5, f"Attendu 5 OK, obtenu {rapport['modeles_ok']}"
shutil.rmtree(TMP)
print()
print('OK PIPELINE COMPLET 5/5 MODELES - INFERENCE BOUT EN BOUT VALIDEE')
