#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 Python 生成的 GKR proof 导出为合约调用参数（用于 Remix / 脚本 gas 比较）。
依赖：需能 import gkr_verifier_fft（PYTHONPATH 含 2026-01-04-gkr-project/python）。
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '2026-01-04-gkr-project', 'python'))
proof_dir = os.path.join(os.path.dirname(__file__), '..', 'proof')
input_dir = os.path.join(os.path.dirname(__file__), '..', 'input')

def main():
    proof_file = os.path.join(proof_dir, "test_fft_8_proof.txt")
    input_file = os.path.join(input_dir, "test_fft_8.txt")
    if len(sys.argv) >= 2:
        proof_file = sys.argv[1]
    if len(sys.argv) >= 3:
        input_file = sys.argv[2]

    from gkr_verifier_fft import parse_proof_file, build_fft_circuit
    from gkr_verifier import mod_add

    proof, inputs = parse_proof_file(proof_file)
    n = len(inputs)
    circuit = build_fft_circuit(n)

    g0_list, g1_list, g2_list = [], [], []
    for sp in proof.sumcheck_proofs:
        for r in sp.rounds:
            g0_list.append(r.g0)
            g1_list.append(r.g1)
            g2_list.append(r.g2)

    round_counts = []
    for layer_idx in range(len(circuit.layers) - 1):
        from gkr_verifier import WiringPredicates
        w = WiringPredicates(circuit, layer_idx)
        round_counts.append(2 * w.ab_vars)

    out = {
        "n": n,
        "output": proof.output,
        "input": [int(x) for x in inputs],
        "g0": [str(x) for x in g0_list],
        "g1": [str(x) for x in g1_list],
        "g2": [str(x) for x in g2_list],
        "roundCounts": [int(x) for x in round_counts],
    }
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
