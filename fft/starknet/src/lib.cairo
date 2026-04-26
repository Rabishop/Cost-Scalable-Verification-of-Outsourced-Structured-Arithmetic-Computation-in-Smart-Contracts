// FFT GKR 证明验证合约 - Starknet 版
// 与 Solidity FFTVerifier.verifyWithIPFS 逻辑一致，域为 Starknet PRIME (felt252)

use core::felt252_div;

/// 域除法：lhs/rhs，rhs 非零（调用方保证）
fn div_felt(lhs: felt252, rhs: felt252) -> felt252 {
    let rhs_nonzero: core::zeroable::NonZero = rhs.try_into().unwrap();
    felt252_div(lhs, rhs_nonzero)
}

/// 2^exp mod P，exp 为 u32
fn pow2_u32(exp: u32) -> felt252 {
    let mut base = 2_felt252;
    let mut result = 1_felt252;
    let mut e = exp;
    loop {
        if e == 0 {
            break;
        }
        if e % 2 == 1 {
            result = result * base;
        }
        base = base * base;
        e = e / 2;
    };
    result
}

/// 计算 2^i，i 为 u32
fn two_pow_i(i: u32) -> u32 {
    let mut r = 1_u32;
    let mut k = 0_u32;
    loop {
        if k >= i {
            break;
        }
        r = r * 2;
        k = k + 1;
    };
    r
}

/// Fiat-Shamir 挑战（与 Python/Solidity 一致）
fn challenge(state: felt252, _first: bool, g0: felt252, g1: felt252) -> felt252 {
    let data = state + g0 * 1000000_felt252 + g1;
    data * 2654435761_felt252 + 2246822507_felt252
}

/// 三点 Lagrange 插值 L(x): L(0)=g0, L(1)=g1, L(2)=g2
fn lagrange3(g0: felt252, g1: felt252, g2: felt252, x: felt252) -> felt252 {
    let one = 1_felt252;
    let two = 2_felt252;
    let xm1 = x - one;
    let xm2 = x - two;
    let inv_neg1 = div_felt(one, (-1_felt252));
    let inv_neg2 = div_felt(one, (-2_felt252));
    let inv2 = div_felt(one, two);
    let l0 = xm1 * xm2 * inv_neg1 * inv_neg2;
    let l1 = x * xm2 * div_felt(one, (-1_felt252));
    let l2 = x * xm1 * inv2;
    g0 * l0 + g1 * l1 + g2 * l2
}

/// log2(x) 位数，x>0；0 返回 0
fn log2_u32(mut x: u32) -> u32 {
    let mut r = 0_u32;
    loop {
        if x == 0 {
            break;
        }
        x = x / 2;
        r = r + 1;
    };
    r
}

/// 稀疏 FFT wiring MLE: W~(r,a,b)
fn wiring_mle_sparse(
    point: Span<felt252>,
    g_vars: u32,
    ab_vars: u32,
) -> felt252 {
    let mut prefix_sum = 1_felt252;
    let one = 1_felt252;
    let mut i: u32 = 0;
    loop {
        if i >= g_vars {
            break;
        }
        let rv = *point.at(i);
        let av = *point.at(g_vars + i);
        let bv = *point.at(g_vars + ab_vars + i);
        let term1 = rv * av * bv;
        let term0 = (-rv + one) * (-av + one) * (-bv + one);
        prefix_sum = prefix_sum * (term1 + term0);
        i = i + 1;
    };

    if ab_vars <= g_vars {
        if g_vars > 0 {
            let last_r = *point.at(g_vars - 1);
            if last_r != 0 {
                return 0_felt252;
            }
        }
        let eq0a = if g_vars > 0 {
            -(*point.at(g_vars + g_vars - 1)) + one
        } else {
            one
        };
        let eq1b = if g_vars > 0 {
            *point.at(g_vars + ab_vars + g_vars - 1)
        } else {
            0_felt252
        };
        return prefix_sum * eq0a * eq1b;
    }

    let eq0ag = -(*point.at(g_vars + g_vars)) + one;
    let eq1bg = *point.at(g_vars + ab_vars + g_vars);
    let mut suffix = eq0ag * eq1bg;
    let mut i = g_vars + 1;
    loop {
        if i >= ab_vars {
            break;
        }
        suffix = suffix * (-(*point.at(g_vars + i)) + one);
        suffix = suffix * (-(*point.at(g_vars + ab_vars + i)) + one);
        i = i + 1;
    };
    prefix_sum * suffix
}

// ========== 直接 FFT 合约（链上 O(n log n) 计算，与 Python 一致） ==========

#[starknet::interface]
trait IFftDirect<TContractState> {
    /// 执行与 Python build_fft_circuit 一致的 FFT：log(n) 层，每层 next[i] = prev[2i] + prev[2i+1]，输出为所有输入之和
    fn fft(ref self: TContractState, input: Array<felt252>) -> felt252;
}

#[starknet::contract]
mod FftDirect {
    #[storage]
    struct Storage {}

    #[abi(embed_v0)]
    impl FftDirectImpl of super::IFftDirect<ContractState> {
        fn fft(ref self: ContractState, input: Array<felt252>) -> felt252 {
            let n = input.len();
            if n == 0 {
                return 0_felt252;
            }
            let mut cur = ArrayTrait::new();
            let mut i: u32 = 0;
            loop {
                if i >= n {
                    break;
                }
                cur.append(*input.at(i));
                i = i + 1;
            };
            let mut size = n;
            while size > 1 {
                let half = size / 2;
                let mut next_cur = ArrayTrait::new();
                let mut i: u32 = 0;
                loop {
                    if i >= half {
                        break;
                    }
                    let idx_hi = i + half;
                    next_cur.append(*cur.at(i) + *cur.at(idx_hi));
                    i = i + 1;
                };
                cur = next_cur;
                size = half;
            };
            *cur.at(0)
        }
    }
}

