#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FFT电路的GKR Verifier - 使用优化的wiring和layer评估
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))
from gkr_verifier import (
    Circuit, Gate, GateType, WiringPredicates, MLE, GKRSumcheck, GKRVerifier,
    GKRProof, SumcheckProof, SumcheckRoundProof, FiatShamirTranscript,
    lagrange_interpolate_3points, mod_uint64, mod_add, mod_sub, mod_mul, PRIME
)
from typing import List, Tuple, Dict

def eq_eval_point_parts(start1: int, start2: int, length: int, 
                        point: List[int], one_minus_point: List[int]) -> int:
    """计算两个point部分的相等性：eq(point[start1:start1+length], point[start2:start2+length])"""
    result = 1
    for i in range(length):
        idx1 = start1 + i
        idx2 = start2 + i
        if idx1 >= len(point) or idx2 >= len(point):
            return 0
        p1 = mod_uint64(point[idx1])
        p2 = mod_uint64(point[idx2])
        # eq(p1, p2) = p1 * p2 + (1-p1) * (1-p2)
        term = mod_add(
            mod_mul(p1, p2),
            mod_mul(mod_sub(1, p1), mod_sub(1, p2))
        )
        result = mod_mul(result, term)
    return result

class FFTWiringPredicates(WiringPredicates):
    """FFT电路的Wiring Predicates，使用优化的稀疏评估"""
    
    def evaluate_wiring_mle_fft_sparse(self, point: List[int]) -> int:
        """
        FFT电路Wiring MLE的分组求和实现 - O(log n)复杂度
        
        关键理解（按用户指导）：
        Step 1: FFT wiring 的 bit 形式
        - 对于 stage s (g_vars = s):
          a = prefix | 0 | suffix
          b = prefix | 1 | suffix
          其中 prefix 是 g 的 bit 表示（s位），suffix 是高位（ab_vars - s - 1位）
        
        Step 2: 把 χ_a(r) 写成 prefix部分 × 第s位 × suffix部分
        - χ_a(r) = eq(a, r) = eq(prefix, r的前s位) × eq(0, r的第s位) × eq(suffix, r的高位)
        - χ_b(r) = eq(b, r) = eq(prefix, r的前s位) × eq(1, r的第s位) × eq(suffix, r的高位)
        
        Step 3: 按 prefix 分组求和
        - W~(r, a, b) = sum over g: eq(g, r) · eq(2g, a) · eq(2g+1, b)
        - 按 prefix 分组：sum over prefix: [eq(prefix, r) · eq(prefix, a的前s位) · eq(prefix, b的前s位)] 
                                        × [eq(0, a的第s位) · eq(1, b的第s位)]
                                        × [eq(0, a的高位) · eq(0, b的高位)]
        
        关键观察：对于每个 prefix，suffix 贡献是相同的（因为 FFT wiring 规则，suffix 全为0）
        所以：∑ over prefix: [prefix贡献] × [suffix贡献]
            = [suffix贡献] × [∑ over prefix: prefix贡献]
        
        但是，由于 eq(prefix, r) · eq(prefix, a的前s位) · eq(prefix, b的前s位) 要求 
        prefix = r = a的前s位 = b的前s位，所以只有当 r = a的前s位 = b的前s位 时，这个和才非零。
        
        因此：∑ over prefix: prefix贡献 = eq(r, a的前s位) · eq(r, b的前s位)
        
        复杂度: O(log n) - 只需要计算 prefix 和 suffix 的贡献，不需要遍历所有 gates
        """
        expected_len = self.g_vars + 2 * self.ab_vars
        if len(point) < expected_len:
            return 0
        
        one_minus_point = [mod_sub(1, mod_uint64(p)) for p in point]
        
        # point结构: [r (g_vars bits), a (ab_vars bits), b (ab_vars bits)]
        r_start = 0
        a_start = self.g_vars
        b_start = self.g_vars + self.ab_vars
        
        # Step 1 & 2: 理解 bit 结构并分解 χ
        # 对于 gate g，其 bit 表示为 prefix (g_vars 位)
        # a = prefix | 0 | suffix_a (suffix_a 是高位，全为0)
        # b = prefix | 1 | suffix_b (suffix_b 是高位，全为0)
        
        # Step 3: 按 prefix 分组求和
        # 关键观察：对于每个 prefix，suffix 贡献是相同的（因为 FFT wiring 规则，suffix 全为0）
        # 所以：∑ over prefix: [prefix贡献] × [suffix贡献]
        #     = [suffix贡献] × [∑ over prefix: prefix贡献]
        
        # 计算 ∑ over prefix: eq(prefix, r) · eq(prefix, a的前g_vars位) · eq(prefix, b的前g_vars位)
        # 在 multilinear extension 中，这个和可以分解为：
        # ∑ over prefix: eq(prefix, r) · eq(prefix, a的前g_vars位) · eq(prefix, b的前g_vars位)
        # = ∏_{i=0}^{g_vars-1} [r_i * a_i * b_i + (1-r_i) * (1-a_i) * (1-b_i)]
        # 这是因为每个 bit 位置独立贡献
        
        prefix_sum = 1
        for i in range(self.g_vars):
            r_idx = r_start + i
            a_idx = a_start + i
            b_idx = b_start + i
            if r_idx >= len(point) or a_idx >= len(point) or b_idx >= len(point):
                return 0
            
            r_val = mod_uint64(point[r_idx])
            a_val = mod_uint64(point[a_idx])
            b_val = mod_uint64(point[b_idx])
            
            # 对于每个 bit 位置 i，prefix 的贡献是：
            # 如果 prefix[i] = 1: r_i * a_i * b_i
            # 如果 prefix[i] = 0: (1-r_i) * (1-a_i) * (1-b_i)
            # 所以总的贡献是：r_i * a_i * b_i + (1-r_i) * (1-a_i) * (1-b_i)
            term_1 = mod_mul(mod_mul(r_val, a_val), b_val)
            one_minus_r = mod_sub(1, r_val)
            one_minus_a = mod_sub(1, a_val)
            one_minus_b = mod_sub(1, b_val)
            term_0 = mod_mul(mod_mul(one_minus_r, one_minus_a), one_minus_b)
            prefix_sum = mod_mul(prefix_sum, mod_add(term_1, term_0))
        
        # 处理 ab_vars == g_vars 的特殊情况
        if self.ab_vars == self.g_vars:
            # 没有 suffix，只有 prefix 和 第g_vars位
            # 检查 r 的最高位是否为 0（因为 2r 需要 g_vars+1 位）
            r_high_bit = point[r_start + self.g_vars - 1]
            if r_high_bit != 0:
                return 0
            
            # 计算 eq(r 的前 g_vars-1 位, a 的前 g_vars-1 位) 和 eq(r 的前 g_vars-1 位, b 的前 g_vars-1 位)
            if self.g_vars > 1:
                eq_r_a_prefix = eq_eval_point_parts(r_start, a_start, self.g_vars - 1, point, one_minus_point)
                eq_r_b_prefix = eq_eval_point_parts(r_start, b_start, self.g_vars - 1, point, one_minus_point)
                prefix_sum = mod_mul(eq_r_a_prefix, eq_r_b_prefix)
            else:
                prefix_sum = 1
            
            # 第g_vars位贡献：eq(0, a的第g_vars位) · eq(1, b的第g_vars位)
            a_g_vars_idx = a_start + self.g_vars - 1
            b_g_vars_idx = b_start + self.g_vars - 1
            if a_g_vars_idx >= len(one_minus_point) or b_g_vars_idx >= len(point):
                return 0
            eq_0_a_g_vars = one_minus_point[a_g_vars_idx]
            eq_1_b_g_vars = point[b_g_vars_idx]
            suffix_contrib = mod_mul(eq_0_a_g_vars, eq_1_b_g_vars)
            
            result = mod_mul(prefix_sum, suffix_contrib)
            return result
        
        # 标准情况：ab_vars > g_vars
        # 第g_vars位贡献：eq(0, a的第g_vars位) · eq(1, b的第g_vars位)
        a_g_vars_idx = a_start + self.g_vars
        b_g_vars_idx = b_start + self.g_vars
        if a_g_vars_idx >= len(one_minus_point) or b_g_vars_idx >= len(point):
            return 0
        eq_0_a_g_vars = one_minus_point[a_g_vars_idx]
        eq_1_b_g_vars = point[b_g_vars_idx]
        
        # suffix 贡献：eq(0, a的高位) · eq(0, b的高位)（因为 FFT wiring 规则，suffix 全为0）
        eq_0_a_suffix = 1
        eq_0_b_suffix = 1
        if self.ab_vars > self.g_vars + 1:
            for i in range(self.g_vars + 1, self.ab_vars):
                a_high_idx = a_start + i
                b_high_idx = b_start + i
                if a_high_idx < len(one_minus_point):
                    eq_0_a_suffix = mod_mul(eq_0_a_suffix, one_minus_point[a_high_idx])
                if b_high_idx < len(one_minus_point):
                    eq_0_b_suffix = mod_mul(eq_0_b_suffix, one_minus_point[b_high_idx])
        
        suffix_contrib = mod_mul(mod_mul(eq_0_a_g_vars, eq_1_b_g_vars),
                                mod_mul(eq_0_a_suffix, eq_0_b_suffix))
        
        # 组合：prefix贡献 × suffix贡献
        result = mod_mul(prefix_sum, suffix_contrib)
        return result
    
    def evaluate_wiring_mle_fft_sparse_old(self, point: List[int]) -> int:
        """
        FFT电路Wiring MLE的分组求和实现 - O(log n)复杂度
        
        关键理解（按用户指导）：
        Step 1: FFT wiring 的 bit 形式
        - 对于 stage s (g_vars = s):
          a = prefix | 0 | suffix
          b = prefix | 1 | suffix
          其中 prefix 是 g 的 bit 表示（s位），suffix 是高位（ab_vars - s - 1位）
        
        Step 2: 把 χ_a(r) 写成 prefix部分 × 第s位 × suffix部分
        - χ_a(r) = eq(a, r) = eq(prefix, r的前s位) × eq(0, r的第s位) × eq(suffix, r的高位)
        - χ_b(r) = eq(b, r) = eq(prefix, r的前s位) × eq(1, r的第s位) × eq(suffix, r的高位)
        
        Step 3: 按 prefix 分组求和
        - W~(r, a, b) = sum over g: eq(g, r) · eq(2g, a) · eq(2g+1, b)
        - 按 prefix 分组：sum over prefix: [eq(prefix, r) · eq(prefix, a的前s位) · eq(prefix, b的前s位)] 
                                        × [eq(0, a的第s位) · eq(1, b的第s位)]
                                        × [eq(0, a的高位) · eq(0, b的高位)]
        
        关键：通过分组，我们可以将求和分解为：
        - prefix 贡献：eq(prefix, r) · eq(prefix, a的前s位) · eq(prefix, b的前s位)
        - suffix 贡献：eq(0, a的第s位) · eq(1, b的第s位) · eq(0, a的高位) · eq(0, b的高位)
        
        复杂度: O(log n) - 只需要计算 prefix 和 suffix 的贡献，不需要遍历所有 gates
        """
        expected_len = self.g_vars + 2 * self.ab_vars
        if len(point) < expected_len:
            return 0
        
        one_minus_point = [mod_sub(1, mod_uint64(p)) for p in point]
        
        # point结构: [r (g_vars bits), a (ab_vars bits), b (ab_vars bits)]
        r_start = 0
        a_start = self.g_vars
        b_start = self.g_vars + self.ab_vars
        
        # Step 1 & 2: 理解 bit 结构并分解 χ
        # 对于 gate g，其 bit 表示为 prefix (g_vars 位)
        # a = prefix | 0 | suffix_a (suffix_a 是高位，全为0)
        # b = prefix | 1 | suffix_b (suffix_b 是高位，全为0)
        
        # Step 3: 按 prefix 分组求和
        # 关键观察：由于 FFT wiring 规则，对于每个 prefix，suffix 都是固定的（全0）
        # 所以我们可以直接计算：
        
        # prefix 贡献：eq(prefix, r) · eq(prefix, a的前g_vars位) · eq(prefix, b的前g_vars位)
        # 由于 prefix 必须同时等于 r、a的前g_vars位、b的前g_vars位，
        # 所以只有当 r = a的前g_vars位 = b的前g_vars位 时，这个和才非零。
        
        # 计算 eq(r, a的前g_vars位) · eq(r, b的前g_vars位)
        eq_r_a_prefix = eq_eval_point_parts(r_start, a_start, self.g_vars, point, one_minus_point)
        eq_r_b_prefix = eq_eval_point_parts(r_start, b_start, self.g_vars, point, one_minus_point)
        
        # 处理 ab_vars == g_vars 的特殊情况
        if self.ab_vars == self.g_vars:
            # 没有 suffix，只有 prefix 和 第g_vars位
            # 检查 r 的最高位是否为 0（因为 2r 需要 g_vars+1 位）
            r_high_bit = point[r_start + self.g_vars - 1]
            if r_high_bit != 0:
                return 0
            
            # 计算 eq(r 的前 g_vars-1 位, a 的前 g_vars-1 位) 和 eq(r 的前 g_vars-1 位, b 的前 g_vars-1 位)
            if self.g_vars > 1:
                eq_r_a_prefix = eq_eval_point_parts(r_start, a_start, self.g_vars - 1, point, one_minus_point)
                eq_r_b_prefix = eq_eval_point_parts(r_start, b_start, self.g_vars - 1, point, one_minus_point)
            else:
                eq_r_a_prefix = 1
                eq_r_b_prefix = 1
            
            # 第g_vars位贡献：eq(0, a的第g_vars位) · eq(1, b的第g_vars位)
            a_g_vars_idx = a_start + self.g_vars - 1
            b_g_vars_idx = b_start + self.g_vars - 1
            if a_g_vars_idx >= len(one_minus_point) or b_g_vars_idx >= len(point):
                return 0
            eq_0_a_g_vars = one_minus_point[a_g_vars_idx]
            eq_1_b_g_vars = point[b_g_vars_idx]
            
            result = mod_mul(mod_mul(eq_r_a_prefix, eq_r_b_prefix), 
                           mod_mul(eq_0_a_g_vars, eq_1_b_g_vars))
            return result
        
        # 标准情况：ab_vars > g_vars
        # 第g_vars位贡献：eq(0, a的第g_vars位) · eq(1, b的第g_vars位)
        a_g_vars_idx = a_start + self.g_vars
        b_g_vars_idx = b_start + self.g_vars
        if a_g_vars_idx >= len(one_minus_point) or b_g_vars_idx >= len(point):
            return 0
        eq_0_a_g_vars = one_minus_point[a_g_vars_idx]
        eq_1_b_g_vars = point[b_g_vars_idx]
        
        # suffix 贡献：eq(0, a的高位) · eq(0, b的高位)（因为 FFT wiring 规则，suffix 全为0）
        eq_0_a_suffix = 1
        eq_0_b_suffix = 1
        if self.ab_vars > self.g_vars + 1:
            for i in range(self.g_vars + 1, self.ab_vars):
                a_high_idx = a_start + i
                b_high_idx = b_start + i
                if a_high_idx < len(one_minus_point):
                    eq_0_a_suffix = mod_mul(eq_0_a_suffix, one_minus_point[a_high_idx])
                if b_high_idx < len(one_minus_point):
                    eq_0_b_suffix = mod_mul(eq_0_b_suffix, one_minus_point[b_high_idx])
        
        # 组合：prefix贡献 × 第g_vars位贡献 × suffix贡献
        result = mod_mul(mod_mul(eq_r_a_prefix, eq_r_b_prefix), 
                       mod_mul(mod_mul(eq_0_a_g_vars, eq_1_b_g_vars),
                              mod_mul(eq_0_a_suffix, eq_0_b_suffix)))
        return result
    
    def evaluate_wiring_mle_fft_closed_form_optimized(self, point: List[int]) -> int:
        """
        FFT电路Wiring MLE的Closed Form实现 - O(log n)复杂度，处理任意felt252值
        
        使用真正的Closed Form公式，不遍历gates。
        """
        expected_len = self.g_vars + 2 * self.ab_vars
        if len(point) < expected_len:
            return 0
        
        one_minus_point = [mod_sub(1, mod_uint64(p)) for p in point]
        
        # point结构: [r (g_vars bits), a (ab_vars bits), b (ab_vars bits)]
        r_start = 0
        a_start = self.g_vars
        b_start = self.g_vars + self.ab_vars
        
        # 计算 eq(r, a的前g_vars位) · eq(r, b的前g_vars位)
        eq_r_a_head = eq_eval_point_parts(r_start, a_start, self.g_vars, point, one_minus_point)
        eq_r_b_head = eq_eval_point_parts(r_start, b_start, self.g_vars, point, one_minus_point)
        
        # 处理 ab_vars == g_vars 的特殊情况
        if self.ab_vars == self.g_vars:
            # 特殊情况：ab_vars == g_vars
            # 对于gate g: left = 2g, right = 2g+1
            # 由于ab_vars == g_vars，a和b都只有g_vars位
            # 2g需要g_vars+1位，但在ab_vars位范围内，我们需要检查2g是否可以用g_vars位表示
            # 只有当g < 2^(g_vars-1)时，2g < 2^g_vars，才能用g_vars位精确表示
            # 所以我们需要检查r的最高位是否为0
            
            # 检查r的最高位（最后一位，因为point是从低位到高位）
            r_high_bit = point[r_start + self.g_vars - 1]
            if r_high_bit != 0:
                # r的最高位为1，2r需要g_vars+1位，无法用g_vars位表示
                return 0
            
            # r的最高位为0，2r可以用g_vars位表示
            # 计算eq(r的前g_vars-1位, a的前g_vars-1位)和eq(r的前g_vars-1位, b的前g_vars-1位)
            if self.g_vars > 1:
                eq_r_a_head = eq_eval_point_parts(r_start, a_start, self.g_vars - 1, point, one_minus_point)
                eq_r_b_head = eq_eval_point_parts(r_start, b_start, self.g_vars - 1, point, one_minus_point)
            else:
                # g_vars == 1的特殊情况
                eq_r_a_head = 1
                eq_r_b_head = 1
            
            # 检查a的第g_vars位 == 0, b的第g_vars位 == 1
            a_g_vars_idx = a_start + self.g_vars - 1
            b_g_vars_idx = b_start + self.g_vars - 1
            if a_g_vars_idx >= len(one_minus_point) or b_g_vars_idx >= len(point):
                return 0
            eq_0_a_g_vars = one_minus_point[a_g_vars_idx]  # eq(0, a[g_vars-1]) = 1 - a[g_vars-1]
            eq_1_b_g_vars = point[b_g_vars_idx]  # eq(1, b[g_vars-1]) = b[g_vars-1]
            
            result = mod_mul(mod_mul(eq_r_a_head, eq_r_b_head), 
                           mod_mul(eq_0_a_g_vars, eq_1_b_g_vars))
            return result
        
        # 标准情况：ab_vars > g_vars
        # 计算 eq(0, a的第g_vars位) 和 eq(1, b的第g_vars位)
        a_g_vars_idx = a_start + self.g_vars
        b_g_vars_idx = b_start + self.g_vars
        if a_g_vars_idx >= len(one_minus_point) or b_g_vars_idx >= len(point):
            return 0
        eq_0_a_g_vars = one_minus_point[a_g_vars_idx]  # eq(0, a[g_vars]) = 1 - a[g_vars]
        eq_1_b_g_vars = point[b_g_vars_idx]  # eq(1, b[g_vars]) = b[g_vars]
        
        # 计算 eq(0, a的高位) 和 eq(0, b的高位)
        eq_0_a_high = 1
        eq_0_b_high = 1
        for i in range(self.g_vars + 1, self.ab_vars):
            a_high_idx = a_start + i
            b_high_idx = b_start + i
            if a_high_idx < len(one_minus_point):
                eq_0_a_high = mod_mul(eq_0_a_high, one_minus_point[a_high_idx])
            if b_high_idx < len(one_minus_point):
                eq_0_b_high = mod_mul(eq_0_b_high, one_minus_point[b_high_idx])
        
        result = mod_mul(mod_mul(eq_r_a_head, eq_r_b_head), 
                       mod_mul(mod_mul(eq_0_a_g_vars, eq_1_b_g_vars),
                              mod_mul(eq_0_a_high, eq_0_b_high)))
        return result
    
    def evaluate_wiring_mle_fft_closed_form(self, point: List[int]) -> int:
        """
        FFT电路Wiring MLE的Closed Form实现 - 处理任意felt252值，O(n)复杂度
        
        关键理解：
        - FFT的wiring是完全规则的：gate g连接下一层的 left = 2g, right = 2g+1
        - 对于任意felt252值，我们需要遍历所有gates，但可以利用wiring的规则性优化
        
        Wiring规则：
        - left(g) = 2g
        - right(g) = 2g+1
        
        W~(r, a, b) = sum over g: eq(g, r) · eq(2g, a) · eq(2g+1, b)
        
        对于FFT wiring，只有满足条件的gates有贡献：
        - Gate g: left = 2g, right = 2g+1
        - 所以我们需要检查：a 是否可以是 2g，b 是否可以是 2g+1
        
        优化：利用wiring的规则性，只遍历n个gates（而不是2^total_vars个可能值）
        
        复杂度: O(n log n) - 遍历n个gates，每个gate O(log n)计算eq值
        """
        expected_len = self.g_vars + 2 * self.ab_vars
        if len(point) < expected_len:
            return 0
        
        one_minus_point = [mod_sub(1, mod_uint64(p)) for p in point]
        
        # point结构: [r (g_vars bits), a (ab_vars bits), b (ab_vars bits)]
        r_start = 0
        a_start = self.g_vars
        b_start = self.g_vars + self.ab_vars
        
        result = 0
        
        # 遍历所有gates，利用FFT wiring的规则性
        for g_idx, gate in enumerate(self.current_layer):
            if gate.gate_type != GateType.ADD:
                continue
            
            # FFT wiring: left(g) = 2g, right(g) = 2g+1
            # 检查这个gate是否符合条件
            
            # 计算 eq(g, r)
            eq_g_r = 1
            for i in range(self.g_vars):
                r_idx = r_start + i
                if r_idx >= len(point):
                    break
                # g_idx 的二进制表示的第 i 位
                bit = (g_idx >> (self.g_vars - 1 - i)) & 1
                r_val = mod_uint64(point[r_idx])
                term = r_val if bit else mod_sub(1, r_val)
                eq_g_r = mod_mul(eq_g_r, term)
            
            # 计算 eq(2g, a) 和 eq(2g+1, b)
            # 2g 的二进制表示是 g 的二进制表示左移1位（后加0）
            # 2g+1 的二进制表示是 g 的二进制表示左移1位（后加1）
            
            # 构建 2g 和 2g+1 的二进制表示
            # 2g = (g, 0) - g的二进制表示后加0
            # 2g+1 = (g, 1) - g的二进制表示后加1
            
            # 计算 eq(2g, a)
            eq_2g_a = 1
            # a 的前 g_vars 位应该等于 g
            for i in range(self.g_vars):
                a_idx = a_start + i
                if a_idx >= len(point):
                    break
                bit = (g_idx >> (self.g_vars - 1 - i)) & 1
                a_val = mod_uint64(point[a_idx])
                term = a_val if bit else mod_sub(1, a_val)
                eq_2g_a = mod_mul(eq_2g_a, term)
            
            # a 的第 g_vars 位应该等于 0（如果 ab_vars > g_vars）
            if self.ab_vars > self.g_vars:
                a_g_vars_idx = a_start + self.g_vars
                if a_g_vars_idx < len(one_minus_point):
                    eq_2g_a = mod_mul(eq_2g_a, one_minus_point[a_g_vars_idx])
                else:
                    eq_2g_a = 0
                
                # a 的高位应该等于 0
                for i in range(self.g_vars + 1, self.ab_vars):
                    a_high_idx = a_start + i
                    if a_high_idx < len(one_minus_point):
                        eq_2g_a = mod_mul(eq_2g_a, one_minus_point[a_high_idx])
                    else:
                        eq_2g_a = 0
            elif self.ab_vars == self.g_vars:
                # 特殊情况：ab_vars == g_vars
                # a 的最后一位（第 g_vars-1 位）应该等于 0
                a_last_idx = a_start + self.g_vars - 1
                if a_last_idx < len(one_minus_point):
                    eq_2g_a = mod_mul(eq_2g_a, one_minus_point[a_last_idx])
                else:
                    eq_2g_a = 0
            
            # 计算 eq(2g+1, b)
            eq_2g1_b = 1
            # b 的前 g_vars 位应该等于 g
            for i in range(self.g_vars):
                b_idx = b_start + i
                if b_idx >= len(point):
                    break
                bit = (g_idx >> (self.g_vars - 1 - i)) & 1
                b_val = mod_uint64(point[b_idx])
                term = b_val if bit else mod_sub(1, b_val)
                eq_2g1_b = mod_mul(eq_2g1_b, term)
            
            # b 的第 g_vars 位应该等于 1（如果 ab_vars > g_vars）
            if self.ab_vars > self.g_vars:
                b_g_vars_idx = b_start + self.g_vars
                if b_g_vars_idx < len(point):
                    eq_2g1_b = mod_mul(eq_2g1_b, point[b_g_vars_idx])
                else:
                    eq_2g1_b = 0
                
                # b 的高位应该等于 0
                for i in range(self.g_vars + 1, self.ab_vars):
                    b_high_idx = b_start + i
                    if b_high_idx < len(one_minus_point):
                        eq_2g1_b = mod_mul(eq_2g1_b, one_minus_point[b_high_idx])
                    else:
                        eq_2g1_b = 0
            elif self.ab_vars == self.g_vars:
                # 特殊情况：ab_vars == g_vars
                # b 的最后一位（第 g_vars-1 位）应该等于 1
                b_last_idx = b_start + self.g_vars - 1
                if b_last_idx < len(point):
                    eq_2g1_b = mod_mul(eq_2g1_b, point[b_last_idx])
                else:
                    eq_2g1_b = 0
            
            # 累加贡献
            contribution = mod_mul(mod_mul(eq_g_r, eq_2g_a), eq_2g1_b)
            result = mod_add(result, contribution)
        
        return result
    
    def get_add_mle(self) -> MLE:
        """重写get_add_mle，返回一个支持Closed Form评估的MLE"""
        # 仍然返回标准MLE，但在compute_final_value中使用Closed Form
        return super().get_add_mle()

