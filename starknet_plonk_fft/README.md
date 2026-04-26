# Starknet · Plonk 风格 FFT 验证费用探测（占位实现）

## 重要说明

- **不是**真实 Plonk（KZG/配对）验证器；完整 Plonk on Starknet 同样需要重型 Cairo 密码学组件。
- **`PlonkFftVerify`** 与 `starknet_groth16_fft` 中合约的**公开语义相同**（仅 **1 个** `public_out` = 叶子和 `sum`，不随 `n` 增加 public 个数），但：
  - 占位 **proof 向量更长**（64 vs 24 `felt252`）；
  - **常数步数循环更大**（模拟 Plonk 多承诺/多式评估更重）。
- 因此同 `n` 下 **Plonk 目录测得的 STRK 一般高于 Groth16 目录**，用于**相对比较**；非审计级证明系统实现。

## 输入

与 `starknet_groth16_fft/input` 相同：`n ∈ {2,4,8,16,32}`。

## 运行

```bash
npm install
scarb build
npm run estimate
```

## 产物

- `target/dev/sn_plonk_fft_PlonkFftVerify.contract_class.json`
- `target/dev/sn_plonk_fft_PlonkFftVerify.compiled_contract_class.json`
