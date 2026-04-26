/**
 * 纯 JS 实现 IPFS 附加数据 (vaVb, nextClaimed) 计算，与合约/Python 一致。
 * 不依赖 gkr_verifier，供 compareGas.js 与 compareGasStarknet.js 在无 Python 时使用。
 */

const PRIME = BigInt("0x800000000000011000000000000000000000000000000000000000000000001");

function mod(x) {
  x = BigInt(x);
  return x >= PRIME ? x % PRIME : x;
}
function add(a, b) { return mod(BigInt(a) + BigInt(b)); }
function mul(a, b) { return mod(BigInt(a) * BigInt(b)); }
function sub(a, b) { return mod(PRIME + BigInt(a) - BigInt(b)); }
function inv(a) {
  a = BigInt(a);
  if (a === 0n) return 0n;
  return pow(a, PRIME - 2n);
}
function pow(base, exp) {
  base = mod(base);
  let result = 1n;
  for (; exp > 0n; exp >>= 1n) {
    if ((exp & 1n) !== 0n) result = mul(result, base);
    base = mul(base, base);
  }
  return result;
}
function lagrange3(g0, g1, g2, x) {
  const xm1 = sub(x, 1);
  const xm2 = sub(x, 2);
  const l0 = mul(mul(xm1, xm2), mul(inv(PRIME - 1n), inv(PRIME - 2n)));
  const l1 = mul(mul(x, xm2), inv(PRIME - 1n));
  const l2 = mul(mul(x, xm1), inv(2));
  return add(add(mul(g0, l0), mul(g1, l1)), mul(g2, l2));
}
function challenge(state, _first, g0, g1) {
  const data = add(add(state, mul(g0, 1000000)), g1);
  return mod(mul(data, 2654435761) + 2246822507n);
}
function log2(x) {
  let r = 0;
  for (let t = BigInt(x); t > 0n; t >>= 1n) r++;
  return r;
}
function inputMleAt(input, point) {
  const k = point.length;
  const n = 1 << k;
  let sum = 0n;
  for (let i = 0; i < n; i++) {
    let chi = 1n;
    for (let j = 0; j < k; j++) {
      const bit = (i >> (k - 1 - j)) & 1;
      chi = mul(chi, bit === 1 ? point[j] : mod(PRIME - BigInt(point[j]) + 1n));
    }
    sum = add(sum, mul(mod(input[i]), chi));
  }
  return sum;
}
function layerMleRecursive(layerIdx, point, input, layerNumVars) {
  const numVars = layerNumVars[layerIdx];
  if (layerIdx === layerNumVars.length - 1) return inputMleAt(input, point);
  const nextVars = layerNumVars[layerIdx + 1];
  const concatLen = numVars + 1;
  const p0 = [];
  const p1 = [];
  for (let j = 0; j < nextVars; j++) {
    let srcIdx;
    if (concatLen >= nextVars) {
      srcIdx = concatLen - nextVars + j;
      p0.push(srcIdx < numVars ? point[srcIdx] : 0n);
      p1.push(srcIdx < numVars ? point[srcIdx] : 1n);
    } else {
      if (j < nextVars - concatLen) {
        p0.push(0n);
        p1.push(0n);
      } else {
        const i = j - (nextVars - concatLen);
        p0.push(i < numVars ? point[i] : 0n);
        p1.push(i < numVars ? point[i] : 1n);
      }
    }
  }
  return add(
    layerMleRecursive(layerIdx + 1, p0, input, layerNumVars),
    layerMleRecursive(layerIdx + 1, p1, input, layerNumVars)
  );
}

/**
 * 从已解析的 proof 计算 vaVb 与 nextClaimed（与 Python compute_ipfs_extra 一致）
 * @param {{ n, input, output, g0, g1, g2, roundCounts }} parsed
 * @returns {{ vaVb: bigint[], nextClaimed: bigint[] }}
 */
function computeIpfsExtra(parsed) {
  const { n, input, output, g0, g1, g2, roundCounts } = parsed;
  const numLayers = roundCounts.length + 1;
  const layerNumVars = [];
  for (let i = 0; i < numLayers; i++) {
    const size = 1 << i;
    layerNumVars.push(size <= 1 ? 1 : log2(size - 1));
  }
  const vaVb = [];
  const nextClaimed = [];
  let globalIdx = 0;
  let currentClaimed = output;
  let currentPoint = Array(layerNumVars[0]).fill(0n);

  for (let layerIdx = 0; layerIdx < numLayers - 1; layerIdx++) {
    const rounds = roundCounts[layerIdx];
    let state = add(g0[globalIdx], g1[globalIdx]);
    if (state !== currentClaimed) throw new Error("claimed_sum mismatch");
    const fixed = [];
    let prevVal = state;
    for (let r = 0; r < rounds; r++) {
      const g0r = g0[globalIdx + r];
      const g1r = g1[globalIdx + r];
      const g2r = g2[globalIdx + r];
      if (add(g0r, g1r) !== prevVal) throw new Error("sumcheck round mismatch");
      const rVal = challenge(state, r === 0, g0r, g1r);
      state = rVal;
      prevVal = lagrange3(g0r, g1r, g2r, rVal);
      fixed.push(rVal);
    }
    globalIdx += rounds;
    const s = Math.floor(rounds / 2);
    const aPoint = fixed.slice(0, s);
    const bPoint = fixed.slice(s, s + s);
    const v_a = layerMleRecursive(layerIdx + 1, aPoint, input, layerNumVars);
    const v_b = layerMleRecursive(layerIdx + 1, bPoint, input, layerNumVars);
    vaVb.push(v_a, v_b);
    let data = 0n;
    for (let k = 0; k < s && k < aPoint.length; k++) {
      data = add(data, mul(aPoint[k], pow(2n, BigInt(k * 32))));
      data = add(data, mul(bPoint[k], pow(2n, BigInt((s + k) * 32))));
    }
    const hashVal = mod(mul(data, 2654435761) + 2246822507n);
    const nextS = layerNumVars[layerIdx + 1];
    currentPoint = [];
    for (let i = 0; i < nextS; i++) currentPoint.push(mod(mul(hashVal, 1000000) + BigInt(i)));
    currentClaimed = layerMleRecursive(layerIdx + 1, currentPoint, input, layerNumVars);
    nextClaimed.push(currentClaimed);
  }
  return { vaVb, nextClaimed };
}

module.exports = { PRIME, computeIpfsExtra };
