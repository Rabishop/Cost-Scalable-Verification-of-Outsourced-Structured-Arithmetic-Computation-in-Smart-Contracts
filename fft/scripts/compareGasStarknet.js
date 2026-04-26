/**
 * Starknet：对比「直接 FFT」与「GKR 验证 FFT」的 fee
 *
 * overall_fee 如何换算：
 * - V3 交易 estimateInvokeFee 返回的 overall_fee 单位是 FRI（Starknet 文档：FRI = STRK 的最小单位，1 STRK = 10^18 FRI）
 * - STRK = overall_fee / 1e18
 * - 链上只收 STRK，协议没有固定 STRK↔ETH 汇率；要得到「等价多少 ETH」需用市价：ETH = STRK × (STRK/ETH 汇率)
 *
 * 环境变量：
 * - STRK_TO_ETH：可选，当前 1 STRK = 多少 ETH（例如 0.5）。若设置，输出为「X.XX ETH」；未设置则输出「X.XX STRK」
 * - STARKNET_NODE_URL, STARKNET_ACCOUNT_ADDRESS, STARKNET_PRIVATE_KEY
 *
 * 运行: node scripts/compareGasStarknet.js
 */

const starknet = require("starknet");
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");
const { computeIpfsExtra } = require("./ipfsExtra.js");

const PRIME = BigInt("0x800000000000011000000000000000000000000000000000000000000000001");
const PROJECT_ROOT = path.join(__dirname, "..");
const STARKNET_ARTIFACTS = path.join(PROJECT_ROOT, "starknet", "target", "dev");

const NODE_URL = process.env.STARKNET_NODE_URL || "http://127.0.0.1:5050/rpc";
const ACCOUNT_ADDRESS = process.env.STARKNET_ACCOUNT_ADDRESS || "0x064b48806902a367c8598f4f95c305e8c1a1acba5f082d294a43793113115691";
const PRIVATE_KEY = process.env.STARKNET_PRIVATE_KEY || "0x0000000000000000000000000000000071d7bb07b9a64f6f78ac4c816aff4da9";
const FRI_PER_STRK = 1e18; // 1 STRK = 10^18 FRI (Starknet 文档)
const STRK_TO_ETH = process.env.STRK_TO_ETH ? parseFloat(process.env.STRK_TO_ETH) : null;

function toHex(b) {
  if (typeof b === "bigint") return "0x" + b.toString(16);
  return starknet.num ? starknet.num.toHex(b) : "0x" + BigInt(b).toString(16);
}

function roundCountsForN(n) {
  const numLayers = Math.floor(Math.log2(n)) + 1;
  const counts = [];
  for (let layer = 0; layer < numLayers - 1; layer++) {
    const nextSize = 1 << (layer + 1);
    const abVars = nextSize <= 1 ? 1 : Math.floor(Math.log2(nextSize - 1)) + 1;
    counts.push(2 * abVars);
  }
  return counts;
}

function parseProofFile(filePath) {
  const content = fs.readFileSync(filePath, "utf8");
  const lines = content.trim().split(/\r?\n/).filter(Boolean);
  if (lines.length < 6) throw new Error("Proof file needs at least 6 lines");
  const n = parseInt(lines[0], 10);
  const input = lines[1].split(/\s+/).map((s) => BigInt(s) % PRIME);
  const output = BigInt(lines[2]) % PRIME;
  const g0 = lines[3].split(/\s+/).map((s) => BigInt(s) % PRIME);
  const g1 = lines[4].split(/\s+/).map((s) => BigInt(s) % PRIME);
  const g2 = lines[5].split(/\s+/).map((s) => BigInt(s) % PRIME);
  const roundCounts = roundCountsForN(n);
  let vaVb = null;
  let nextClaimed = null;
  if (lines.length >= 8 && /^\d/.test(lines[6]) && /^\d/.test(lines[7])) {
    vaVb = lines[6].split(/\s+/).map((s) => BigInt(s) % PRIME);
    nextClaimed = lines[7].split(/\s+/).map((s) => BigInt(s) % PRIME);
  }
  return { n, input, output, g0, g1, g2, roundCounts, vaVb, nextClaimed };
}

