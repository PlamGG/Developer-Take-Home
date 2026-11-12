import assert from "node:assert";
import test from "node:test";
import {
  allocateEqualShares,
  formatSatangToAmount,
  formatSatangToDisplay,
  parseAmountToSatang,
} from "./money.ts";

test("parseAmountToSatang strictly parses amounts without float corruption", () => {
  assert.strictEqual(parseAmountToSatang("100.00"), 10000);
  assert.strictEqual(parseAmountToSatang("0.01"), 1);
  assert.strictEqual(parseAmountToSatang("10"), 1000);
  assert.strictEqual(parseAmountToSatang("10.5"), 1050);
  assert.strictEqual(parseAmountToSatang("1,000.50"), 100050);

  // Invalid throws
  assert.throws(() => parseAmountToSatang("0"));
  assert.throws(() => parseAmountToSatang("-10.00"));
  assert.throws(() => parseAmountToSatang("1e3"));
  assert.throws(() => parseAmountToSatang("10.001"));
});

test("Shared test vectors match backend exactly", () => {
  // 1. 100.00 / 3 -> 33.34, 33.33, 33.33
  const satang100 = parseAmountToSatang("100.00");
  const res100 = allocateEqualShares(satang100, ["alice", "bob", "carol"]);
  assert.deepStrictEqual(
    res100.map((r) => r.amount),
    ["33.34", "33.33", "33.33"]
  );

  // 2. 0.01 / 3 -> 0.01, 0.00, 0.00
  const satang001 = parseAmountToSatang("0.01");
  const res001 = allocateEqualShares(satang001, ["alice", "bob", "carol"]);
  assert.deepStrictEqual(
    res001.map((r) => r.amount),
    ["0.01", "0.00", "0.00"]
  );

  // 3. 0.10 / 3 -> 0.04, 0.03, 0.03
  const satang010 = parseAmountToSatang("0.10");
  const res010 = allocateEqualShares(satang010, ["alice", "bob", "carol"]);
  assert.deepStrictEqual(
    res010.map((r) => r.amount),
    ["0.04", "0.03", "0.03"]
  );

  // 4. 0.1 + 0.2 equivalent -> 0.30
  const total = parseAmountToSatang("0.10") + parseAmountToSatang("0.20");
  assert.strictEqual(formatSatangToAmount(total), "0.30");
  assert.strictEqual(formatSatangToDisplay(total), "0.30");

  // 5. Large amount
  const satangLarge = parseAmountToSatang("9999999999.99");
  const resLarge = allocateEqualShares(satangLarge, ["alice", "bob"]);
  assert.deepStrictEqual(
    resLarge.map((r) => r.amount),
    ["5000000000.00", "4999999999.99"]
  );
  assert.strictEqual(formatSatangToDisplay(resLarge[0].satang), "5,000,000,000.00");
});