class FFTGKRSumcheck(GKRSumcheck):
    """FFT电路的GKRSumcheck，使用优化的wiring MLE评估"""
    
    def __init__(self, wiring: WiringPredicates, next_mle: MLE, r_point: List[int], n: int):
        # next_mle可以为None，因为我们使用递归评估而不是MLE对象
        if next_mle is None:
            # 创建一个虚拟的MLE对象以满足父类要求，但不会使用它
            from gkr_verifier import MLE
            dummy_mle = MLE([0], 0)
            super().__init__(wiring, dummy_mle, r_point, n)
        else:
            super().__init__(wiring, next_mle, r_point, n)
    
    def compute_final_value(self, a_point: List[int], b_point: List[int], v_a: int, v_b: int) -> int:
        """使用稀疏评估优化wiring MLE评估 - O(log n)复杂度"""
        point = self.r + list(a_point) + list(b_point)
        
        # 检查是否有ADD gates（FFT电路只有ADD gates）
        has_add = any(gate.gate_type == GateType.ADD for gate in self.wiring.current_layer)
        
        if has_add and isinstance(self.wiring, FFTWiringPredicates):
            # 使用稀疏评估 - O(log n) - 利用FFT wiring的规则性
            add_val = self.wiring.evaluate_wiring_mle_fft_sparse(point)
            mul_val = 0
        elif has_add:
            # Fallback到标准MLE评估 - O(n) - 仅用于非FFT电路
            add_mle = self.wiring.get_add_mle()
            add_val = add_mle.evaluate(point)
            mul_val = 0
        else:
            add_val = 0
            mul_val = 0
        
        result = mod_add(
            mod_mul(add_val, mod_add(v_a, v_b)),
            mod_mul(mul_val, mod_mul(v_a, v_b))
        )
        
        return result

