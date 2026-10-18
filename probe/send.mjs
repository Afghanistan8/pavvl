import { createClient, createAccount, studionet } from "genlayer-js";
import { studionet as chain } from "genlayer-js/chains";

const RPC = "https://studio.genlayer.com/api";
const key = process.argv[2];
const to = process.argv[3];
const method = process.argv[4];
const argsJson = process.argv[5] || "[]";
const valueStr = process.argv[6] || "0";

const account = createAccount(key);
const client = createClient({ chain, endpoint: RPC, account });
const args = JSON.parse(argsJson);
const value = BigInt(valueStr);
console.log("from", account.address, "value", String(value));
const hash = await client.writeContract({
  address: to,
  functionName: method,
  args,
  value,
});
console.log("tx", hash);
const r = await client.waitForTransactionReceipt({ hash, status: "FINALIZED", interval: 4000, retries: 60 });
console.log(JSON.stringify({ status: r.statusName ?? r.status, result: r.result }, null, 1).slice(0, 2000));
