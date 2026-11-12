const AMOUNT_REGEX = /^\d+(\.\d{1,2})?$/;
const MAX_SATANG = 999999999999; // 9,999,999,999.99

/**
 * Strips commas and checks strict numeric formatting, parsing into satang (cents).
 * Never uses parseFloat or Number(str) directly on decimal points.
 */
export function parseAmountToSatang(input: string, allowZero = false): number {
  if (typeof input !== "string") {
    throw new Error("Amount must be a string");
  }
  const clean = input.replace(/,/g, "").trim();
  if (!AMOUNT_REGEX.test(clean)) {
    throw new Error("Amount must be a valid numeric string with up to 2 decimal places");
  }

  const parts = clean.split(".");
  const baht = parseInt(parts[0], 10);
  let satang = 0;
  if (parts.length === 2) {
    const dec = parts[1];
    if (dec.length === 1) {
      satang = parseInt(dec, 10) * 10;
    } else if (dec.length === 2) {
      satang = parseInt(dec, 10);
    }
  }

  const total = baht * 100 + satang;
  if (allowZero) {
    if (total < 0) throw new Error("Amount cannot be negative");
  } else {
    if (total <= 0) throw new Error("Amount must be greater than zero");
  }
  if (total > MAX_SATANG) {
    throw new Error("Amount exceeds maximum limit");
  }

  return total;
}

/**
 * Formats integer satang to fixed two decimal string ("1000.00").
 */
export function formatSatangToAmount(satang: number): string {
  const sign = satang < 0 ? "-" : "";
  const abs = Math.abs(satang);
  const baht = Math.floor(abs / 100);
  const rem = abs % 100;
  return `${sign}${baht}.${rem < 10 ? "0" : ""}${rem}`;
}

/**
 * Formats integer satang with commas ("1,000.00").
 */
export function formatSatangToDisplay(satang: number): string {
  const sign = satang < 0 ? "-" : "";
  const abs = Math.abs(satang);
  const baht = Math.floor(abs / 100);
  const rem = abs % 100;
  const bahtStr = baht.toLocaleString("en-US");
  return `${sign}${bahtStr}.${rem < 10 ? "0" : ""}${rem}`;
}

/**
 * Allocates equal shares and distributes residual satang according to group's deterministic member order.
 */
export function allocateEqualShares(
  totalSatang: number,
  orderedMembers: string[]
): { username: string; satang: number; amount: string }[] {
  if (orderedMembers.length === 0) return [];
  const count = orderedMembers.length;
  const base = Math.floor(totalSatang / count);
  const remainder = totalSatang % count;

  return orderedMembers.map((username, index) => {
    const s = base + (index < remainder ? 1 : 0);
    return {
      username,
      satang: s,
      amount: formatSatangToAmount(s),
    };
  });
}
