#!/usr/bin/env python3
"""
Starknet 占位合约（单 public_out + 定长 proof）：
Groth16 / Plonk 的 STRK 与 n 无关，表中所有 n 使用同一实测常数。

复现：`npm run estimate`（starknet_groth16_fft / starknet_plonk_fft）。
"""
from __future__ import annotations

# Katana 一次跑数（与 slides/starknet_four_methods_strk.md 一致）
GROTH16_STRK_CONST = 0.0059258880
PLONK_STRK_CONST = 0.0176366880

ALL_N = [2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048]


def main() -> None:
    print("Groth16 / Plonk（单 public_out）：STRK 为常数，无需对 n 线性外推。")
    print(f"  Groth16: {GROTH16_STRK_CONST:.10f} STRK")
    print(f"  Plonk:   {PLONK_STRK_CONST:.10f} STRK")
    print()
    print("n\tGroth16\tPlonk\tsource")
    for n in ALL_N:
        print(f"{n}\t{GROTH16_STRK_CONST:.10f}\t{PLONK_STRK_CONST:.10f}\tconstant")


if __name__ == "__main__":
    main()
