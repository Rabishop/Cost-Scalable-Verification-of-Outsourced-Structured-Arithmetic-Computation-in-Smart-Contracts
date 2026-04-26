/**
 * 对 Plonk 占位合约做 estimateInvokeFee，输出各 n 的 STRK。
 * 需：Katana/Devnet + scarb build。
 */
const starknet = require("starknet");
const fs = require("fs");
const path = require("path");

const PRIME = BigInt("0x800000000000011000000000000000000000000000000000000000000000001");
const ROOT = path.join(__dirname, "..");
const ARTIFACTS = path.join(ROOT, "target", "dev");
const INPUT_DIR = path.join(ROOT, "input");

const NODE_URL = process.env.STARKNET_NODE_URL || "http://127.0.0.1:5050/rpc";
const ACCOUNT_ADDRESS =
  process.env.STARKNET_ACCOUNT_ADDRESS || "0x064b48806902a367c8598f4f95c305e8c1a1acba5f082d294a43793113115691";
const PRIVATE_KEY =
  process.env.STARKNET_PRIVATE_KEY || "0x0000000000000000000000000000000071d7bb07b9a64f6f78ac4c816aff4da9";

const PACKAGE_PREFIX = "sn_plonk_fft";
const CONTRACT_MODULE = "PlonkFftVerify";
const ENTRYPOINT = "verify_fft";
const PROOF_LEN = 64;

function toHex(b) {
  if (typeof b === "bigint") return "0x" + b.toString(16);
  return "0x" + BigInt(b).toString(16);
}

function parseFftTxt(filePath) {
  const text = fs.readFileSync(filePath, "utf8");
  const lines = text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  const n = parseInt(lines[0], 10);
  const inputs = lines[1].split(/\s+/).filter(Boolean).map((s) => BigInt(s) % PRIME);
  if (inputs.length !== n) throw new Error(`${filePath}: need ${n} inputs`);
  const sum = inputs.reduce((a, b) => (a + b) % PRIME, 0n);
  return { n, inputs, sum };
}

function arrayToCalldata(arr) {
  return [toHex(arr.length)].concat(arr.map((x) => toHex(x)));
}

function buildProofLimbs() {
  const out = [];
  for (let i = 0; i < PROOF_LEN; i++) out.push(BigInt((i + 1) * 11) % PRIME);
  return out;
}

async function declareAndDeploy(account, sierraPath, casmPath) {
  const contractClass = JSON.parse(fs.readFileSync(sierraPath, "utf8"));
  const casmClass = JSON.parse(fs.readFileSync(casmPath, "utf8"));
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

function formatStrk(feeBigInt) {
  if (feeBigInt == null) return "-";
  const n = typeof feeBigInt === "bigint" ? Number(feeBigInt) : Number(feeBigInt);
  const strk = n / 1e18;
  return strk >= 1 ? strk.toFixed(6) : strk.toFixed(10);
}

async function main() {
  const sierra = path.join(ARTIFACTS, `${PACKAGE_PREFIX}_${CONTRACT_MODULE}.contract_class.json`);
  const casm = path.join(ARTIFACTS, `${PACKAGE_PREFIX}_${CONTRACT_MODULE}.compiled_contract_class.json`);
  if (!fs.existsSync(sierra) || !fs.existsSync(casm)) {
    console.error("缺少编译产物。请先在本目录执行: scarb build");
    process.exit(1);
  }

  const provider = new starknet.RpcProvider({ nodeUrl: NODE_URL });
  const account = new starknet.Account({ provider, address: ACCOUNT_ADDRESS, signer: PRIVATE_KEY });

  console.log("部署 PlonkFftVerify (mock)...");
  const addr = await declareAndDeploy(account, sierra, casm);
  console.log("合约地址:", addr);
  console.log("节点:", NODE_URL);
  console.log("\nn\tSTRK (verify fee est.)");
  console.log("---");

  const proof = buildProofLimbs();
  const files = fs.readdirSync(INPUT_DIR).filter((f) => /^test_fft_\d+\.txt$/.test(f));
  files.sort((a, b) => parseInt(a.match(/\d+/)[0], 10) - parseInt(b.match(/\d+/)[0], 10));

  for (const f of files) {
    const { n, sum } = parseFftTxt(path.join(INPUT_DIR, f));
    const calldata = [toHex(sum), ...arrayToCalldata(proof)];
    try {
      const est = await account.estimateInvokeFee({
        contractAddress: addr,
        entrypoint: ENTRYPOINT,
        calldata,
      });
      console.log(`${n}\t${formatStrk(est.overall_fee)}`);
    } catch (e) {
      console.log(`${n}\t(error) ${e.message}`);
    }
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
