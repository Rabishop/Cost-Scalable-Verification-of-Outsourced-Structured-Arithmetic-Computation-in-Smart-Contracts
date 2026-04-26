#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FFT电路GKR协议批量测试脚本
"""

import sys
import os
import subprocess
import time

# 修复Windows编码问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

INPUT_DIR = os.path.join(os.path.dirname(__file__), "input")
PROOF_DIR = os.path.join(os.path.dirname(__file__), "proof")

def run_test(test_name: str, input_file: str):
    """运行单个测试"""
    print(f"\n{'=' * 60}")
    print(f"测试: {test_name}")
    print(f"输入文件: {input_file}")
    print(f"{'=' * 60}\n")
    
    # 输入在 input/，证明输出到 proof/
    input_path = os.path.join(INPUT_DIR, input_file) if not os.path.isabs(input_file) else input_file
    base = os.path.splitext(os.path.basename(input_file))[0]
    proof_file = base + "_proof.txt"
    proof_path = os.path.join(PROOF_DIR, proof_file)
    
    # 生成证明
    print(f"[1/2] 生成证明...")
    try:
        result = subprocess.run(
            [sys.executable, 'gkr_prover_fft.py', input_path, proof_path],
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        print(result.stdout)
        if result.returncode != 0:
            print(f"❌ 生成证明失败:")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False
    
    # 验证证明
    print(f"\n[2/2] 验证证明...")
    try:
        result = subprocess.run(
            [sys.executable, 'gkr_verifier_fft.py', proof_path],
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        print(result.stdout)
        if result.returncode != 0:
            print(f"❌ 验证失败:")
            print(result.stderr)
            return False
        
        if "VERIFICATION PASSED" in result.stdout:
            print(f"✅ {test_name} 通过!")
            return True
        else:
            print(f"❌ {test_name} 失败!")
            return False
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False

def main():
    os.makedirs(PROOF_DIR, exist_ok=True)
    print("=" * 60)
    print("FFT电路GKR协议批量测试")
    print("=" * 60)
    
    # 测试用例
    tests = [
        ("2点FFT", "test_fft_2.txt"),
        ("4点FFT", "test_fft_4.txt"),
        ("8点FFT", "test_fft_8.txt"),
        ("16点FFT", "test_fft_16.txt"),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, input_file in tests:
        input_path = os.path.join(INPUT_DIR, input_file)
        if not os.path.exists(input_path):
            print(f"⚠️  跳过 {test_name}: 文件 {input_path} 不存在")
            continue
        
        if run_test(test_name, input_file):
            passed += 1
        else:
            failed += 1
    
    print(f"\n{'=' * 60}")
    print("测试结果汇总")
    print(f"{'=' * 60}")
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    print(f"总计: {passed + failed}")
    
    if failed == 0:
        print("\n✅ 所有测试通过!")
    else:
        print(f"\n❌ 有 {failed} 个测试失败")

if __name__ == "__main__":
    main()


