# Pavvl toolchain pins — PROVEN ON STUDIONET 2026-10-17

Pavvl deploys to **GenLayer Studionet only** (chain ID `61999`).
Any other chain is refused by the deployment scripts and by the contract itself
(`_guard_chain` in every state-changing method).

## Pinned versions

| Tool | Pinned version | Notes |
|---|---|---|
| GenLayer CLI | 0.39.2 | `genlayer --version` |
| genlayer-py | 0.16.3 | pip package (test harness dependency only) |
| genlayer-test | 0.29.2 | Direct Mode harness (`gltest`) |
| genlayer-js | 1.1.8 | client library (deployment scripts / probes) |
| GenVM (Studionet) | v0.2.16 | from node log `genvm_common ... version v0.2.16-x86_64-linux-release` |
| Python | 3.12+ | contract tests and scripts |
| Node.js | 22+ | deployment scripts and probes |

## Contract header (EXACT — proven on Studionet)

```python
# v0.2.16
# { "Depends": "py-genlayer:132536jbnxkd1axfxg5rpfr5b60cr11adm2y4r90hgn0l59qsp9w" }
```

Why this exact form:

- Studionet's GenVM is **v0.2.16, non-debug**. It rejects `:test`/`:latest`
  runner aliases (`:test/:latest runner used in non-debug mode, this is not
  allowed` → `invalid_contract`), and it rejects the older Studio Next-era header
  form (`py-genlayer:5jycge…`, with no version line) with `invalid_contract` —
  verified against this network.
- The version MUST be its own `# v0.2.16` first line. Any other placement
  (`# v0.2.16 {...}` on one line, JSON-only) yields `invalid_contract`.
- Runner `132536…` pairs with std `0mmsw09…` and uses the
  `genlayer.gl._internal.runner` entrypoint.

## Contract import idiom (EXACT — proven on Studionet)

```python
import genlayer.gl as gl
from genlayer.py.types import Address, u256
from genlayer.gl._internal.eth import evm_contract_interface as eth_iface
from genlayer.py.storage import TreeMap
```

- `import genlayer as gl` does NOT exist in this std (no `Contract` attr).
- `from genlayer.chain import Account` does NOT exist.
- `from genlayer.types import ...` does NOT exist (it's `genlayer.py.types`).
- `from genlayer import ...` top-level form exists but its `gl` proxy breaks
  cloudpickle inside `run_nondet` closures. Do not use it.

## Proven patterns (each verified by a FINALIZED Studionet tx)

| Capability | Pattern | Proof |
|---|---|---|
| Chain gate | `int(gl.message.chain_id) == 61999` | `get_chain` → `{"chain_id": 61999}` |
| Payable + value | `@gl.public.write.payable`, `gl.message.value` | deposit receipt |
| Nondet text | `gl.nondet.exec_prompt(p, response_format="json")` returns **dict**; leader must `json.dumps` it to str | `nd_json_str` AGREE |
| Nondet image | `images=[bytes]`, leader returns `json.dumps(...)` str | `nd_img` AGREE, `{"ok":true}` |
| Consensus | `gl.vm.run_nondet(leader, validator)`; validator checks `isinstance(result, gl.vm.Return)` | MAJORITY_AGREE |
| Transfer | `_EthPayee(Address(raw_bytes)).emit_transfer(value=u256(n))` via `genlayer.gl._internal.eth.evm_contract_interface`; recipient as `bytes`, NOT `Address` object | `p-sent`, balances moved |
| Balance | contract holds native GEN via `account send` or payable; `p` fails `inbalance` when unfunded | `inbalance` → `p-sent` |

## Transfer rules

- The recipient MUST be constructed as `Address(raw_bytes)` where `raw_bytes`
  is 20 bytes. Passing an `Address` object into a method and re-wrapping it
  fails (`cannot convert 'Address' object to bytes`). Take `to: bytes`.
- `_Payee` MUST use the internal `EthSend`-backed interface
  (`genlayer.gl._internal.eth.evm_contract_interface`). The public
  `gl.evm.contract_interface` emits `PostMessage` to a contract account and
  fails with `exit_code 1` for EOA recipients on Studionet.
- `emit_transfer` default `on="finalized"` works for withdraw payouts.

## Endpoints

- RPC: `https://studio.genlayer.com/api`
- Main contract: `0xb7278A61aa25c888815aFC32Ad3cC52fF24fE575`
- Explorer: `https://explorer-studio.genlayer.com`
- Faucet/funding: `genlayer account send <to> <wei>` (amount in WEI, not GEN)
