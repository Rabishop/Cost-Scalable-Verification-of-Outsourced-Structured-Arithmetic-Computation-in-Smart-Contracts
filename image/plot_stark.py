"""
Starknet: Direct execution vs GKR verification — fee in STRK (from image/evm.txt).
Output: image/stark.png

Run from repo root: python image/plot_stark.py
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
LW = 2.5
MS = 9
SAVEFIG_DPI = 600


def main():
    d = load_evm_table()
    N = d["n"]
    direct_strk = d["stark_direct"]
    gkr_strk = d["stark_gkr"]

    try:
        plt.style.use("seaborn-v0_8-whitegrid")
    except Exception:
        plt.style.use("ggplot")

    fig, ax = plt.subplots(figsize=(9, 5.5))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.grid(True, alpha=0.35, linestyle="-")

    # Crossover band: GKR becomes cheaper than Direct (see starknet_four_methods_strk.md)
    ax.axvspan(64, 128, alpha=0.12, color="0.5", zorder=0)

    ax.plot(
        N,
        direct_strk,
        linestyle="-",
        marker="o",
        color=COLOR_DIRECT,
        linewidth=LW,
        markersize=MS,
        label="Direct execution",
        zorder=3,
    )
    ax.plot(
        N,
        gkr_strk,
        linestyle="--",
        marker="s",
        color=COLOR_GKR,
        linewidth=LW,
        markersize=MS,
        label="GKR verification",
        zorder=3,
    )

    ax.set_xlabel(r"Input size $n$", fontsize=13, fontweight="medium")
    ax.set_ylabel("STRK", fontsize=13, fontweight="medium")
    ax.set_xscale("log", base=2)
    ax.set_xticks(N)
    ax.set_xticklabels([str(x) for x in N], fontsize=11)
    ax.tick_params(axis="both", labelsize=11)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f"{x:.4g}"))
    ax.legend(loc="upper left", fontsize=11, frameon=False)
    ax.set_ylim(0, None)
    ax.margins(x=0.02)

    plt.tight_layout()
    out = HERE / "stark.png"
    fig.savefig(out, dpi=SAVEFIG_DPI, bbox_inches="tight", facecolor="white", pad_inches=0.02)
    print(f"Saved: {out}")
    plt.close()


if __name__ == "__main__":
    main()
