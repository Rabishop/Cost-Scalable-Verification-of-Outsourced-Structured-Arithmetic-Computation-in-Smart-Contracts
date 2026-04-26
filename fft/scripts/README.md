# 脚本说明

## compareGasStarknet.js

对比 **直接 FFT** 与 **GKR 验证 FFT** 在 Starknet 上的 fee。

- **overall_fee** 单位是 **FRI**（1 STRK = 10^18 FRI）。默认输出 **STRK**（= fee/1e18）。
- 要换成 **ETH**：设环境变量 `STRK_TO_ETH`（1 STRK = 多少 ETH，用当前市价），例如 `STRK_TO_ETH=0.5 node scripts/compareGasStarknet.js`。

```bash
npm run test:gas:starknet
# 输出 STRK；若需 ETH：STRK_TO_ETH=0.5 npm run test:gas:starknet
```

需先 `npm run starknet:build` 并启动 devnet（如 `starknet-devnet --port 5050`）。

## ipfsExtra.js

纯 JS 计算 proof 的 vaVb、nextClaimed，供 `compareGasStarknet.js` 在无 Python 时使用。
