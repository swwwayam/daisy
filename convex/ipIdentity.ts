/** Normalize equivalent IP spellings; group IPv6 privacy addresses by /64. */
export function signupNetwork(ip: string): string {
  const raw = ip.trim().replace(/^\[|\]$/g, "");
  if (!raw || raw.length > 64 || raw.includes("%")) throw new Error("Invalid request IP");
  if (!raw.includes(":")) {
    const parts = raw.split(".");
    if (parts.length !== 4 || parts.some(p => !/^\d{1,3}$/.test(p) || Number(p) > 255)) throw new Error("Invalid request IP");
    return parts.map(Number).join(".");
  }
  // URL's IPv6 parser validates and canonicalizes compressed and embedded IPv4.
  const canonical = new URL(`https://[${raw}]/`).hostname.slice(1, -1);
  const halves = canonical.split("::");
  const left = halves[0] ? halves[0].split(":") : [];
  const right = halves[1] ? halves[1].split(":") : [];
  const parts = halves.length === 2 ? [...left, ...Array(8 - left.length - right.length).fill("0"), ...right] : left;
  const nums = parts.map(p => parseInt(p, 16));
  if (nums.length !== 8 || nums.some(n => !Number.isFinite(n))) throw new Error("Invalid request IP");
  if (nums.slice(0, 5).every(n => n === 0) && nums[5] === 65535) {
    return [nums[6] >> 8, nums[6] & 255, nums[7] >> 8, nums[7] & 255].join(".");
  }
  return `${nums.slice(0, 4).map(n => n.toString(16)).join(":")}::/64`;
}

/** HMAC avoids retaining raw IP addresses or guessable plain IP hashes. */
export async function signupIpKey(ip: string, secret: string): Promise<string> {
  if (!secret) throw new Error("Signup protection secret is missing");
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const signature = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(`daisy-signup:${signupNetwork(ip)}`));
  return Array.from(new Uint8Array(signature), b => b.toString(16).padStart(2, "0")).join("");
}
