# Work Completed (Code-Based Summary for the Paper)

This document summarizes the work already implemented in the `fft` codebase, based on code analysis, for use in writing the paper.

---

## 1. Overview

- **Goal**: On-chain verification of GKR proofs for an FFT-style circuit (addition tree, output = sum of inputs), comparing **direct execution** (run the circuit on-chain) vs **GKR verify** (verify a proof on-chain).
- **Chains**: EVM (Solidity) and Starknet (Cairo). Gas/fee measured and reported in ETH (EVM: gas × gas price; Starknet: fee in STRK converted via market rate).
- **Scope implemented**: FFT circuit, prover, verifier (Python); Solidity and Cairo contracts; gas/fee comparison scripts; IPFS-style optimization (no full input on-chain).

---

## 2. FFT Circuit and Field

- **Circuit** (`gkr_prover_fft.py`, `gkr_verifier_fft.py`):  
  - **Definition**: For size `n` (power of 2), the circuit has an input layer of `n` values, then `log₂(n)` layers of gates. Each gate is an **ADD** combining two previous-layer values (simplified FFT with **ω = 1**, so effectively “even + odd”). Output layer has one value: **sum of all inputs**.  
  - **Structure**: Layered arithmetic circuit compatible with the GKR protocol (layer sizes and variable counts computed in `build_fft_circuit`).
- **Field**: Same prime in all components: **Starknet PRIME**  
  `P = 0x800000000000011000000000000000000000000000000000000000000000001`  
  (used in Python, Solidity, Cairo, and JS helpers).

---

## 3. Prover (Off-Chain)

- **Location**: `fft/gkr_prover_fft.py`.  
- **Dependencies**: Uses shared GKR prover from `gkr_prover` (via `sys.path` to a sibling `python` directory).
- **Functionality**:
  - Builds the FFT circuit for given `n`.
  - Reads input from a file, runs the GKR prover to generate a proof (output, sumcheck rounds: g0, g1, g2 per round).
  - Writes proof to a text file (format: `n`, input line, output, g0 line, g1 line, g2 line; optionally lines 7–8 for vaVb and nextClaimed).
- **Testing**: `run_tests.py` runs prove + verify for n = 2, 4, 8, 16; `run_128_test.py` for n = 128 (assumes `gkr_prover` / `gkr_verifier` on PYTHONPATH).

---

## 4. Verifier (Off-Chain, Python)

- **Location**: `fft/gkr_verifier_fft.py`.  
- **Dependencies**: Uses shared GKR verifier from `gkr_verifier` (Circuit, MLE, Sumcheck, Fiat–Shamir, etc.).
- **Main components**:
  - **FFTWiringPredicates**: Wiring predicates for the FFT circuit with **O(log n) sparse evaluation** of the wiring MLE (grouped by prefix/suffix; no full gate iteration).
  - **FFTGKRVerifier**: Extends the base GKR verifier; **verify_proof** uses the FFT-optimized wiring and **recursive layer MLE evaluation** (O(log n)) so that verification does not scale with n in a naive way.
  - **compute_ipfs_extra**: Runs the same verification logic but returns **(vaVb, nextClaimed)** for use by the **verifyWithIPFS / verify_with_ipfs** contract interface (so the chain does not need the full input).
- **Proof file format**: Parsed in `parse_proof_file` (n, inputs, output, g0, g1, g2; optional vaVb and nextClaimed on lines 7–8).
- **CLI**: `python gkr_verifier_fft.py <proof_file>` for verification; `python gkr_verifier_fft.py <proof_file> --ipfs-extra` to print vaVb and nextClaimed only (for scripts).

---

## 5. Smart Contracts

### 5.1 EVM (Solidity)

- **Source**: Referenced in the project README and build artifacts under `fft/artifacts/contracts/` (FFTDirect.sol, FFTVerifier.sol, Field.sol). The repo root README describes the following.
- **FFTDirect**: Direct execution of the same FFT circuit on-chain; `fft(uint256[] calldata input)` returns the sum of inputs. Complexity O(n log n); gas grows with n.
- **FFTVerifier**:
  - **verifyFull(input, output, g0, g1, g2, roundCounts)**: Full verification with full input (input MLE and layer recursion on-chain). Gas includes O(n) input layer; for n ≥ 128, runs out of gas in practice.
  - **verifyWithIPFS(inputCommitment, output, g0, g1, g2, roundCounts, vaVb, nextClaimed)**: Input not sent; only a commitment and the proof (including vaVb and nextClaimed). Saves calldata and on-chain input MLE; gas grows slowly with n (~350k–530k in the reported table).
- **Field.sol**: Shared finite-field arithmetic (mod, Lagrange interpolation, etc.) for both contracts.
- **Gas comparison**: README states that `npx hardhat run scripts/compareGas.js` deploys both contracts and compares gas for `fft`, `verifyFull`, and `verifyWithIPFS`; the script is expected to be run from the project root (EVM tooling may live in a parent or sibling repo).

### 5.2 Starknet (Cairo)

