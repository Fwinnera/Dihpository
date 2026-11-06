// Camp-group count of every map file: node mapgroups.mjs MAPDIR
import fs from 'node:fs';
import path from 'node:path';
import { WASI } from 'node:wasi';
const WASM = '/root/.cache/cambc/assets/9f6ac05ec0984f5d2d48b58cc7aeff66328c54b5a19d3462d0c5c439037ed99e/visualiser/assets/v3_0_0-DBS2ESWO.wasm';
const wasi = new WASI({ version: 'preview1', args: [], env: {} });
const inst = await WebAssembly.instantiate(await WebAssembly.compile(fs.readFileSync(WASM)), { wasi_snapshot_preview1: wasi.wasiImport });
wasi.initialize(inst);
const ex = inst.exports;
const mem = () => new DataView(ex.memory.buffer);
const outBuf = ex.Engine_Malloc(64), out = ex.Engine_Malloc(64);
const res = {};
for (const f of fs.readdirSync(process.argv[2]).filter(f => f.endsWith('.map26a')).sort()) {
  const bytes = fs.readFileSync(path.join(process.argv[2], f));
  const p = ex.Engine_Malloc(bytes.length);
  new Uint8Array(ex.memory.buffer, p, bytes.length).set(bytes);
  if (ex.Game_FromMapFileBytes(p, bytes.length, outBuf) !== 0) { res[f] = -1; continue; }
  const game = mem().getBigUint64(outBuf, true);
  const c = ex.Game_API_Map_GetNumCampGroups(game, out);
  res[f.replace('.map26a', '')] = c === 0 ? mem().getUint32(out, true) : -100 - c;
}
process.stdout.write(JSON.stringify(res));
