#!/usr/bin/env node
const { run } = require("./engine");
const arg = process.argv.slice(2).join(" ");
if (arg) { console.log(run(arg)); process.exit(0); }
const rl = require("readline").createInterface({ input: process.stdin, output: process.stdout, prompt: "yt> " });
console.log(run("/help")); rl.prompt();
rl.on("line", l => { if (/^(exit|quit)$/.test(l.trim())) return rl.close(); console.log(run(l)); rl.prompt(); });
