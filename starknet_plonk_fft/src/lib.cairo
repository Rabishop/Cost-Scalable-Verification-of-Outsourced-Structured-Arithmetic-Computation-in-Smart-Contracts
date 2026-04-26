//! Plonk 类 **工作量占位**：公开仅 **1 个 felt**（`public_out`）；`proof_limbs` 更长、常数循环更大。

#[starknet::interface]
trait IPlonkFftVerify<TContractState> {
    fn verify_fft(ref self: TContractState, public_out: felt252, proof_limbs: Array<felt252>) -> felt252;
}

const PROOF_LIMBS: usize = 64;
const PLONK_MOCK_ITERS: u32 = 2100;

#[starknet::contract]
mod PlonkFftVerify {
    #[storage]
    struct Storage {}

    #[abi(embed_v0)]
    impl PlonkFftVerifyImpl of super::IPlonkFftVerify<ContractState> {
        fn verify_fft(ref self: ContractState, public_out: felt252, proof_limbs: Array<felt252>) -> felt252 {
            if proof_limbs.len() != super::PROOF_LIMBS {
                return 0_felt252;
            }
            if public_out == 0_felt252 {
                return 0_felt252;
            }
            let mut x = *proof_limbs.at(0) + public_out;
            let mut t: usize = 1;
            loop {
                if t >= super::PROOF_LIMBS {
                    break;
                }
                x = x + *proof_limbs.at(t);
                t = t + 1;
            };
            let mut j: u32 = 0;
            loop {
                if j >= super::PLONK_MOCK_ITERS {
                    break;
                }
                x = x * 5_felt252 + 11_felt252 + public_out;
                j = j + 1;
            };
            if x == 0_felt252 {
                return 0_felt252;
            }
            1_felt252
        }
    }
}
