// Drive one live case through the deployed Pavvl contract on Studionet, so a
// reviewer can inspect real data rather than a description of it: a criteria
// digest the respondent accepted, evidence stored on chain with a digest the
// contract computed, and a finding the validators agreed on.
//
// The signing keys are read from the GenLayer CLI's OS-keychain cache, in
// memory. No key is written to disk, printed, or stored.
//
//   node probe/pavvl_demo_case.mjs
//   PAVVL_CASE_TITLE="..." node probe/pavvl_demo_case.mjs
//
// Writes are made by two wallets: the claimant opens and funds the case, the
// respondent accepts its frozen terms. Both file evidence and mark it
// complete; the claimant then asks for the assessment. The script resumes: run
// it again and it continues from whatever the chain already holds.

import { createRequire } from "node:module";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "..");

const CLI_DIR = "C:/Users/emman/AppData/Roaming/npm/node_modules/genlayer/";
const SDK = "file:///C:/Users/emman/AppData/Roaming/npm/node_modules/genlayer/node_modules/genlayer-js/dist/index.js";
const CHAINS = "file:///C:/Users/emman/AppData/Roaming/npm/node_modules/genlayer/node_modules/genlayer-js/dist/chains/index.js";

const require = createRequire(CLI_DIR);
const keytar = require("keytar");
const { createClient, createAccount } = await import(SDK);
const { studionet: chain } = await import(CHAINS);

const RPC = "https://studio.genlayer.com/api";
const CONTRACT = process.env.PAVVL_CONTRACT || "0x6173BD4FC60273bDD03a251B0C302cdFE5cD80E7";
const CLAIMANT = process.env.PAVVL_CLAIMANT_ACCOUNT || "deployer";
const RESPONDENT = process.env.PAVVL_RESPONDENT_ACCOUNT || "hatchmade-reviewer";
const TITLE = process.env.PAVVL_CASE_TITLE || "Delivery of 100 widgets to Depot B";
const FINALIZE = process.argv.includes("--finalize");
const GEN = 10n ** 18n;
const HELD = 1n * GEN;

function log(line) {
  process.stdout.write(line + "\n");
}

async function accountFor(name) {
  const pk = await keytar.getPassword("genlayer-cli", `account:${name}`);
  if (!pk) throw new Error(`no cached key for the ${name} account`);
  const account = createAccount(pk.startsWith("0x") ? pk : `0x${pk}`);
  log(`  ${name} -> ${account.address}`);
  return account;
}

function clientFor(account) {
  return createClient({ chain, endpoint: RPC, account });
}

