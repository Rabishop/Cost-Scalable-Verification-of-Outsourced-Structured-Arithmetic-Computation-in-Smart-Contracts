"""Load image/evm.txt (CSV). EVM gas columns + Starknet STRK columns. Used by plot_evm*.py."""
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent


def load_evm_table():
    path = HERE / "evm.txt"
    rows_n = []
    evm = []
    stark = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",")]
            if parts[0].lower() == "n":
                continue
            rows_n.append(int(parts[0]))
            evm.append([int(parts[1]), int(parts[2]), int(parts[3])])
            stark.append([float(parts[4]), float(parts[5]), float(parts[6])])
    evm_a = np.array(evm, dtype=np.int64)
    st_a = np.array(stark, dtype=np.float64)
    n = np.array(rows_n, dtype=np.int64)
    return {
        "n": n,
        "direct": evm_a[:, 0],
        "gkr": evm_a[:, 1],
        "plonk": evm_a[:, 2],
        "stark_direct": st_a[:, 0],
        "stark_gkr": st_a[:, 1],
        "stark_plonk": st_a[:, 2],
    }
