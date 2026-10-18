# Deployment

Pavvl deploys to **GenLayer Studionet only** (chain ID `61999`). Both the contract
(`_guard_chain` in every write) and the deploy driver refuse any other chain.

## Prerequisites

- GenLayer CLI `0.39.2` on `PATH`, with a configured account that is **unlocked**
  and on Studionet:

  ```bash
  genlayer network set studionet
  genlayer network info        # must show chainId 61999
  genlayer account             # must show your deployer, status: unlocked
  ```

- Node.js 22+ (the driver uses only Node built-ins — no install step).
- The source at `contracts/pavvl.py` with the pinned header (see below).

The driver **never reads, prints, or stores a private key**. Signing is done by the
CLI's own unlocked account, exactly as a maintainer would do by hand.

## The pinned header (exact)

```python
# v0.2.16
# { "Depends": "py-genlayer:132536jbnxkd1axfxg5rpfr5b60cr11adm2y4r90hgn0l59qsp9w" }
```

Studionet's GenVM is v0.2.16, non-debug. It rejects `:test`/`:latest` runner
aliases and the Studio Next era header/import idiom. `scripts/deploy.mjs` refuses to
deploy a source that does not start with exactly these two lines. See
[`TOOLCHAIN.md`](../TOOLCHAIN.md) for the full set of proven pins.

## Commands

```bash
# Validate the source header and the configured network. No transaction.
node scripts/deploy.mjs --check

# Deploy, wait for the transaction to finalize, verify the on-chain source,
# and write the manifest. Uses the CLI's unlocked deployer.
node scripts/deploy.mjs

# Re-verify the recorded deployment against the current source.
node scripts/deploy.mjs --verify

# Verify a known deployment and (re)write the manifest without deploying.
node scripts/deploy.mjs --record --address 0x… --tx 0x…
```

Read-only CLI calls (`network info`, `account`, `receipt`, `code`, `--version`)
retry a couple of times on a transient crash. The **deploy** is never retried, so a
run cannot accidentally create two deployments.

## What a deploy does

1. Asserts the configured network is Studionet (chain 61999) and the RPC is the
   Studio RPC. Aborts otherwise.
2. Reads `contracts/pavvl.py`, asserts the pinned header, computes its SHA-256.
3. Runs `genlayer deploy`, then waits for the deployment transaction to reach
   `FINALIZED` (attempting `genlayer finalize` if it is `READY_TO_FINALIZE`).
4. Re-fetches the contract source with `genlayer code` and compares its SHA-256 to
   the repository source (canonicalised: CRLF→LF, trailing newlines collapsed).
   **If they differ, the script exits non-zero and refuses to claim success.**
5. Writes `deployments/studionet.json` and the raw proofs under
   `deployments/proofs/`.

## The manifest

`deployments/studionet.json` (and the identical per-deployment copy under
`deployments/proofs/`) is machine-written. Its fields:

| Field | Meaning |
|---|---|
| `network`, `chain_id`, `rpc`, `explorer` | where it lives |
| `contract`, `contract_address` | source path and deployed address |
| `deployer`, `transaction` | provenance |
| `finalized`, `result`, `deployed_at`, `rounds` | receipt summary |
| `genvm`, `runner`, `header` | the pinned runtime |
| `source.{bytes,sha256,canonical_sha256}` | the repository source |
| `onchain_source_sha256` | the source as stored on chain |
| `verified`, `verified_at` | whether the two hashes matched |
| `toolchain.{genlayer_cli,node}` | how it was produced |

Alongside the JSON, `deployments/proofs/studionet-<address>.genlayer.py` is the raw
on-chain source as fetched, and `.receipt.json` is a compact receipt summary. These
are the artefacts an outside reviewer can hash independently.

## Current deployment of record

| | |
|---|---|
| Contract | `0xAcBdea1B9CA3863355C1081Dd3c302b1aaDc2144` |
| Transaction | `0x9de6ae50d711348a0a4073efff407c388b2d0d67ce97f419e6743b6805c9ddb1` |
| Deployer | `0x4184bc5E5444F250767E8D33A49817A9B4FB0df3` |
| Source SHA-256 | `8fc10d6f8c62b3a62c02fa449e0ee5ec2ce56cf9cb0db73959767d3276d4e019` |
| Verified | yes — on-chain source hash equals the repository source hash |

## Reading a deployment from a client

Any client points at the address above. Nothing else is required: the contract
publishes `get_config` (network, chain, limits), `get_governance` (no authority),
and `get_actions` (what a wallet may do), and every read returns canonical JSON.
A client should refuse to sign on any chain but `61999` before building a
transaction; the contract refuses regardless.

## Post-deploy smoke check

```bash
genlayer call <address> get_config
genlayer call <address> get_governance     # expect empty owner/admin, no keys
genlayer call <address> get_stats          # expect all-zero counters
```
