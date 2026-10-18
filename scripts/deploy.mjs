#!/usr/bin/env node
/**
 * Pavvl deployment driver — GenLayer Studionet (chain 61999) only.
 *
 * Deploys contracts/pavvl.py with the GenLayer CLI's configured, unlocked
 * deployer account, waits for the deployment to finalize, and then proves that
 * the source stored on chain is the source in this repository by fetching it
 * back and comparing SHA-256 digests. Every run writes a manifest under
 * deployments/ so an outside reviewer can re-check the deployment without
 * trusting this machine.
 *
 * The script never reads, prints, or stores a private key: signing is done by
 * the CLI's own unlocked account, exactly as a maintainer would do by hand.
 *
 * Safety properties
 *   * refuses any network whose chain id is not 61999;
 *   * refuses source whose GenVM header is not the pinned, proven form;
 *   * refuses to claim success unless the on-chain source matches the file;
 *   * exits non-zero on any mismatch, timeout, or parse failure.
 *
 * Usage
 *   node scripts/deploy.mjs                 deploy, verify, write manifest
 *   node scripts/deploy.mjs --check         validate source + network only
 *   node scripts/deploy.mjs --record \
 *        --address 0x… --tx 0x…            verify an existing deployment
 *   node scripts/deploy.mjs --verify        re-verify the recorded deployment
 *
 * Environment
 *   GENLAYER_BIN   genlayer CLI executable (default: "genlayer")
 */

import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const CONTRACT = join(ROOT, "contracts", "pavvl.py");
const CONTRACT_REL = "contracts/pavvl.py";

const NETWORK = "studionet";
const CHAIN_ID = 61999;
const RPC = "https://studio.genlayer.com/api";
const EXPLORER = "https://explorer-studio.genlayer.com";
const GENVM = "v0.2.16";
const RUNNER = "py-genlayer:132536jbnxkd1axfxg5rpfr5b60cr11adm2y4r90hgn0l59qsp9w";
const EXPECTED_HEADER = `# ${GENVM}\n# { "Depends": "${RUNNER}" }\n`;

const MANIFEST = join(ROOT, "deployments", "studionet.json");
const PROOFS = join(ROOT, "deployments", "proofs");
const BIN = process.env.GENLAYER_BIN || "genlayer";

// The CLI prints more than a megabyte of consensus detail for a deploy. Cap it
// so a runaway process cannot exhaust memory, and trim what we persist.
const MAX_OUTPUT = 64 * 1024 * 1024;
const FINALIZE_TIMEOUT_MS = 20 * 60 * 1000;

const HEX64 = /0x[0-9a-fA-F]{64}/;
const HEX40 = /0x[0-9a-fA-F]{40}/;

function log(message) {
  process.stdout.write(`${message}\n`);
}

function fail(message, code = 1) {
  process.stderr.write(`\npavvl: ${message}\n`);
  process.exit(code);
}

function sha256(text) {
  return createHash("sha256").update(text, "utf8").digest("hex");
}

// The CLI re-emits the stored source through a formatted writer that appends
// blank lines and may use the host's line endings. Canonicalisation makes the
// comparison about the contract text, not the transport: CRLF becomes LF and
// trailing newlines collapse to exactly one.
function canonical(text) {
  return text.replace(/\r\n/g, "\n").replace(/\n+$/g, "\n");
}

