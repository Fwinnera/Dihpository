// Replay reader: runs the visualiser's engine (wasm, engine 2.0.0) under Node and prints one JSON line per
// round with every champion's team, type, position, health, alive flag, gold and gems.
//   node read.mjs REPLAY_FILE [STEP]
// REPLAY_FILE is the inner replay (replay.repl26a from the bundle zip). Layout from the visualiser's
// timeline snapshot parser (PanelChrome `mr`, ABI 40152/42840).
import fs from 'node:fs';
import { WASI } from 'node:wasi';

const WASM = '/root/.cache/cambc/assets/9f6ac05ec0984f5d2d48b58cc7aeff66328c54b5a19d3462d0c5c439037ed99e/visualiser/assets/v3_0_0-DBS2ESWO.wasm';
const file = process.argv[2];
const wasi = new WASI({ version: 'preview1', args: [], env: {} });
const mod = await WebAssembly.compile(fs.readFileSync(WASM));
const inst = await WebAssembly.instantiate(mod, { wasi_snapshot_preview1: wasi.wasiImport });
wasi.initialize(inst);
const ex = inst.exports;
const mem = () => new DataView(ex.memory.buffer);
const outBuf = ex.Engine_Malloc(32);
const args = ex.Engine_Malloc(128);

function cstr(p) {
  const b = new Uint8Array(ex.memory.buffer);
  let s = '';
  for (let i = p; b[i]; i++) s += String.fromCharCode(b[i]);
  return s;
}
function check(code) {
  if (code !== 0) throw new Error(`engine error ${code}: ${cstr(ex.GetLastErrorMsg())}`);
}

const bytes = fs.readFileSync(file);
const p = ex.Engine_Malloc(bytes.length);
new Uint8Array(ex.memory.buffer, p, bytes.length).set(bytes);
check(ex.Game_FromReplayFileBytes(p, bytes.length, outBuf));
const game = mem().getBigUint64(outBuf, true);
ex.Engine_Free(p);

check(ex.Game_Visualiser_Timeline_GetMain(game, outBuf));
const timeline = mem().getBigUint64(outBuf, true);
check(ex.Game_Visualiser_Timeline_Info(game, timeline, args, args + 8, args + 16));
const size = mem().getUint32(args, true);
const snapSize = ex.Game_Visualiser_TimelineSnapshotSize();
const snap = ex.Engine_Malloc(snapSize);

function read() {
  check(ex.Game_Visualiser_ReadTimelineState(game, snap));
  const d = mem();
  const t = snap;
  const abi = d.getUint32(t + 4, true);
  if (abi !== 40152 && abi !== 42840) throw new Error(`unsupported snapshot ABI ${abi}`);
  const extra = abi === 42840 ? 168 : 0;
  const u = (o) => d.getUint32(t + o, true);
  const s = (o) => d.getInt32(t + o, true);
  const f = (o) => d.getFloat32(t + o, true);
  const n = u(172);
  const champs = [];
  for (let k = 0; k < n && k < 16; k++) {
    const b = 196 + k * (252 + extra);
    const x = s(b + 16), y = s(b + 20);
    champs.push([u(b + 4), u(b + 8), u(b + 12), x, y, Math.round(f(b + 24)), Math.round(f(b + 28)),
                 u(b + 32), u(b + 36), u(b + 40), u(b + 44)]);
  }
  const ncamps = u(176);
  const campBase = 4228 + (abi === 42840 ? 2688 : 0);
  const camps = [];
  for (let k = 0; k < ncamps && k < 500; k++) {
    const b = campBase + k * 28;
    camps.push([u(b + 4), s(b + 16), s(b + 20), f(b + 24)]);
  }
  return { round: u(8), input: u(56), phase: u(24), champs, camps };
}

const mode = process.argv[3] || 'next';
let last = -1;
const prevCamp = new Map();
const withCamps = process.argv.includes('camps');
const t0 = Date.now();
if (process.argv[4] === 'cp') check(ex.Game_Runner_SetCheckpointsEnabled(game, 1));
check(ex.Game_Visualiser_Timeline_Seek(game, timeline, 0, 0));
for (let pos = 0; pos < size; pos += 1) {
  if (mode === 'seek') check(ex.Game_Visualiser_Timeline_Seek(game, timeline, pos, 0));
  else if (pos > 0) check(ex.Game_Visualiser_Timeline_ReplayNext(game, 1));
  const st = read();
  if (st.round !== last) {
    last = st.round;
    // champs: [index, team, type, x, y, hp, maxhp, alive, gold, gems, kills]
    // d: camps that lost health since the previous round: [index, x, y, health lost]
    const d = [];
    for (const c of st.camps) {
      const before = prevCamp.get(c[0]);
      if (before !== undefined && c[3] < before - 0.01) d.push([c[0], c[1], c[2], Math.round(before - c[3])]);
      prevCamp.set(c[0], c[3]);
    }
    process.stdout.write(JSON.stringify(withCamps ? { r: st.round, c: st.champs, d } : { r: st.round, c: st.champs }) + '\n');
  }
}
process.stderr.write(`positions ${size}, ${(Date.now() - t0) / 1000}s\n`);
