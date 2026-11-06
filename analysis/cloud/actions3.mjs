// Action stream: one JSON line per consumed input: [round, actor index, code, fx, fy, tx, ty, h116, hp changes].
//   node actions.mjs REPLAY
import fs from 'node:fs';
import { WASI } from 'node:wasi';
const WASM = '/root/.cache/cambc/assets/9f6ac05ec0984f5d2d48b58cc7aeff66328c54b5a19d3462d0c5c439037ed99e/visualiser/assets/v3_0_0-DBS2ESWO.wasm';
const file = process.argv[2];
const wasi = new WASI({ version: 'preview1', args: [], env: {} });
const inst = await WebAssembly.instantiate(await WebAssembly.compile(fs.readFileSync(WASM)), { wasi_snapshot_preview1: wasi.wasiImport });
wasi.initialize(inst);
const ex = inst.exports;
const mem = () => new DataView(ex.memory.buffer);
const outBuf = ex.Engine_Malloc(32), args = ex.Engine_Malloc(128);
function check(code) { if (code !== 0) throw new Error(`engine error ${code}`); }
const bytes = fs.readFileSync(file);
const p = ex.Engine_Malloc(bytes.length);
new Uint8Array(ex.memory.buffer, p, bytes.length).set(bytes);
check(ex.Game_FromReplayFileBytes(p, bytes.length, outBuf));
const game = mem().getBigUint64(outBuf, true);
check(ex.Game_Visualiser_Timeline_GetMain(game, outBuf));
const timeline = mem().getBigUint64(outBuf, true);
check(ex.Game_Visualiser_Timeline_Info(game, timeline, args, args + 8, args + 16));
const size = mem().getUint32(args, true);
const snap = ex.Engine_Malloc(ex.Game_Visualiser_TimelineSnapshotSize());
check(ex.Game_Visualiser_Timeline_Seek(game, timeline, 0, 0));
let prevInput = -1, prevHp = [], teamsShown = false;
const s32 = (d, o) => d.getInt32(snap + o, true);
// The timeline's size counts inputs; ReplayNext advances one engine step (many per input), so run until the
// last input has been consumed or the engine refuses to step.
for (let pos = 0; ; pos += 1) {
  if (pos > 0 && ex.Game_Visualiser_Timeline_ReplayNext(game, 1) !== 0) break;
  check(ex.Game_Visualiser_ReadTimelineState(game, snap));
  const d = mem();
  const extra = d.getUint32(snap + 4, true) === 42840 ? 168 : 0;
  const n = d.getUint32(snap + 172, true);
  const hp = [];
  for (let k = 0; k < n && k < 16; k++) hp.push(Math.round(d.getFloat32(snap + 196 + k * (252 + extra) + 24, true)));
  if (!teamsShown && n > 0) {
    const tm = [];
    for (let k = 0; k < n && k < 16; k++) { const b = snap + 196 + k * (252 + extra); tm.push([d.getUint32(b + 4, true), d.getUint32(b + 8, true), d.getUint32(b + 12, true)]); }
    process.stdout.write(JSON.stringify({ teams: tm }) + '\n');
    teamsShown = true;
  }
  const input = d.getUint32(snap + 56, true);
  const changes = [];
  hp.forEach((v, k) => { if (prevHp[k] !== undefined && v !== prevHp[k]) changes.push([k, v - prevHp[k]]); });
  if (input !== prevInput || changes.length) {
    process.stdout.write(JSON.stringify([d.getUint32(snap + 8, true), s32(d, 60), d.getUint32(snap + 68, true),
      s32(d, 80), s32(d, 84), s32(d, 88), s32(d, 92), d.getUint32(snap + 116, true), input !== prevInput ? 1 : 0, changes]) + '\n');
  }
  prevInput = input; prevHp = hp;
  if (pos > 400000000) break;
}