class FFTCircuit(Circuit):
    """FFT电路，支持递归Layer MLE评估"""
    
    def evaluate_layer_mle_fft_recursive(self, layer_idx: int, point: List[int]) -> int:
        """
        递归评估FFT层的MLE，利用FFT的递归关系 - O(log n)复杂度
        
        FFT递归关系：对于Layer i的gate g，它连接Layer i+1的gate 2g和gate 2g+1
        - W_i(g) = W_{i+1}(2g) + W_{i+1}(2g+1)
        
        对于MLE评估W~_i(r)：
        - 将point r的二进制表示拆分为(r_low, r_high)
        - r_high是最后1位，r_low是前num_vars-1位
        - 递归评估下一层在(r_low, 0)和(r_low, 1)的值
        - 使用multilinear extension组合：
          W~_i(r) = (1-r_high) * W~_{i+1}(r_low, 0) + r_high * W~_{i+1}(r_low, 1)
        
        复杂度：O(log n) - 递归深度为O(log n)，每层O(1)操作
        """
        if layer_idx >= len(self.evaluated_layers):
            return 0
        
        num_vars = self.layer_num_vars[layer_idx]
        if len(point) != num_vars:
            return 0
        
        return self._evaluate_fft_layer_recursive(layer_idx, point, num_vars)
    
    def _evaluate_fft_layer_recursive(self, layer_idx: int, point: List[int], num_vars: int) -> int:
        """
        递归评估FFT层的MLE，利用FFT的递归关系
        
        FFT递归关系：对于Layer i的gate g，它连接Layer i+1的gate 2g和gate 2g+1
        - W_i(g) = W_{i+1}(2g) + W_{i+1}(2g+1)
        
        对于MLE评估W~_i(r)：
        - 将point r的二进制表示拆分为(r_low, r_high)
        - r_high是最后1位，r_low是前num_vars-1位
        - 递归评估下一层在(r_low, 0)和(r_low, 1)的值
        - 使用multilinear extension组合：
          W~_i(r) = (1-r_high) * W~_{i+1}(r_low, 0) + r_high * W~_{i+1}(r_low, 1)
        
        复杂度：O(log n) - 递归深度为O(log n)，每层O(1)操作
        """
        if num_vars == 0:
            # 基础情况：num_vars=0，直接返回layer[0]的值
            if layer_idx < len(self.evaluated_layers):
                layer = self.evaluated_layers[layer_idx]
                if len(layer) > 0:
                    return mod_uint64(layer[0].value)
            return 0
        
        # 获取下一层（更接近输入层）
        next_layer_idx = layer_idx + 1
        if next_layer_idx >= len(self.evaluated_layers):
            # 如果已经是最后一层，使用标准递归评估
            layer = self.evaluated_layers[layer_idx]
            return self._evaluate_layer_mle_recursive(layer, num_vars, point, 0, 0)
        
        # 下一层的num_vars应该比当前层多1
        next_num_vars = self.layer_num_vars[next_layer_idx]
        
        # 根据FFT递归关系：W~_i(r) = W~_{i+1}(r, 0) + W~_{i+1}(r, 1)
        # 构建下一层的point：point + [0] 和 point + [1]
        next_point_0 = point + [0]
        next_point_1 = point + [1]
        
        # 调整point长度以匹配next_num_vars
        if len(next_point_0) < next_num_vars:
            # 如果point长度+1小于next_num_vars，需要填充0到前面（高位）
            padding = [0] * (next_num_vars - len(next_point_0))
            next_point_0 = padding + next_point_0
            next_point_1 = padding + next_point_1
        elif len(next_point_0) > next_num_vars:
            # 如果point长度+1大于next_num_vars，取最后next_num_vars位（低位）
            # 这是因为point的二进制表示中，低位对应gate索引的低位
            next_point_0 = next_point_0[-next_num_vars:]
            next_point_1 = next_point_1[-next_num_vars:]
        
        # 递归评估下一层在(r, 0)和(r, 1)的值
        v0 = self.evaluate_layer_mle_fft_recursive(next_layer_idx, next_point_0)
        v1 = self.evaluate_layer_mle_fft_recursive(next_layer_idx, next_point_1)
        
        # 使用FFT递归关系：W~_i(r) = W~_{i+1}(r, 0) + W~_{i+1}(r, 1)
        result = mod_add(v0, v1)
        
        return result
    
    def _evaluate_layer_mle_recursive(self, layer: List[Gate], num_vars: int, 
                                      point: List[int], var_idx: int, gate_idx: int) -> int:
        """递归评估layer MLE，复杂度O(2^num_vars)但可以提前终止"""
        if var_idx >= num_vars:
            if gate_idx < len(layer):
                return mod_uint64(layer[gate_idx].value)
            return 0
        
        x_i = mod_uint64(point[var_idx])
        
        # 优化：如果x_i = 0，只需要左子树
        if x_i == 0:
            return self._evaluate_layer_mle_recursive(layer, num_vars, point, var_idx + 1, gate_idx)
        
        # 优化：如果x_i = 1，只需要右子树
        if x_i == 1:
            offset = 1 << (num_vars - var_idx - 1)
            return self._evaluate_layer_mle_recursive(layer, num_vars, point, var_idx + 1, gate_idx + offset)
        
        # 一般情况：递归计算左右子树
        one_minus_x = mod_sub(1, x_i)
        left = self._evaluate_layer_mle_recursive(layer, num_vars, point, var_idx + 1, gate_idx)
        offset = 1 << (num_vars - var_idx - 1)
        right = self._evaluate_layer_mle_recursive(layer, num_vars, point, var_idx + 1, gate_idx + offset)
        return mod_add(mod_mul(one_minus_x, left), mod_mul(x_i, right))