function getIpfsExtraFromPython(proofPath) {
  const verifierPath = path.join(PROJECT_ROOT, "gkr_verifier_fft.py");
  const cmd = `python "${verifierPath}" "${proofPath}" --ipfs-extra`;
  const PYTHONPATH = process.env.PYTHONPATH || path.join(PROJECT_ROOT, "..", "2026-01-04-gkr-project", "python");
  const opts = { encoding: "utf8", cwd: PROJECT_ROOT, env: { ...process.env, PYTHONPATH } };
  try {
    const out = execSync(cmd, opts).trim();
    const twoLines = out.split(/\r?\n/);
    if (twoLines.length < 2) throw new Error("Expected 2 lines from --ipfs-extra");
    const vaVb = twoLines[0].split(/\s+/).map((s) => BigInt(s) % PRIME);
    const nextClaimed = twoLines[1].split(/\s+/).map((s) => BigInt(s) % PRIME);
    return { vaVb, nextClaimed };
  } catch (e) {
    throw new Error("Failed to run Python for IPFS extra: " + (e.stderr || e.message));
  }
}

function arrayToCalldata(arr) {
  return [toHex(arr.length)].concat(arr.map((x) => toHex(x)));
}

function buildFftCalldata(input) {
  return arrayToCalldata(input);
}

function buildVerifyWithIpfsCalldata(parsed) {
  const { output, g0, g1, g2, roundCounts, vaVb, nextClaimed } = parsed;
  if (!vaVb || !nextClaimed) throw new Error("Need vaVb and nextClaimed");
  const calldata = [
    toHex(0n),
    toHex(output),
    ...arrayToCalldata(g0),
    ...arrayToCalldata(g1),
    ...arrayToCalldata(g2),
    ...arrayToCalldata(roundCounts.map((x) => BigInt(x))),
    ...arrayToCalldata(vaVb),
    ...arrayToCalldata(nextClaimed),
  ];
  return calldata;
}

/** 将 fee（FRI）格式化为 STRK 或 ETH：STRK = fee/1e18；若设 STRK_TO_ETH 则再乘该系数得到 ETH */
function formatFee(feeBigInt) {
  if (feeBigInt == null || feeBigInt === undefined) return "-";
  const n = typeof feeBigInt === "bigint" ? Number(feeBigInt) : Number(feeBigInt);
  if (n !== n || n < 0) return "-";
  const strk = n / FRI_PER_STRK;
  const value = STRK_TO_ETH != null ? strk * STRK_TO_ETH : strk;
  const unit = STRK_TO_ETH != null ? " ETH" : " STRK";
  const s = value >= 1 ? value.toFixed(4) : value.toFixed(8);
  return s.replace(/\.?0+$/, "") + unit;
}

async function declareAndDeploy(account, sierraPath, casmPath, label) {
  const contractClass = JSON.parse(fs.readFileSync(sierraPath, "utf8"));
  const casmClass = fs.existsSync(casmPath) ? JSON.parse(fs.readFileSync(casmPath, "utf8")) : undefined;
  if (!casmClass) throw new Error(`缺少 CASM: ${casmPath}`);
  let classHash;
  try {
    const declareTx = await account.declare({ contract: contractClass, casm: casmClass });
    classHash = declareTx.class_hash ?? declareTx.classHash;
  } catch (e) {
    if (e.message && (e.message.includes("already declared") || e.message.includes("CLASS_ALREADY_DECLARED")))
      classHash = starknet.hash.computeContractClassHash(contractClass);
    else throw e;
  }
  const deployResp = await account.deployContract({ classHash, constructorCalldata: [] });
  return deployResp.contract_address ?? deployResp.address;
}

