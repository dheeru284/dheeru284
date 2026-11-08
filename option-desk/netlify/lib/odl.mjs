// Loads site/lib.js (the browser maths library) in Node so the server, the auto-trader and the
// app use exactly the same pricing, expiry calendar and holiday list.
import './win-shim.mjs';
import '../../site/lib.js';

export const L = globalThis.window.ODL;
