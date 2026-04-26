# FFT 智能合约（Starknet）

本目录仅保留说明，合约代码在 **starknet/**（Cairo）。

- **直接 FFT**：`FftDirect.fft(input)` — 链上 O(n log n) 计算，输出为输入之和。
- **GKR 验证**：`FftVerifier.verify_with_ipfs(...)` — 验证 FFT 的 GKR 证明，不传完整 input。

编译与 Fee 对比见 **starknet/README.md**，运行 `npm run test:gas:starknet` 对比两者 fee（以 ETH 等价表示）。
