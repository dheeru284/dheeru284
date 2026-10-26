const { run, commands } = require("./engine"); const a = require("assert");
const ex = {"ideas":"/ideas cooking 20","script":"/script sleep 10min","seo":"/seo sleep | sleep, insomnia"};
for (const c of commands) { const r = run(ex[c] || `/${c} cooking`); a.ok(r.includes("educational purposes"), c); a.ok(!r.includes("undefined"), c); }
a.strictEqual((run("/ideas cooking 20").match(/^\| \d+ /gm) || []).length, 20);
a.ok(run("/seo sleep | sleep").includes("not financial, medical"));
console.log("all", commands.length, "commands ok");