async function main() {
  const feeUnit = STRK_TO_ETH != null ? "ETH" : "STRK";
  console.log(`=== Starknet: 直接 FFT vs GKR 验证 FFT — Fee 对比（${feeUnit}） ===\n`);
  console.log("节点:", NODE_URL);
  if (STRK_TO_ETH != null) {
    console.log(`说明: overall_fee 为 FRI，STRK = fee/1e18；已按 STRK_TO_ETH=${STRK_TO_ETH} 换算为 ETH。`);
  } else {
    console.log("说明: overall_fee 为 FRI，下表为 STRK（fee/1e18）。要换算为 ETH 请设置环境变量 STRK_TO_ETH（1 STRK = 多少 ETH）。");
  }
  console.log("");

  const provider = new starknet.RpcProvider({ nodeUrl: NODE_URL });
  const account = new starknet.Account({ provider, address: ACCOUNT_ADDRESS, signer: PRIVATE_KEY });

  const directSierra = path.join(STARKNET_ARTIFACTS, "fft_verifier_FftDirect.contract_class.json");
  const directCasm = path.join(STARKNET_ARTIFACTS, "fft_verifier_FftDirect.compiled_contract_class.json");
  const verifierSierra = path.join(STARKNET_ARTIFACTS, "fft_verifier_FftVerifier.contract_class.json");
  const verifierCasm = path.join(STARKNET_ARTIFACTS, "fft_verifier_FftVerifier.compiled_contract_class.json");
  if (!fs.existsSync(directSierra) || !fs.existsSync(verifierSierra)) {
    console.error("请先执行: npm run starknet:build");
    process.exit(1);
  }

  console.log("部署 FftDirect...");
  const directAddress = await declareAndDeploy(account, directSierra, directCasm, "FftDirect");
  console.log("FftDirect 地址:", directAddress);
  console.log("部署 FftVerifier...");
  const verifierAddress = await declareAndDeploy(account, verifierSierra, verifierCasm, "FftVerifier");
  console.log("FftVerifier 地址:", verifierAddress);
  console.log("");

  const proofDir = path.join(PROJECT_ROOT, "proof");
  const proofFiles = fs.readdirSync(proofDir).filter((f) => f.match(/^test_fft_\d+_proof\.txt$/));
  const toRun = proofFiles
    .map((f) => ({ name: "n=" + f.replace(/\D/g, ""), proofPath: path.join(proofDir, f), n: parseInt(f.replace(/\D/g, ""), 10) }))
    .sort((a, b) => a.n - b.n);

  const results = [];
  for (const { name, proofPath, n } of toRun) {
    const parsed = parseProofFile(proofPath);
    let { vaVb, nextClaimed } = parsed;
    if (vaVb == null || nextClaimed == null) {
      try {
        const extra = getIpfsExtraFromPython(proofPath);
        vaVb = extra.vaVb;
        nextClaimed = extra.nextClaimed;
      } catch (_) {
        try {
          const extra = computeIpfsExtra(parsed);
          vaVb = extra.vaVb;
          nextClaimed = extra.nextClaimed;
        } catch (e) {
          console.log(`${name} 跳过: ${e.message}`);
          continue;
        }
      }
    }
    const parsedWithExtra = { ...parsed, vaVb, nextClaimed };

    let feeDirect = null;
    let feeGkr = null;
    try {
      const fftCalldata = buildFftCalldata(parsed.input);
      const estDirect = await account.estimateInvokeFee({
        contractAddress: directAddress,
        entrypoint: "fft",
        calldata: fftCalldata,
      });
      feeDirect = estDirect.overall_fee;
    } catch (e) {
      console.log(`${name} 直接 FFT 预估失败:`, e.message);
    }
    try {
      const verifyCalldata = buildVerifyWithIpfsCalldata(parsedWithExtra);
      const estGkr = await account.estimateInvokeFee({
        contractAddress: verifierAddress,
        entrypoint: "verify_with_ipfs",
        calldata: verifyCalldata,
      });
      feeGkr = estGkr.overall_fee;
    } catch (e) {
      console.log(`${name} GKR 验证预估失败:`, e.message);
    }

    results.push({ n, name, feeDirect, feeGkr });
  }

  console.log(`\n========== Fee 对比（${feeUnit}） ==========`);
  console.log("规模 n\t直接 FFT\tGKR 验证\t更省");
  console.log("---");
  for (const r of results) {
    const directStr = formatFee(r.feeDirect);
    const gkrStr = formatFee(r.feeGkr);
    let better = "-";
    if (r.feeDirect != null && r.feeGkr != null) {
      const d = typeof r.feeDirect === "bigint" ? Number(r.feeDirect) : r.feeDirect;
      const g = typeof r.feeGkr === "bigint" ? Number(r.feeGkr) : r.feeGkr;
      better = g < d ? "GKR" : "直接FFT";
    }
    console.log(`${r.n}\t${directStr}\t${gkrStr}\t${better}`);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
