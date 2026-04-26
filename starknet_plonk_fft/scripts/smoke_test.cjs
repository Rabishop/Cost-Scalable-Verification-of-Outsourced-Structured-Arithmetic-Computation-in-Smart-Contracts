const fs = require("fs");
const path = require("path");

const PRIME = BigInt("0x800000000000011000000000000000000000000000000000000000000000001");
const INPUT_DIR = path.join(__dirname, "..", "input");
const PROOF_LEN = 64;

function parseFftTxt(filePath) {
  const text = fs.readFileSync(filePath, "utf8");
  const lines = text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  const n = parseInt(lines[0], 10);
  const inputs = lines[1].split(/\s+/).filter(Boolean).map((s) => BigInt(s) % PRIME);
  if (inputs.length !== n) throw new Error(`${filePath}: need ${n} inputs`);
  const sum = inputs.reduce((a, b) => (a + b) % PRIME, 0n);
  return { n, sum };
}

let ok = true;
const files = fs.readdirSync(INPUT_DIR).filter((f) => /^test_fft_\d+\.txt$/.test(f));
files.sort((a, b) => parseInt(a.match(/\d+/)[0], 10) - parseInt(b.match(/\d+/)[0], 10));
for (const f of files) {
  try {
    const { n, sum } = parseFftTxt(path.join(INPUT_DIR, f));
    console.log(`OK ${f}: n=${n}, public_out=sum=${sum}, proof_limbs=${PROOF_LEN}`);
  } catch (e) {
    console.error(`FAIL ${f}:`, e.message);
    ok = false;
  }
}
process.exit(ok ? 0 : 1);
