"""
Package features — les 4 blocs de feature engineering.

Usage :
    from src.features import bloc_a_transaction, bloc_b_temporel
    from src.features import bloc_c_comportemental, bloc_d_contextuel

    df = bloc_a_transaction.build(df)
    df = bloc_b_temporel.build(df)
    df = bloc_c_comportemental.build(df)   # df doit être trié !
    df = bloc_d_contextuel.build(df)
"""
from . import bloc_a_transaction
from . import bloc_b_temporel
from . import bloc_c_comportemental
from . import bloc_d_contextuel
