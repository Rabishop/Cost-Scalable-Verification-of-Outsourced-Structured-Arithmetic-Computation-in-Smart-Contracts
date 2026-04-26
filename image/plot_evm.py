"""
Read image/evm.txt and save image/evm.png (Direct execution vs GKR verification).
Run from repo root: python image/plot_evm.py
"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from evm_io import load_evm_table


def main():
    d = load_evm_table()
    N, direct_gas, gkr_gas = d["n"], d["direct"], d["gkr"]

    COLOR_DIRECT = "#2563eb"
    COLOR_GKR = "#ea580c"
    LW = 2.5
    MS = 9

    try:
        plt.style.use("seaborn-v0_8-whitegrid")
    except Exception:
        plt.style.use("ggplot")

    fig, ax = plt.subplots(figsize=(9, 5.5))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.grid(True, alpha=0.35, linestyle="-")

    ax.plot(
        N,
        direct_gas,
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
        gkr_gas,
        linestyle="--",
        marker="s",
        color=COLOR_GKR,
        linewidth=LW,
        markersize=MS,
        label="GKR verification",
        zorder=3,
    )

    ax.axvspan(256, 512, alpha=0.12, color="0.5", zorder=0)

    ax.set_xlabel(r"Input size $n$", fontsize=13, fontweight="medium")
    ax.set_ylabel("Gas", fontsize=13, fontweight="medium")
    ax.set_xscale("log", base=2)
    ax.set_xticks(N)
    ax.set_xticklabels([str(x) for x in N], fontsize=11)
    ax.tick_params(axis="both", labelsize=11)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f"{int(x):,}"))
    ax.legend(loc="upper left", fontsize=11, framealpha=0.95)
    ax.set_ylim(0, None)
    ax.margins(x=0.02)

    plt.tight_layout()
    out = HERE / "evm.png"
    # 600 DPI: print-grade raster (width×height in px ≈ figsize_inches × dpi)
    fig.savefig(out, dpi=600, bbox_inches="tight", facecolor="white", pad_inches=0.02)
    print(f"Saved: {out}")
    plt.close()


if __name__ == "__main__":
    main()