- **Location**: `fft/starknet/src/lib.cairo`.  
- **Design**: Intended to match Solidity FFTVerifier.verifyWithIPFS logic over Starknet PRIME (felt252).
- **FftDirect**: On-chain direct FFT circuit execution; `fft(input)` returns the sum of inputs. O(n log n) operations.
- **FftVerifier**:
  - **verify_with_ipfs(input_commitment, output, g0, g1, g2, round_counts, va_vb, next_claimed)**: Same idea as verifyWithIPFS: no full input on-chain; contract only uses the provided proof and extra data. `input_commitment` is kept for ABI; the current verification logic does not check it.
- **Auxiliary functions**: Field division, pow2, Fiat–Shamir challenge (same constants as Python/Solidity), Lagrange interpolation at three points, **wiring_mle_sparse** (sparse FFT wiring MLE in O(log n)), layer sizes and round counts derived from the circuit structure.
- **Build**: `npm run starknet:build` or `cd starknet && scarb build`; outputs in `starknet/target/dev/`.

---

## 6. Scripts and Measured Results

### 6.1 Starknet fee comparison

- **Script**: `fft/scripts/compareGasStarknet.js`.  
- **Steps**: Deploys FftDirect and FftVerifier on a Starknet devnet (or configured RPC); for each proof file in `proof/` (e.g. `test_fft_2_proof.txt` … `test_fft_2048_proof.txt`), estimates fee for direct FFT and for GKR verify (`verify_with_ipfs`).  
- **Output**: Table of fee per n. Fee is reported in STRK (overall_fee / 1e18) or, if **STRK_TO_ETH** is set, in ETH.  
- **IPFS extra**: If the proof file has no lines 7–8 (vaVb, nextClaimed), the script can call `gkr_verifier_fft.py <proof> --ipfs-extra` (with PYTHONPATH set) or use **ipfsExtra.js** to compute them in pure JS from the parsed proof.

### 6.2 ipfsExtra.js

- **Location**: `fft/scripts/ipfsExtra.js`.  
- **Role**: Pure JavaScript implementation of the same vaVb and nextClaimed computation as in the contract and Python, so that Starknet (and any EVM) gas/fee scripts can run without invoking Python. Used by `compareGasStarknet.js` when proof files lack lines 7–8.

### 6.3 EVM gas comparison

- **Documented**: Root README and slides report EVM gas for FFTDirect.fft vs verifyWithIPFS (and verifyFull where feasible). Crossover: direct FFT cheaper for n ≤ 256, GKR verify cheaper for n ≥ 512 (e.g. ~47% less gas at n = 1024).  
- **Script**: `compareGas.js` is referenced from the root (e.g. `npx hardhat run scripts/compareGas.js`); it may live in the same repo at the root or in another repo; the **reported gas table** is consistent with the described contracts and interfaces.

---

## 7. Proof and Test Data

- **Proof format**: Text files (e.g. in `proof/`) with at least 6 lines: n, inputs, output, g0, g1, g2; optionally lines 7–8 for vaVb and nextClaimed.  
- **Inputs**: `run_tests.py` expects input files under `input/` (e.g. `test_fft_2.txt`, …).  
- **Coverage**: Tests and gas/fee tables cover n = 2, 4, 8, 16, 64, 128, 256, 512, 1024 (and 2048 in slides, possibly extrapolated).

---

## 8. Summary Table for the Paper

| Component | What is implemented |
|-----------|--------------------|
| **Circuit** | FFT-style addition tree (ω = 1), n inputs → one output (sum); layered, GKR-compatible. |
| **Prover** | Python (`gkr_prover_fft.py`); builds circuit, generates GKR proof; writes proof file. |
| **Verifier (off-chain)** | Python (`gkr_verifier_fft.py`); FFT-optimized wiring O(log n), recursive layer MLE; `verify_proof` and `compute_ipfs_extra`. |
| **EVM contracts** | FFTDirect (direct FFT), FFTVerifier (verifyFull, verifyWithIPFS); Field library; gas measured and reported. |
| **Starknet contracts** | FftDirect, FftVerifier.verify_with_ipfs; same field and verification logic as Solidity. |
| **Fee/gas scripts** | Starknet: `compareGasStarknet.js` (fee table, STRK/ETH); EVM: gas table in README/slides (compareGas.js referenced). |
| **IPFS-style optimization** | verifyWithIPFS / verify_with_ipfs: no full input on-chain; commitment + proof (g0, g1, g2, round_counts, vaVb, nextClaimed); vaVb/nextClaimed from Python or ipfsExtra.js. |

---

## 9. What Has Not Been Done (in This Repo)

- **Inner product**: Attempted elsewhere (or in another branch); not successfully used on-chain here; reasons documented in slides (circuit structure, arithmetization cost, prioritization).
- **Convolution / merge sort**: Mentioned as extensions; no GKR circuits or gas/fee data in this codebase yet.
- **Actual IPFS**: No code that uploads or fetches by CID; “IPFS” in the contract names means “verify without sending full input” (commitment + proof only).

---

*Generated from code analysis of the `fft` directory for use in the paper. Update this file if new experiments or contracts are added.*
