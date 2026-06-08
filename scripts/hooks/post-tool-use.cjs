const { emit, getToolFilePath, readHookPayload, toPosixPath } = require("./hookUtils.cjs");

const RULES = [
  {
    test: (p) =>
      p.includes("wallet") ||
      p.includes("keys") ||
      p.includes("address") ||
      p.includes("transaction") ||
      p.includes("signer"),
    context:
      "CRYPTO CODE EDITED. Verify: (1) no private keys logged or printed, (2) entropy sources are secrets/os.urandom only, (3) no custom cryptography introduced, (4) type annotations on all functions, (5) known test vectors validate the operation.",
  },
  {
    test: (p) => p.includes("constants"),
    context: "CONSTANTS FILE EDITED. Verify: (1) values match the Bitcoin protocol specification, (2) units and encoding documented.",
  },
  {
    test: (p) => p.includes("/tests/"),
    context:
      "TEST FILE EDITED. Verify: (1) at least one test uses known Bitcoin test vectors, (2) no mocking of cryptographic operations, (3) exact equality for deterministic crypto ops.",
  },
];

async function main() {
  const payload = await readHookPayload();
  const f = toPosixPath(getToolFilePath(payload));
  if (!f) return;
  const m = RULES.find((r) => r.test(f));
  if (m) emit({ hookSpecificOutput: { hookEventName: "PostToolUse", additionalContext: m.context } });
}

main().catch((e) => {
  process.stderr.write(`[hook] post-tool-use failed: ${e.message}\n`);
  process.exitCode = 0;
});
