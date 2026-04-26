#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键运行 128 点 FFT 的 Prover + Verifier 测试。
依赖：需将 PYTHONPATH 指向包含 gkr_prover.py / gkr_verifier.py 的目录（如 2026-01-04-gkr-project/python）。
"""
import sys
import os
import time

# 若存在兄弟项目中的 python 目录，则加入 path
_fft_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_fft_dir)
_python_path = os.path.join(_project_root, "python")
_alt_python = os.path.join(os.path.dirname(_project_root), "2026-01-04-gkr-project", "python")
if os.path.isdir(_python_path):
    sys.path.insert(0, _python_path)
elif os.path.isdir(_alt_python):
    sys.path.insert(0, _alt_python)

def main():
    from gkr_prover_fft import build_fft_circuit, parse_input_file, generate_proof_file, GKRProver
    from gkr_verifier_fft import parse_proof_file, FFTGKRVerifier, build_fft_circuit as build_circuit_v

    n = 128
    input_dir = os.path.join(_fft_dir, "input")
    proof_dir = os.path.join(_fft_dir, "proof")
    input_file = os.path.join(input_dir, "test_fft_128.txt")
    proof_file = os.path.join(proof_dir, "test_fft_128_proof.txt")

    if not os.path.exists(input_file):
        print(f"输入文件不存在: {input_file}")
        sys.exit(1)

    print("=" * 60)
    print("128 点 FFT GKR 测试")
    print("=" * 60)

    # Prover
    print("\n[1/2] Prover 生成证明...")
    t0 = time.perf_counter()
    inputs = parse_input_file(input_file)
    circuit = build_fft_circuit(n)
    prover = GKRProver(circuit, inputs)
    proof = prover.generate_proof()
    generate_proof_file(proof, inputs, proof_file)
    t_prover = (time.perf_counter() - t0) * 1000
    print(f"  电路输出: {proof.output}, 证明层数: {len(proof.sumcheck_proofs)}")
    print(f"  Prover 耗时: {t_prover:.0f} ms")

    # Verifier
    print("\n[2/2] Verifier 验证证明...")
    t0 = time.perf_counter()
    proof_data, inputs_v = parse_proof_file(proof_file)
    circuit_v = build_circuit_v(len(inputs_v))
    verifier = FFTGKRVerifier(circuit_v, inputs_v)
    ok = verifier.verify_proof(proof_data)
    t_verifier = (time.perf_counter() - t0) * 1000
    print(f"  Verifier 耗时: {t_verifier:.0f} ms")

    print("\n" + "=" * 60)
    if ok:
        print("VERIFICATION PASSED")
    else:
        print("VERIFICATION FAILED")
    print("=" * 60)
    print(f"128 点汇总: Prover {t_prover:.0f} ms, Verifier {t_verifier:.0f} ms")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
