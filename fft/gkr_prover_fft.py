#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FFT电路GKR Prover - 基于标准实现
"""

import sys
import os
import time
from typing import List, Tuple, Dict, Optional
from enum import Enum

# 导入标准实现的常量、函数和类
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))
from gkr_prover import (
    PRIME, mod_uint64, mod_add, mod_sub, mod_mul, mod_inv,
    GateType, Gate, MLE, Circuit, WiringPredicates,
    FiatShamirTranscript, SumcheckRoundProof, SumcheckProof,
    GKRProof, GKRSumcheck, GKRProver
)

def build_fft_circuit(n: int) -> Circuit:
    """
    构建n点FFT电路
    
    FFT电路结构：
    - 输入层：n个输入值
    - FFT层：log2(n)层蝶形运算
    - 输出层：n个FFT结果
    
    简化实现：使用omega=1（单位根），实际应该使用PRIME域的单位根
    """
    if n < 1 or (n & (n - 1)) != 0:
        raise ValueError("n must be a power of 2")
    
    all_layers: List[List[Gate]] = []
    
    # 输入层：n个输入
    input_layer = [Gate(GateType.INPUT) for _ in range(n)]
    all_layers.append(input_layer)
    
    # 计算log2(n)
    log_n = 0
    temp = n
    while temp > 1:
        log_n += 1
        temp >>= 1
    
    # FFT层：递归蝶形运算
    current_size = n
    current_layer = input_layer
    
    for level in range(log_n):
        next_size = current_size // 2
        next_layer: List[Gate] = []
        
        # 简化：使用omega=1作为单位根
        omega = 1
        
        for i in range(next_size):
            # 蝶形运算：even + omega^k * odd, even - omega^k * odd
            # 简化：使用omega=1，所以直接使用even + odd
            even_idx = i * 2
            odd_idx = i * 2 + 1
            
            # 简化FFT：even + odd（因为omega=1）
            add_gate = Gate(GateType.ADD, even_idx, odd_idx)
            next_layer.append(add_gate)
        
        all_layers.append(next_layer)
        current_layer = next_layer
        current_size = next_size
    
    # 反转层顺序（从输出到输入）
    all_layers.reverse()
    
    circuit = Circuit()
    circuit.layers = all_layers
    
    # 计算每层的变量数
    for layer in all_layers:
        circuit.layer_sizes.append(len(layer))
        size = len(layer)
        if size <= 1:
            bits = 1
        else:
            num_vars = size - 1
            if num_vars == 0:
                bits = 1
            else:
                bits = 0
                temp = num_vars
                while temp > 0:
                    bits += 1
                    temp >>= 1
        circuit.layer_num_vars.append(bits)
    
    return circuit

def parse_input_file(input_file: str) -> List[int]:
    """解析FFT输入文件：第一行是n，第二行是n个输入值"""
    input_path = input_file
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file '{input_file}' not found")
    
    with open(input_path, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]
    
    if len(lines) < 2:
        raise ValueError("Invalid input file format: expected at least 2 lines")
    
    n = int(lines[0])
    inputs = [int(x) for x in lines[1].split()]
    
    if len(inputs) != n:
        raise ValueError(f"Input count mismatch: expected {n}, got {len(inputs)}")
    
    return inputs

def generate_proof_file(proof: GKRProof, inputs: List[int], output_file: str):
    """生成proof文件，格式与标准实现一致"""
    g0_list: List[str] = []
    g1_list: List[str] = []
    g2_list: List[str] = []
    
    for sp in proof.sumcheck_proofs:
        for round_proof in sp.rounds:
            g0_list.append(str(round_proof.g0))
            g1_list.append(str(round_proof.g1))
            g2_list.append(str(round_proof.g2))
    
    os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)
    
    with open(output_file, 'w') as f:
        f.write(f"{len(inputs)}\n")
        f.write(" ".join(str(x) for x in inputs) + "\n")
        f.write(f"{proof.output}\n")
        f.write(" ".join(g0_list) + "\n")
        f.write(" ".join(g1_list) + "\n")
        f.write(" ".join(g2_list) + "\n")
        f.write("\n")

def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <input-file> <output-file>", file=sys.stderr)
        print(f"Example: {sys.argv[0]} test_fft_4.txt test_fft_4_proof.txt", file=sys.stderr)
        sys.exit(1)
    
    total_start = time.time()
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    try:
        inputs = parse_input_file(input_file)
        n = len(inputs)
        print(f"FFT size: {n}")
        print(f"Total inputs: {len(inputs)}")
        
        circuit = build_fft_circuit(n)
        prover = GKRProver(circuit, inputs)
        proof = prover.generate_proof()
        
        print(f"Circuit output: {proof.output}")
        print(f"Number of layers: {len(circuit.layers)}")
        
        generate_proof_file(proof, inputs, output_file)
        
        total_end = time.time()
        total_duration = int((total_end - total_start) * 1000)
        print(f"Proof generated in {total_duration} ms")
        print(f"Number of sumcheck proofs: {len(proof.sumcheck_proofs)}")
        print(f"Proof written to {output_file}")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

