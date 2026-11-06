// Bush tiles of every map file: node mapbushes.mjs MAPDIR > bushes.json  ({map: [[x, y], ...]})
import fs from 'node:fs';
import path from 'node:path';
import { WASI } from 'node:wasi';
const WASM = '/root/.cache/cambc/assets/b4bd02e29fafd8626118cb898669aca185ed66f95bd8387cd05efc770a09cdc0/visualiser/assets/v2_0_0-hWOQ1R8f.wasm';
const dir = process.argv[2];
const wasi = new WASI({ version: 'preview1', args: [], env: {} });
const inst = await WebAssembly.instantiate(await WebAssembly.compile(fs.readFileSync(WASM)), { wasi_snapshot_preview1: wasi.wasiImport });
wasi.initialize(inst);
const ex = inst.exports;
const mem = () => new DataView(ex.memory.buffer);
const outBuf = ex.Engine_Malloc(64), out = ex.Engine_Malloc(64);
const result = {};
for (const f of fs.readdirSync(dir).filter(f => f.endsWith('.map26a')).sort()) {
  const bytes = fs.readFileSync(path.join(dir, f));
  const p = ex.Engine_Malloc(bytes.length);
  new Uint8Array(ex.memory.buffer, p, bytes.length).set(bytes);
  const code = ex.Game_FromMapFileBytes(p, bytes.length, outBuf);
  if (code !== 0) { result[f] = { error: code }; continue; }
  const game = mem().getBigUint64(outBuf, true);
  const tiles = [];
  for (let y = 0; y < 128; y++) {
    let any = false;
    for (let x = 0; x < 128; x++) {
      const c = ex.Game_GetBush(game, x, y, out);
      if (c !== 0) continue;
      any = true;
      if (mem().getUint32(out, true)) tiles.push([x, y]);
    }
    if (!any && y > 0) break;
  }
  result[f.replace('.map26a', '')] = tiles;
}
process.stdout.write(JSON.stringify(result));