function stripAnsi(text) {
  return text.replace(/\u001b\[[0-9;]*m/g, "");
}

function run(args, { allowFail = false, retries = 0 } = {}) {
  // Build one command string rather than an args array so the shell resolves
  // the platform wrapper (genlayer.cmd on Windows) without the DEP0190 warning.
  // Every argument here is a fixed literal or a value already validated as hex.
  const quote = (s) => (/[\s"&|<>^]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s);
  const command = [BIN, ...args].map(quote).join(" ");
  let result;
  for (let attempt = 0; ; attempt += 1) {
    result = spawnSync(command, {
      cwd: ROOT,
      encoding: "utf8",
      shell: true,
      maxBuffer: MAX_OUTPUT,
      windowsHide: true,
    });
    if (result.error) {
      fail(`could not run "${BIN}": ${result.error.message}`);
    }
    if ((result.status ?? 1) === 0 || attempt >= retries) break;
    sleepSync(2000);
  }
  const stdout = stripAnsi(result.stdout ?? "");
  const stderr = stripAnsi(result.stderr ?? "");
  if ((result.status ?? 1) !== 0 && !allowFail) {
    fail(`"${BIN} ${args.join(" ")}" exited ${result.status}\n${stdout}\n${stderr}`);
  }
  return { status: result.status ?? 1, stdout, stderr };
}

// Read-only CLI calls are safe to repeat: a transient crash or a dropped
// connection is retried. Writes are never retried, so a deploy cannot run twice.
function runRead(args, options = {}) {
  return run(args, { retries: 2, ...options });
}

function cliVersion() {
  return runRead(["--version"]).stdout.trim();
}

function assertStudionet() {
  const { stdout } = runRead(["network", "info"]);
  const chain = /chainId:\s*'?(\d+)'?/.exec(stdout);
  const rpc = /rpc:\s*'?([^'\n]+?)'?,?\s*\n/.exec(stdout);
  if (!chain || Number(chain[1]) !== CHAIN_ID) {
    fail(
      `refusing to deploy: the configured network is not Studionet ` +
        `(expected chain ${CHAIN_ID}, saw ${chain ? chain[1] : "none"}). ` +
        `Run: genlayer network set ${NETWORK}`,
    );
  }
  if (rpc && rpc[1].trim() !== RPC) {
    fail(`refusing to deploy: unexpected RPC ${rpc[1].trim()} (expected ${RPC})`);
  }
  log(`network      ${NETWORK} (chain ${CHAIN_ID}, ${rpc ? rpc[1].trim() : RPC})`);
}

function readSource() {
  const raw = readFileSync(CONTRACT, "utf8");
  if (!raw.startsWith(EXPECTED_HEADER)) {
    fail(
      `refusing to deploy: ${CONTRACT_REL} does not start with the pinned header\n` +
        `--- expected ---\n${EXPECTED_HEADER}--- found ---\n${raw.slice(0, 200)}`,
    );
  }
  const header = raw.slice(0, EXPECTED_HEADER.length);
  if (/:(test|latest)\b/.test(header)) {
    fail("refusing to deploy: runner alias :test/:latest is rejected in non-debug mode");
  }
  return {
    raw,
    bytes: Buffer.byteLength(raw, "utf8"),
    sha256: sha256(raw),
    canonical_sha256: sha256(canonical(raw)),
  };
}

function parseDeployOutput(stdout) {
  const tx =
    /Deployment Transaction Hash:[\s\n]+(0x[0-9a-fA-F]{64})/.exec(stdout)?.[1] ??
    /'Transaction Hash':\s*'(0x[0-9a-fA-F]{64})'/.exec(stdout)?.[1];
  const address =
    /'Contract Address':\s*'(0x[0-9a-fA-F]{40})'/.exec(stdout)?.[1] ??
    /contract_address:\s*'(0x[0-9a-fA-F]{40})'/.exec(stdout)?.[1] ??
    /recipient:\s*'(0x[0-9a-fA-F]{40})'/.exec(stdout)?.[1];
  if (!tx || !address) {
    fail("could not read the transaction hash and contract address from the deploy output");
  }
  return { tx, address };
}

function receiptSummary(tx) {
  const { stdout } = runRead([
    "receipt",
    tx,
    "--status",
    "ACCEPTED",
    "--retries",
    "1",
    "--interval",
    "1000",
    "--rpc",
    RPC,
  ]);
  const field = (name) => new RegExp(`${name}:\\s*'([^']*)'`).exec(stdout)?.[1] ?? null;
  const status = field("status_name");
  if (!status) fail(`could not read the status of ${tx}`);
  const pct = (name) => {
    const m = new RegExp(`${name}:\\s*'?([0-9]+)'?`).exec(stdout);
    return m ? Number(m[1]) : null;
  };
  return {
    status,
    result: field("result_name"),
    from: field("from_address") ?? field("origin_address") ?? field("sender"),
    recipient: field("recipient"),
    created_at: field("created_at"),
    tx_id: field("tx_id") ?? tx,
    rounds: pct("num_of_rounds"),
  };
}

function waitFinalized(tx) {
  const deadline = Date.now() + FINALIZE_TIMEOUT_MS;
  let last = "unknown";
  while (Date.now() < deadline) {
    const summary = receiptSummary(tx);
    last = summary.status;
    if (summary.status === "FINALIZED") return summary;
    if (["UNDETERMINED", "CANCELED", "LEADER_TIMEOUT", "VALIDATORS_TIMEOUT"].includes(summary.status)) {
      fail(`deployment ${tx} ended in ${summary.status}`);
    }
    if (summary.status === "READY_TO_FINALIZE") {
      log(`finalizing ${tx} ...`);
      run(["finalize", tx, "--rpc", RPC], { allowFail: true });
    } else {
      log(`waiting for finality (status: ${summary.status}) ...`);
    }
    sleepSync(8000);
  }
  fail(`deployment ${tx} did not finalize within ${FINALIZE_TIMEOUT_MS / 60000} minutes (last: ${last})`);
}

// Sleep without importing timers into a module that stays dependency free.
// Atomics.wait on a private buffer is the standard synchronous sleep.
function sleepSync(ms) {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
}

function fetchOnchainSource(address) {
  const { stdout } = runRead(["code", address, "--rpc", RPC]);
  const marker = "Result:\n";
  const at = stdout.indexOf(marker);
  if (at < 0) fail(`could not read the on-chain source for ${address}`);
  return stdout.slice(at + marker.length);
}

function buildManifest({ source, address, tx, summary, onchainSource }) {
  const onchainCanonical = sha256(canonical(onchainSource));
  const verified =
    onchainCanonical === source.sha256 && onchainCanonical === source.canonical_sha256;
  const now = new Date().toISOString();
  return {
    project: "Pavvl",
    network: NETWORK,
    chain_id: CHAIN_ID,
    rpc: RPC,
    explorer: EXPLORER,
    contract: CONTRACT_REL,
    contract_address: address,
    deployer: summary.from,
    transaction: tx,
    finalized: summary.status === "FINALIZED",
    result: summary.result,
    deployed_at: summary.created_at,
    rounds: summary.rounds,
    genvm: GENVM,
    runner: RUNNER,
    source: {
      path: CONTRACT_REL,
      bytes: source.bytes,
      sha256: source.sha256,
      canonical_sha256: source.canonical_sha256,
    },
    onchain_source_sha256: onchainCanonical,
    verified,
    verified_at: now,
    toolchain: {
      genlayer_cli: cliVersion(),
      node: process.version,
    },
    header: { genvm: GENVM, depends: RUNNER },
  };
}

function writeProofs(manifest, onchainSource) {
  mkdirSync(PROOFS, { recursive: true });
  const base = join(PROOFS, `studionet-${manifest.contract_address}`);
  writeFileSync(`${base}.json`, `${JSON.stringify(manifest, null, 2)}\n`);
  writeFileSync(`${base}.genlayer.py`, onchainSource);
  writeFileSync(
    `${base}.receipt.json`,
    `${JSON.stringify(
      {
        transaction: manifest.transaction,
        status: manifest.finalized ? "FINALIZED" : "NOT_FINALIZED",
        result: manifest.result,
        contract_address: manifest.contract_address,
        deployer: manifest.deployer,
        created_at: manifest.deployed_at,
        rounds: manifest.rounds,
      },
      null,
      2,
    )}\n`,
  );
  return base;
}

function assertVerified(manifest) {
  if (!manifest.verified) {
    fail(
      `on-chain source does not match ${CONTRACT_REL}\n` +
        `  local   canonical sha256: ${manifest.source.canonical_sha256}\n` +
        `  onchain canonical sha256: ${manifest.onchain_source_sha256}`,
    );
  }
}

function reportManifest(manifest, where) {
  log(`contract     ${manifest.contract_address}`);
  log(`transaction  ${manifest.transaction}`);
  log(`deployer     ${manifest.deployer}`);
  log(`status       ${manifest.finalized ? "FINALIZED" : manifest.status ?? "NOT_FINALIZED"}`);
  log(`result       ${manifest.result}`);
  log(`source sha256 ${manifest.source.sha256}`);
  log(`onchain sha256 ${manifest.onchain_source_sha256}`);
  log(`verified     ${manifest.verified}`);
  log(`manifest     ${where}`);
}

/** Deploy, wait for finality, verify the stored source, and write proofs. */
function deploy(source) {
  assertStudionet();
  log(`source       ${CONTRACT_REL} (${source.bytes} bytes, sha256 ${source.sha256})`);
  log(`deployer     ${runRead(["account"]).stdout.match(HEX40)?.[0] ?? "unknown"}`);
  log("deploying ...");
  const deployed = parseDeployOutput(
    run(["deploy", "--contract", CONTRACT_REL, "--rpc", RPC]).stdout,
  );
  log(`transaction  ${deployed.tx}`);
  log(`contract     ${deployed.address}`);
  const summary = waitFinalized(deployed.tx);
  const onchainSource = fetchOnchainSource(deployed.address);
  const manifest = buildManifest({ source, address: deployed.address, tx: deployed.tx, summary, onchainSource });
  const base = writeProofs(manifest, onchainSource);
  writeFileSync(MANIFEST, `${JSON.stringify(manifest, null, 2)}\n`);
  assertVerified(manifest);
  reportManifest(manifest, base);
}

/** Verify a known deployment and (re)write the manifest; never deploys. */
function record(source, address, tx) {
  if (!address) fail("--record requires --address 0x…");
  const summary = tx
    ? receiptSummary(tx)
    : { status: "FINALIZED", result: null, from: null, recipient: address, created_at: null, tx_id: null, rounds: null };
  const onchainSource = fetchOnchainSource(address);
  const manifest = buildManifest({ source, address, tx: tx ?? summary.tx_id, summary, onchainSource });
  const base = writeProofs(manifest, onchainSource);
  writeFileSync(MANIFEST, `${JSON.stringify(manifest, null, 2)}\n`);
  assertVerified(manifest);
  reportManifest(manifest, base);
}

/** Re-verify a recorded deployment against the live chain; never writes. */
function verifyRecorded(source, address) {
  const manifest = JSON.parse(readFileSync(MANIFEST, "utf8"));
  const target = address ?? manifest.contract_address;
  const onchainSource = fetchOnchainSource(target);
  const onchainCanonical = sha256(canonical(onchainSource));
  const matchesSource =
    onchainCanonical === source.sha256 && onchainCanonical === source.canonical_sha256;
  const matchesRecord = onchainCanonical === manifest.onchain_source_sha256;
  log(`contract      ${target}`);
  log(`transaction   ${manifest.transaction}`);
  log(`deployer      ${manifest.deployer}`);
  log(`status        ${manifest.finalized ? "FINALIZED" : manifest.status ?? "NOT_FINALIZED"}`);
  log(`result        ${manifest.result}`);
  log(`source sha256 ${source.sha256}`);
  log(`onchain sha256 ${onchainCanonical}`);
  log(`recorded sha256 ${manifest.onchain_source_sha256}`);
  log(`verified      ${matchesSource && matchesRecord}`);
  log(`manifest      ${MANIFEST} (unchanged)`);
  if (!matchesSource || !matchesRecord) {
    fail(
      `on-chain source does not match ${CONTRACT_REL} or the recorded manifest\n` +
        `  local   canonical sha256: ${source.canonical_sha256}\n` +
        `  onchain canonical sha256: ${onchainCanonical}\n` +
        `  recorded canonical sha256: ${manifest.onchain_source_sha256}`,
    );
  }
}

function parseArgs(argv) {
  const args = { mode: "deploy", address: null, tx: null };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--check") args.mode = "check";
    else if (a === "--record") args.mode = "record";
    else if (a === "--verify") args.mode = "verify";
    else if (a === "--address") args.address = argv[++i];
    else if (a === "--tx") args.tx = argv[++i];
    else if (a === "--help" || a === "-h") args.mode = "help";
    else fail(`unknown argument: ${a}`);
  }
  return args;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.mode === "help") {
    log("node scripts/deploy.mjs [--check | --record --address 0x… --tx 0x… | --verify]");
    return;
  }
  const source = readSource();
  if (args.mode === "check") {
    assertStudionet();
    log(`source       ${CONTRACT_REL} (${source.bytes} bytes, sha256 ${source.sha256})`);
    log("ok");
    return;
  }
  if (args.mode === "record") return record(source, args.address, args.tx);
  if (args.mode === "verify") return verifyRecorded(source, args.address);
  return deploy(source);
}

main();
