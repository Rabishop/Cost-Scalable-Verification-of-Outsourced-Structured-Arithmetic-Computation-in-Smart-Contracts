# FFT 合约 (Starknet / Cairo)

- **FftDirect**：链上直接执行 FFT 电路（O(n log n)，与 Python 一致），`fft(input)` 返回输入之和。
- **FftVerifier**：GKR 证明验证，`verify_with_ipfs(...)` 不传完整 input，验证 FFT 结果。

## 依赖

- [Scarb](https://docs.swmansion.com/scarb/)
- Node（跑 fee 对比脚本）

## 编译

```bash
npm run starknet:build
# 或 cd starknet && scarb build
```

产物在 `starknet/target/dev/`：`fft_verifier_FftDirect.*`、`fft_verifier_FftVerifier.*`。

## Fee 对比（直接 FFT vs GKR 验证）

1. 启动测试网：`starknet-devnet --port 5050`
2. 在 `fft` 目录运行：`npm run test:gas:starknet`

脚本会部署 FftDirect 与 FftVerifier，对每个 proof 规模 n 分别估算 fee，并输出对比表。

**overall_fee 换算（Starknet 文档）**：V3 的 `estimateInvokeFee` 返回的 `overall_fee` 单位是 **FRI**（1 STRK = 10^18 FRI）。链上费用以 **STRK** 收取，协议无固定 STRK↔ETH 汇率。

- **STRK** = overall_fee / 1e18（脚本默认输出 STRK）
- **ETH** = STRK × (当前 STRK/ETH 市价)；需设置环境变量 `STRK_TO_ETH` 后脚本才会输出 ETH

### 环境变量

| 变量 | 说明 | 默认 |
|------|------|------|
| `STARKNET_NODE_URL` | RPC | `http://127.0.0.1:5050/rpc` |
| `STARKNET_ACCOUNT_ADDRESS` | 账户地址 | 见下 |
| `STARKNET_PRIVATE_KEY` | 私钥 | 见下 |
| `STRK_TO_ETH` | 可选。1 STRK = 多少 ETH（市价）。设置后输出列为 ETH，未设置则输出 STRK | 未设置 → 输出 STRK |

### 测试网账户示例

- Account: `0x064b48806902a367c8598f4f95c305e8c1a1acba5f082d294a43793113115691`
- Private key: `0x0000000000000000000000000000000071d7bb07b9a64f6f78ac4c816aff4da9`

### Proof

若 proof 无第 7–8 行（vaVb、nextClaimed），脚本会用 `ipfsExtra.js` 在本地计算，无需 Python。