function asJson(value) {
  if (typeof value !== "string") return value;
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

async function read(client, functionName, args = []) {
  return asJson(await client.readContract({ address: CONTRACT, functionName, args }));
}

async function write(client, functionName, args = [], value = 0n, label = "") {
  const hash = await client.writeContract({ address: CONTRACT, functionName, args, value });
  const receipt = await client.waitForTransactionReceipt({
    hash,
    status: "FINALIZED",
    interval: 4000,
    retries: 450,
  });
  log(`  ${label || functionName}: ${receipt.statusName ?? receipt.status} ${hash}`);
  return { hash, receipt };
}

const claimant = await accountFor(CLAIMANT);
const respondent = await accountFor(RESPONDENT);
const cClient = clientFor(claimant);
const rClient = clientFor(respondent);

log(`contract  ${CONTRACT}`);
log(`rpc       ${RPC}`);

if (FINALIZE) {
  // Anyone may finalize once the challenge window has closed, so this is a
  // separate, idempotent step: it finalizes whatever is standing and ready.
  const all = (await read(cClient, "list_cases", [0, 50]))?.cases || [];
  for (const row of all) {
    const cid = row.case_id;
    const c = await read(cClient, "get_case", [cid]);
    if (c.state !== "DETERMINED") {
      log(`  ${cid}: state ${c.state}, nothing to finalize`);
      continue;
    }
    const decision = await read(cClient, "get_decision", [c.standing]);
    const ends = decision.challenge_window_ends;
    if (ends && new Date(ends) > new Date()) {
      log(`  ${cid}: ${decision.overall}, still challengeable until ${ends}`);
      continue;
    }
    const done = await write(cClient, "finalize", [cid], 0n, `finalize ${cid}`);
    const after = await read(cClient, "get_case", [cid]);
    log(`  ${cid}: state ${after.state} settlement ${JSON.stringify(after.settlement)}`);
    const receipt = await read(cClient, "get_receipt", [cid]);
    if (receipt && receipt.digest) log(`  ${cid}: receipt digest ${receipt.digest}`);
    void done;
  }
  process.exit(0);
}

const terms = {
  title: TITLE,
  subject_kind: "DELIVERY_MADE",
  subject_ref: "order-42",
  time_zone: "UTC",
  claim: "The supplier delivered 100 widgets to Depot B on 2026-10-10",
  criteria: [{ text: "100 widgets were delivered to Depot B on 2026-10-10", needs_independent: false }],
  allowed: ["PHOTO", "TEXT_DOCUMENT"],
  respondent: respondent.address,
  held_sum_wei: HELD.toString(),
  funder: "CLAIMANT",
  challenge_bond_wei: (GEN / 10n).toString(),
  evidence_period_seconds: 86400,
  challenge_window_seconds: 3600,
};

log("\n1. the case");
let cases = (await read(cClient, "list_cases", [0, 50]))?.cases || [];
let found = cases.find((c) => c.title === terms.title && c.claimant === claimant.address);
if (!found) {
  await write(cClient, "open_case", [JSON.stringify(terms)], 0n, "open_case");
  cases = (await read(cClient, "list_cases", [0, 50]))?.cases || [];
  found = cases.find((c) => c.title === terms.title && c.claimant === claimant.address);
}
if (!found) throw new Error("the case was not created");
const cid = found.case_id;
let c = await read(cClient, "get_case", [cid]);
log(`  case ${cid} state ${c.state} accepted_version ${c.accepted_version} funded ${c.funded_wei}`);

log("\n2. the respondent accepts that exact version of the terms");
const frozen = await read(cClient, "get_terms", [cid, 1]);
log(`  terms digest ${frozen.digest}`);
if (!c.accepted_version) {
  await write(rClient, "accept_case", [cid, frozen.digest], 0n, "accept_case");
  c = await read(cClient, "get_case", [cid]);
}

log("\n3. the claimant deposits the held sum");
if (c.state === "DRAFT" && c.funded_wei === "0") {
  await write(cClient, "fund_case", [cid], HELD, "fund_case");
  c = await read(cClient, "get_case", [cid]);
}
log(`  state ${c.state} funded ${c.funded_wei}`);

if (c.state === "OPEN") {
  log("\n4. both parties file evidence");
  if (!(c.evidence_ids || []).length) {
    const photo = readFileSync(resolve(HERE, "pavvl_demo_evidence.png"));
    await write(
      cClient,
      "submit_image",
      [cid, JSON.stringify({ kind: "PHOTO" }), new Uint8Array(photo)],
      0n,
      "submit_image (claimant)",
    );
    await write(
      cClient,
      "submit_text",
      [
        cid,
        JSON.stringify({ kind: "TEXT_DOCUMENT", doc_type: "DELIVERY_NOTE", title: "Delivery note 42" }),
        "Delivery note order 42: 100 widgets received at Depot B on 2026-10-10. Counted 10 rows of 10.",
      ],
      0n,
      "submit_text (claimant)",
    );
    await write(
      rClient,
      "submit_text",
      [
        cid,
        JSON.stringify({ kind: "TEXT_DOCUMENT", doc_type: "DELIVERY_NOTE", title: "Receipt confirmation 42" }),
        "Depot B confirms receipt of 100 widgets against order 42 on 2026-10-10.",
      ],
      0n,
      "submit_text (respondent)",
    );
    c = await read(cClient, "get_case", [cid]);
  }

  log("\n5. both parties mark their evidence complete");
  if (!c.ready?.CLAIMANT) await write(cClient, "mark_ready", [cid], 0n, "mark_ready (claimant)");
  if (!c.ready?.RESPONDENT) await write(rClient, "mark_ready", [cid], 0n, "mark_ready (respondent)");
  c = await read(cClient, "get_case", [cid]);

  log("\n6. the claimant asks for the assessment");
  if (!c.standing) {
    await write(cClient, "request_assessment", [cid], 0n, "request_assessment");
    c = await read(cClient, "get_case", [cid]);
  } else {
    log(`  already assessed: ${c.standing}`);
  }
}

log("\n7. what the chain now holds");
log(`  state   ${c.state}`);
const decision = c.standing ? await read(cClient, "get_decision", [c.standing]) : null;
if (decision && decision.decision_id) {
  log(`  finding ${decision.overall}`);
  for (const row of decision.criteria || []) {
    log(`    ${row.id} ${row.finding} (floors: ${(row.floors || []).join(",") || "none"})`);
  }
  log(`  seen by the validators ${JSON.stringify(decision.seen_ids)}`);
  log(`  challenge window ends ${decision.challenge_window_ends}`);
}
const receipt = await read(cClient, "get_receipt", [cid]);
if (receipt && receipt.digest) log(`  receipt digest ${receipt.digest}`);

const record = {
  contract: CONTRACT,
  rpc: RPC,
  claimant: claimant.address,
  respondent: respondent.address,
  case_id: cid,
  terms_digest: frozen.digest,
  terms,
  state: c.state,
  decision,
  receipt,
};
const out = resolve(REPO, "deployments", `demo-case-${cid}.json`);
writeFileSync(out, JSON.stringify(record, null, 2) + "\n", "utf8");
log(`\nwrote ${out}`);