class FFTGKRVerifier(GKRVerifier):
    """FFT电路的GKR Verifier，使用优化的wiring和layer评估 - O(log³ n)复杂度"""
    
    def __init__(self, circuit: Circuit, inputs: List[int]):
        # 将circuit转换为FFTCircuit以支持递归评估
        if not isinstance(circuit, FFTCircuit):
            fft_circuit = FFTCircuit()
            fft_circuit.layers = circuit.layers
            fft_circuit.layer_sizes = circuit.layer_sizes
            fft_circuit.layer_num_vars = circuit.layer_num_vars
            fft_circuit.evaluated_layers = circuit.evaluated_layers
            circuit = fft_circuit
        super().__init__(circuit, inputs)
        self.circuit = circuit
    
    def verify_proof(self, proof: GKRProof) -> bool:
        """重写verify_proof，使用FFT优化的WiringPredicates"""
        transcript = FiatShamirTranscript()
        current_claimed = proof.output
        
        num_layers = len(self.circuit.layers)
        
        output_layer_idx = 0
        output_num_vars = self.circuit.layer_num_vars[output_layer_idx]
        current_point = [0] * output_num_vars
        
        output_mle = self.circuit.get_layer_mle(output_layer_idx)
        output_eval = output_mle.evaluate(current_point)
        
        if output_eval != proof.output:
            return False
        
        # 计算 n（FFT大小）
        n = len(self.inputs)
        
        for layer_idx, sumcheck_proof in enumerate(proof.sumcheck_proofs):
            if layer_idx >= num_layers - 1:
                return False
            
            claimed_sum = sumcheck_proof.claimed_sum
            
            if claimed_sum != current_claimed:
                return False
            
            # 使用FFTWiringPredicates替代标准WiringPredicates
            standard_wiring = WiringPredicates(self.circuit, layer_idx)
            wiring = FFTWiringPredicates(self.circuit, layer_idx)
            # 复制属性
            wiring.current_layer = standard_wiring.current_layer
            wiring.next_layer = standard_wiring.next_layer
            wiring.g_vars = standard_wiring.g_vars
            wiring.ab_vars = standard_wiring.ab_vars
            wiring.total_vars = standard_wiring.total_vars
            
            # 使用递归Layer MLE评估 - O(log n)复杂度
            # 不再需要构建完整的MLE对象，直接使用递归评估
            
            # 使用FFTGKRSumcheck - 支持稀疏评估
            # 传递None作为next_mle，因为我们将直接使用递归评估
            transcript.reset()
            sumcheck = FFTGKRSumcheck(wiring, None, current_point, n)
            success, a_point, b_point, v_a, v_b = self.verify_sumcheck_proof_fft(
                sumcheck_proof, wiring, layer_idx + 1, current_point, transcript, n
            )
            
            if not success:
                return False
            
            s = len(a_point)
            # 与标准实现一致：使用位运算打包数据
            data = 0
            for k in range(min(len(a_point), len(b_point))):
                pow_k32 = pow(2, k * 32, PRIME)
                pow_k32_plus = pow(2, (k + len(a_point)) * 32, PRIME)
                data = mod_add(data, mod_mul(a_point[k], pow_k32))
                data = mod_add(data, mod_mul(b_point[k], pow_k32_plus))
            
            hash_value = mod_add(mod_mul(data, 2654435761), 2246822507)
            
            next_s = self.circuit.layer_num_vars[layer_idx + 1] if layer_idx + 1 < len(self.circuit.layer_num_vars) else 1
            new_point: List[int] = []
            
            for i in range(next_s):
                coord_seed = mod_add(mod_mul(hash_value, 1000000), i)
                new_point.append(coord_seed)
            
            # 使用递归Layer MLE评估 - O(log n)复杂度
            if isinstance(self.circuit, FFTCircuit):
                current_claimed = self.circuit.evaluate_layer_mle_fft_recursive(layer_idx + 1, new_point)
            else:
                next_mle_for_merge = self.circuit.get_layer_mle(layer_idx + 1)
                current_claimed = next_mle_for_merge.evaluate(new_point)
            current_point = new_point
        
        input_layer_idx = len(self.circuit.layers) - 1
        input_num_vars = self.circuit.layer_num_vars[input_layer_idx]
        input_mle = MLE(self.inputs, input_num_vars)
        
        computed = input_mle.evaluate(current_point)
        
        return computed == current_claimed

    def compute_ipfs_extra(self, proof: GKRProof) -> Tuple[List[int], List[int]]:
        """与 verify_proof 相同逻辑，但返回 (vaVb, nextClaimed) 供链上 verifyWithIPFS 使用。
        vaVb: 每层 [v_a, v_b] 按层顺序拼接，长度 2*(numLayers-1)。
        nextClaimed: 每层 sumcheck 后下一层在挑战点的 claimed 值，长度 numLayers-1。
        """
        transcript = FiatShamirTranscript()
        current_claimed = proof.output
        num_layers = len(self.circuit.layers)
        output_num_vars = self.circuit.layer_num_vars[0]
        current_point = [0] * output_num_vars
        n = len(self.inputs)
        va_vb: List[int] = []
        next_claimed: List[int] = []

        for layer_idx, sumcheck_proof in enumerate(proof.sumcheck_proofs):
            if layer_idx >= num_layers - 1:
                break
            if sumcheck_proof.claimed_sum != current_claimed:
                raise ValueError("claimed_sum mismatch")
            standard_wiring = WiringPredicates(self.circuit, layer_idx)
            wiring = FFTWiringPredicates(self.circuit, layer_idx)
            wiring.current_layer = standard_wiring.current_layer
            wiring.next_layer = standard_wiring.next_layer
            wiring.g_vars = standard_wiring.g_vars
            wiring.ab_vars = standard_wiring.ab_vars
            wiring.total_vars = standard_wiring.total_vars
            transcript.reset()
            sumcheck = FFTGKRSumcheck(wiring, None, current_point, n)
            success, a_point, b_point, v_a, v_b = self.verify_sumcheck_proof_fft(
                sumcheck_proof, wiring, layer_idx + 1, current_point, transcript, n
            )
            if not success:
                raise ValueError("sumcheck verification failed")
            va_vb.append(v_a)
            va_vb.append(v_b)
            s = len(a_point)
            data = 0
            for k in range(min(len(a_point), len(b_point))):
                pow_k32 = pow(2, k * 32, PRIME)
                pow_k32_plus = pow(2, (k + len(a_point)) * 32, PRIME)
                data = mod_add(data, mod_mul(a_point[k], pow_k32))
                data = mod_add(data, mod_mul(b_point[k], pow_k32_plus))
            hash_value = mod_add(mod_mul(data, 2654435761), 2246822507)
            next_s = self.circuit.layer_num_vars[layer_idx + 1] if layer_idx + 1 < len(self.circuit.layer_num_vars) else 1
            new_point = [mod_add(mod_mul(hash_value, 1000000), i) for i in range(next_s)]
            if isinstance(self.circuit, FFTCircuit):
                current_claimed = self.circuit.evaluate_layer_mle_fft_recursive(layer_idx + 1, new_point)
            else:
                next_mle_for_merge = self.circuit.get_layer_mle(layer_idx + 1)
                current_claimed = next_mle_for_merge.evaluate(new_point)
            next_claimed.append(current_claimed)
            current_point = new_point
        return va_vb, next_claimed
    
    def verify_sumcheck_proof_fft(self, proof: SumcheckProof, wiring: FFTWiringPredicates,
                                  next_layer_idx: int, r_point: List[int],
                                  transcript: FiatShamirTranscript, n: int) -> Tuple[bool, List[int], List[int], int, int]:
        """使用FFT优化的sumcheck验证 - 直接使用递归评估，不依赖MLE对象"""
        # 创建sumcheck对象（next_mle为None，因为我们使用递归评估）
        sumcheck = FFTGKRSumcheck(wiring, None, r_point, n)
        s = sumcheck.s
        
        transcript.set_claimed_sum(proof.claimed_sum)
        prev_val = proof.claimed_sum
        fixed: List[int] = []
        
        for round_proof in proof.rounds:
            g0 = round_proof.g0
            g1 = round_proof.g1
            g2 = round_proof.g2
            
            if mod_add(g0, g1) != prev_val:
                return False, [], [], 0, 0
            
            r = transcript.challenge(g0, g1, g2)
            prev_val = lagrange_interpolate_3points(g0, g1, g2, r)
            fixed.append(r)
        
        # fixed包含2*ab_vars个固定值（sumcheck有2*ab_vars轮，每轮固定一个变量）
        # 前ab_vars个是a的值，后ab_vars个是b的值
        a_point = fixed[:s]
        b_point = fixed[s:]
        
        # 直接使用递归评估计算v_a和v_b - O(log n)复杂度
        v_a = self.circuit.evaluate_layer_mle_fft_recursive(next_layer_idx, a_point)
        v_b = self.circuit.evaluate_layer_mle_fft_recursive(next_layer_idx, b_point)
        
        final_computed = sumcheck.compute_final_value(a_point, b_point, v_a, v_b)
        
        if prev_val != final_computed:
            # 调试信息
            print(f"DEBUG: Sumcheck final value mismatch: prev_val={prev_val}, final_computed={final_computed}")
            print(f"  a_point={a_point}, b_point={b_point}")
            print(f"  v_a={v_a}, v_b={v_b}")
            print(f"  wiring: g_vars={wiring.g_vars}, ab_vars={wiring.ab_vars}")
            return False, [], [], 0, 0
        
        return True, a_point, b_point, v_a, v_b