// ========== GKR 验证合约 ==========

#[starknet::interface]
trait IFftVerifier<TContractState> {
    /// IPFS 优化验证：不传 input，只传 commitment 与 proof（含 vaVb、nextClaimed）
    fn verify_with_ipfs(
        ref self: TContractState,
        input_commitment: felt252,
        output: felt252,
        g0: Array<felt252>,
        g1: Array<felt252>,
        g2: Array<felt252>,
        round_counts: Array<felt252>,
        va_vb: Array<felt252>,
        next_claimed: Array<felt252>,
    ) -> bool;
}

#[starknet::contract]
mod FftVerifier {
    use super::{challenge, lagrange3, wiring_mle_sparse, pow2_u32, log2_u32, two_pow_i};

    #[storage]
    struct Storage {}

    #[abi(embed_v0)]
    impl FftVerifierImpl of super::IFftVerifier<ContractState> {
        fn verify_with_ipfs(
            ref self: ContractState,
            input_commitment: felt252,  // 保留用于 ABI，验证逻辑不校验 commitment
            output: felt252,
            g0: Array<felt252>,
            g1: Array<felt252>,
            g2: Array<felt252>,
            round_counts: Array<felt252>,
            va_vb: Array<felt252>,
            next_claimed: Array<felt252>,
        ) -> bool {
            let num_layers = round_counts.len() + 1;
            if va_vb.len() < 2 * (num_layers - 1) {
                return false;
            }
            if next_claimed.len() < num_layers - 1 {
                return false;
            }

            let mut layer_num_vars: Array<u32> = ArrayTrait::new();
            let mut i: u32 = 0;
            loop {
                if i >= num_layers {
                    break;
                }
                let size = two_pow_i(i);
                let lv = if size <= 1 {
                    1_u32
                } else {
                    log2_u32(size - 1)
                };
                layer_num_vars.append(lv);
                i = i + 1;
            };

            let mut global_idx: u32 = 0;
            let mut current_claimed = output;
            let mut current_point = ArrayTrait::new();
            let cp_len = *layer_num_vars.at(0);
            let mut j: u32 = 0;
            loop {
                if j >= cp_len {
                    break;
                }
                current_point.append(0_felt252);
                j = j + 1;
            };
            let mut va_vb_idx: u32 = 0;

            let mut layer_idx: u32 = 0;
            loop {
                if layer_idx >= num_layers - 1 {
                    break;
                }

                let rounds: u32 = (*round_counts.at(layer_idx)).try_into().unwrap();
                let g0_len: u32 = g0.len().try_into().unwrap();
                if global_idx + rounds > g0_len {
                    return false;
                }

                let prev_val = *g0.at(global_idx) + *g1.at(global_idx);
                if prev_val != current_claimed {
                    return false;
                }

                let mut first = true;
                let mut state = prev_val;
                let mut running_claim: felt252 = prev_val;
                let mut fixed = ArrayTrait::new();
                let mut r: u32 = 0;
                loop {
                    if r >= rounds {
                        break;
                    }
                    let g0r = *g0.at(global_idx + r);
                    let g1r = *g1.at(global_idx + r);
                    let g2r = *g2.at(global_idx + r);
                    if g0r + g1r != running_claim {
                        return false;
                    }
                    let r_val = challenge(state, first, g0r, g1r);
                    first = false;
                    state = r_val;
                    running_claim = lagrange3(g0r, g1r, g2r, r_val);
                    fixed.append(r_val);
                    r = r + 1;
                };
                global_idx = global_idx + rounds;

                let s = rounds / 2;
                let g_vars = *layer_num_vars.at(layer_idx);
                let ab_vars = s;

                let mut point = ArrayTrait::new();
                let mut idx: u32 = 0;
                loop {
                    if idx >= g_vars {
                        break;
                    }
                    point.append(*current_point.at(idx));
                    idx = idx + 1;
                };
                idx = 0;
                loop {
                    if idx >= ab_vars {
                        break;
                    }
                    point.append(*fixed.at(idx));
                    idx = idx + 1;
                };
                idx = 0;
                loop {
                    if idx >= ab_vars {
                        break;
                    }
                    point.append(*fixed.at(s + idx));
                    idx = idx + 1;
                };

                let add_val = wiring_mle_sparse(point.span(), g_vars, ab_vars);
                let va = *va_vb.at(va_vb_idx);
                let vb = *va_vb.at(va_vb_idx + 1);
                va_vb_idx = va_vb_idx + 2;
                let final_val = add_val * (va + vb);
                if running_claim != final_val {
                    return false;
                }

                let mut data = 0_felt252;
                let mut k: u32 = 0;
                loop {
                    if k >= s || k >= ab_vars {
                        break;
                    }
                    let pow_k = pow2_u32(k * 32);
                    let pow_sk = pow2_u32((s + k) * 32);
                    data = data + (*fixed.at(k)) * pow_k + (*fixed.at(s + k)) * pow_sk;
                    k = k + 1;
                };
                let hash_val = data * 2654435761_felt252 + 2246822507_felt252;

                let next_s = *layer_num_vars.at(layer_idx + 1);
                current_point = ArrayTrait::new();
                let mut i: u32 = 0;
                loop {
                    if i >= next_s {
                        break;
                    }
                    current_point.append(hash_val * 1000000_felt252 + i.try_into().unwrap());
                    i = i + 1;
                };
                current_claimed = *next_claimed.at(layer_idx);
                layer_idx = layer_idx + 1;
            };

            true
        }
    }
}
