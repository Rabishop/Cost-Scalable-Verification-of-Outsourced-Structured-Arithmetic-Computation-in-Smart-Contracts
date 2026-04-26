# FFT On-Chain Verification Benchmark

## What This Repository Evaluates

This project compares two ways to handle an FFT-style workload on-chain:

- **Direct execution**: execute the FFT circuit logic on-chain.
- **GKR verification**: compute off-chain, then verify a proof on-chain.

We report results on both:

- **EVM** (Solidity; cost shown in ETH using a fixed gas price),
- **Starknet** (Cairo; fee shown in ETH converted from STRK).

The goal is to show the scaling trend as input size `n` grows.

## Main Result Table

| n | EVM Direct (ETH) | EVM Verify (ETH) | Starknet Direct (ETH) | Starknet Verify (ETH) |
|---:|---:|---:|---:|---:|
| 2 | 7.79e-6 | 1.15e-5 | 4.46e-8 | 5.30e-8 |
| 4 | 8.44e-6 | 1.72e-5 | 4.51e-8 | 6.17e-8 |
| 8 | 9.71e-6 | 2.56e-5 | 4.84e-8 | 6.98e-8 |
| 16 | 1.22e-5 | 3.64e-5 | 5.49e-8 | 8.17e-8 |
| 64 | 2.72e-5 | 6.55e-5 | 1.27e-7 | 1.60e-7 |
| 128 | 4.72e-5 | 8.41e-5 | 2.17e-7 | 1.86e-7 |
| 256 | 8.71e-5 | 1.05e-4 | 4.05e-7 | 2.18e-7 |
| 512 | 1.68e-4 | 1.28e-4 | 7.76e-7 | 2.55e-7 |
| 1024 | 3.30e-4 | 1.53e-4 | 1.52e-6 | 2.91e-7 |
| 2048 | 7.26e-4 | 1.82e-4 | 3.00e-6 | 3.63e-7 |
| 4096 | 1.52e-3 | 2.41e-4 | 5.96e-6 | 5.08e-7 |

## Key Takeaways

- **EVM**: direct execution is cheaper at small `n`, while verification becomes cheaper from medium/large `n` onward.
- **Starknet**: a similar crossover happens earlier, and the verification curve grows much more slowly.
- Overall, the data supports the expected pattern: **verification scales better than direct execution** as `n` increases.

## Notes on Conventions

- EVM ETH values are converted from gas using a fixed gas-price convention in the project.
- Starknet ETH values are converted from STRK (`overall_fee / 1e18`) using the project’s stated exchange-rate assumption.
- Some large-`n` rows are extrapolated according to the repository’s documented convention.