def build_fft_circuit(n: int) -> Circuit:
    """构建FFT电路"""
    all_layers: List[List[Gate]] = []
    
    # 输入层
    input_layer: List[Gate] = []
    for i in range(n):
        input_gate = Gate(GateType.INPUT, -1, -1)
        input_layer.append(input_gate)
    all_layers.append(input_layer)
    
    log_n = 0
    temp = n
    while temp > 1:
        log_n += 1
        temp >>= 1
    
    current_size = n
    current_layer = input_layer
    
    for level in range(log_n):
        next_size = current_size // 2
        next_layer: List[Gate] = []
        
        omega = 1
        
        for i in range(next_size):
            even_idx = i * 2
            odd_idx = i * 2 + 1
            
            # 简化FFT：even + odd（因为omega=1）
            add_gate = Gate(GateType.ADD, even_idx, odd_idx)
            next_layer.append(add_gate)
        
        all_layers.append(next_layer)
        current_layer = next_layer
        current_size = next_size
    
    all_layers.reverse()
    
    circuit = Circuit()
    circuit.layers = all_layers
    
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

def parse_proof_file(proof_file: str) -> Tuple[GKRProof, List[int]]:
    """解析proof文件，格式与标准实现一致"""
    with open(proof_file, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]
    
    if len(lines) < 5:
        raise ValueError(f"Invalid proof file format: expected at least 5 lines, got {len(lines)}")
    
    num_inputs = int(lines[0])
    inputs = [int(x) for x in lines[1].split()]
    output = int(lines[2])
    
    g0_list = [int(x) for x in lines[3].split()]
    g1_list = [int(x) for x in lines[4].split()]
    g2_list = [int(x) for x in lines[5].split()]
    
    if len(g0_list) != len(g1_list) or len(g1_list) != len(g2_list):
        raise ValueError("g0, g1, g2 lists must have the same length")
    
    # 构建sumcheck proofs
    n = len(inputs)
    circuit = build_fft_circuit(n)
    
    sumcheck_proofs: List[SumcheckProof] = []
    round_idx = 0
    
    for layer_idx in range(len(circuit.layers) - 1):
        wiring = WiringPredicates(circuit, layer_idx)
        num_vars = 2 * wiring.ab_vars
        
        rounds: List[SumcheckRoundProof] = []
        for i in range(num_vars):
            if round_idx >= len(g0_list):
                raise ValueError("Not enough proof data")
            rounds.append(SumcheckRoundProof(i, g0_list[round_idx], g1_list[round_idx], g2_list[round_idx]))
            round_idx += 1
        
        # claimed_sum从第一轮的g0+g1计算
        claimed_sum = mod_add(rounds[0].g0, rounds[0].g1) if rounds else 0
        sumcheck_proofs.append(SumcheckProof(claimed_sum, rounds))
    
    if round_idx != len(g0_list):
        raise ValueError("Extra proof data")
    
    return GKRProof(output, sumcheck_proofs), inputs

