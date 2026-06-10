# =============================================================
# CONVERSION CORRIGÉE — schéma figé pour éviter les conflits de type
# Remplace la cellule §2 du notebook 01_conversion_parquet
# =============================================================

def nettoyer_chunk(chunk):
    """Typage stable d'un chunk : force les types pour un schéma constant."""
    # Numériques -> float64 systématique
    for col in cfg.COLS_NUM:
        if col in chunk.columns:
            chunk[col] = pd.to_numeric(chunk[col], errors='coerce').astype('float64')

    # Dates -> datetime64
    for col in cfg.COLS_DATE:
        if col in chunk.columns:
            chunk[col] = pd.to_datetime(chunk[col], errors='coerce', dayfirst=True)

    # TOUTES les autres colonnes -> string (object) pour éviter
    # qu'une colonne vide soit float dans un chunk et texte dans un autre
    cols_string = [c for c in chunk.columns
                   if c not in cfg.COLS_NUM and c not in cfg.COLS_DATE]
    for col in cols_string:
        chunk[col] = chunk[col].astype(str).replace('nan', None)

    return chunk


cfg.PARQUET_PATH.parent.mkdir(parents=True, exist_ok=True)

print('Conversion en cours (plusieurs minutes)...')
debut = time.time()
writer = None
schema_ref = None   # schéma figé du premier chunk
n_total = 0

reader = pd.read_csv(
    cfg.CSV_RAW, sep=cfg.CSV_SEP, encoding=cfg.CSV_ENCODING,
    chunksize=cfg.CHUNK_SIZE, low_memory=False,
    usecols=lambda c: c in presentes
)

for i, chunk in enumerate(reader, 1):
    chunk = nettoyer_chunk(chunk)
    n_total += len(chunk)

    if schema_ref is None:
        # Premier chunk : on fige le schéma et on réordonne les colonnes
        table = pa.Table.from_pandas(chunk, preserve_index=False)
        schema_ref = table.schema
        writer = pq.ParquetWriter(cfg.PARQUET_PATH, schema_ref, compression='snappy')
    else:
        # Chunks suivants : on force le même schéma
        table = pa.Table.from_pandas(chunk, preserve_index=False, schema=schema_ref)

    writer.write_table(table)
    if i % 5 == 0:
        print(f'  Chunk {i:3d} | {n_total:,} lignes | {time.time()-debut:.0f}s')

if writer:
    writer.close()

duree = time.time() - debut
taille_pq  = cfg.PARQUET_PATH.stat().st_size / (1024**3)
taille_csv = os.path.getsize(cfg.CSV_RAW) / (1024**3)
print(f'\nTERMINÉ en {duree:.0f}s')
print(f'   Lignes      : {n_total:,}')
print(f'   Parquet     : {taille_pq:.2f} Go')
print(f'   Compression : {taille_csv/taille_pq:.1f}x')
