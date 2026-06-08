const { emit, getToolFilePath, isSensitivePath, readHookPayload, toPosixPath } = require("./hookUtils.cjs");

async function main() {
  const payload = await readHookPayload();
  const target = getToolFilePath(payload);
  if (!target) return;
  const p = toPosixPath(target);

  if (p.includes("/bitcoin_blockchain_dev/")) {
    emit({ decision: "block", reason: "bitcoin_blockchain_dev/ is READ-ONLY reference material. DO NOT modify." });
    return;
  }
  if (p.includes("rpc_credentials")) {
    emit({ decision: "block", reason: "RPC credentials file must not be committed or overwritten by AI." });
    return;
  }
  if (isSensitivePath(target)) {
    emit({ decision: "block", reason: `Refusing to write ${target} — sensitive file. Confirm explicitly with the user before retrying.` });
  }
}

main().catch((e) => {
  process.stderr.write(`[hook] pre-tool-use failed: ${e.message}\n`);
  process.exitCode = 0;
});