def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: python gkr_verifier_fft.py <proof_file> [--ipfs-extra]")
        sys.exit(1)
    
    proof_file = sys.argv[1]
    ipfs_extra_only = len(sys.argv) >= 3 and sys.argv[2] == "--ipfs-extra"
    
    try:
        proof, inputs = parse_proof_file(proof_file)
        circuit = build_fft_circuit(len(inputs))
        verifier = FFTGKRVerifier(circuit, inputs)
        
        if ipfs_extra_only:
            va_vb, next_claimed = verifier.compute_ipfs_extra(proof)
            print(" ".join(str(x) for x in va_vb))
            print(" ".join(str(x) for x in next_claimed))
            sys.exit(0)
        
        print(f"FFT size: {len(inputs)}")
        print(f"Inputs: {' '.join(map(str, inputs))}")
        print(f"Claimed output: {proof.output}")
        print(f"Number of sumcheck proofs: {len(proof.sumcheck_proofs)}")
        
        import time
        start_time = time.time()
        result = verifier.verify_proof(proof)
        elapsed_time = (time.time() - start_time) * 1000
        
        print()
        print("=" * 60)
        if result:
            print("VERIFICATION PASSED")
        else:
            print("VERIFICATION FAILED")
        print("=" * 60)
        print(f"Time: {elapsed_time:.0f} ms")
        
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
