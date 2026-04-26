"""
Starknet: Direct + GKR + Plonk (STRK). Data: image/evm.txt
Output: image/stark-plonk.png

Run: python image/plot_stark_plonk.py
"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from evm_io import load_evm_table

COLOR_DIRECT = "#2563eb"
COLOR_GKR = "#ea580c"
COLOR_PLONK = "#7c3aed"
LW = 2.5
MS = 9
SAVEFIG_DPI = 600


def main():
    d = load_evm_table()
    N = d["n"]
    direct_strk = d["stark_direct"]
    gkr_strk = d["stark_gkr"]
    plonk_strk = d["stark_plonk"]

    try:
        plt.style.use("seaborn-v0_8-whitegrid")
    except Exception:
        plt.style.use("ggplot")

    fig, ax = plt.subplots(figsize=(9, 5.5))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.grid(True, alpha=0.35, linestyle="-")

    ax.axvspan(64, 128, alpha=0.12, color="0.5", zorder=0)

    ax.plot(
        N, direct_strk, linestyle="-", marker="o", color=COLOR_DIRECT,
        linewidth=LW, markersize=MS, label="Direct execution", zorder=3,
    )
    ax.plot(
        N, gkr_strk, linestyle="--", marker="s", color=COLOR_GKR,
        linewidth=LW, markersize=MS, label="GKR verification", zorder=3,
    )
    ax.plot(
        N, plonk_strk, linestyle="--", marker="^", color=COLOR_PLONK,
        linewidth=LW, markersize=MS, label="Plonk verification", zorder=3,
    )

    ax.set_xlabel(r"Input size $n$", fontsize=13, fontweight="medium")
    ax.set_ylabel("STRK", fontsize=13, fontweight="medium")
    ax.set_xscale("log", base=2)
    ax.set_xticks(N)
    ax.set_xticklabels([str(x) for x in N], fontsize=11)
    ax.tick_params(axis="both", labelsize=11)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f"{x:.4g}"))
    ax.legend(loc="upper left", fontsize=10, frameon=False, ncol=1)
    ax.set_ylim(0, None)
    ax.margins(x=0.02)

    plt.tight_layout()
    out = HERE / "stark-plonk.png"
    fig.savefig(out, dpi=SAVEFIG_DPI, bbox_inches="tight", facecolor="white", pad_inches=0.02)
    print(f"Saved: {out}")
    plt.close()


if __name__ == "__main__":
    main()
