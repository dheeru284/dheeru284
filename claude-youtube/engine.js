// Claude YouTube — offline, template-driven faceless channel manager. Zero deps, free.
(function (root) {
  const DISCLAIMER = "> _This is AI-generated content for educational purposes._";
  const SENSITIVE = /(financ|invest|stock|crypto|money|tax|health|medic|diet|fitness|weight|legal|law|sleep|supplement|mental|therapy|drug|loan|debt|insurance)/i;
  const cap = s => s.replace(/\b\w/g, c => c.toUpperCase());
  const pick = (arr, i) => arr[i % arr.length];
  const hash = s => [...s].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7);
  const note = t => SENSITIVE.test(t) ? "\n> ⚠️ Educational content only — not financial, medical, or legal advice. Consult a qualified professional.\n" : "";
  const out = (title, body, topic = "") => `# ${title}\n${note(topic)}\n${body.trim()}\n\n${DISCLAIMER}\n`;

  const ANGLES = ["Hidden truth about", "Why nobody talks about", "I tested", "The dark side of", "What happens when you", "The 1% secret of", "Beginner mistakes in", "Science behind", "History of", "Future of", "Myths about", "Cheap vs expensive", "Ranking every", "Day-by-day experiment:", "Top 7 tools for"];
  const EMOTIONS = ["shocked", "curious", "excited", "skeptical", "amazed"];
  const COLORS = [["yellow", "black"], ["red", "white"], ["neon green", "dark navy"], ["orange", "deep blue"], ["white", "crimson"]];

  const cmds = {
    "channel-audit"([niche = "productivity"]) {
      const h = hash(niche), score = 5 + (h % 5);
      const comp = ["Authority explainer channel (long-form, high polish)", "Listicle/top-10 channel (fast cuts, stock footage)", "Storytelling/documentary channel", "Shorts-first viral clip channel", "Tutorial/screen-recording channel"];
      return out(`Channel Audit: ${cap(niche)}`, `
## Niche Opportunity Score: **${score}/10**
- Demand: evergreen search interest + Shorts discovery
- Competition: ${score > 7 ? "moderate — room for new faceless voices" : "high — needs a sharp sub-niche"}
- Monetization: AdSense, affiliates, digital products, sponsorships

## Top 5 Competitor Archetypes
${comp.map((c, i) => `${i + 1}. **${c}** — weakness: ${pick(["inconsistent uploads", "weak hooks", "outdated info", "no Shorts strategy", "generic thumbnails"], i)}`).join("\n")}

## Content Gaps
- Data-backed deep dives (most channels repeat surface-level tips)
- "Tested for 30 days" experiments told via screen recordings/visual logs
- Beginner roadmaps updated for ${new Date().getFullYear()}
- Myth-busting with sources on screen

## Audience Demand Signals
- Search: "how to ${niche}", "best ${niche} tools", "${niche} for beginners"
- Comments on competitors asking for step-by-step/templates

## 3 Content Angles
1. **The Explainer** — "${cap(niche)} explained in 8 minutes" (evergreen SEO)
2. **The Experiment** — narrated visual logs of real tests
3. **The Contrarian** — "Everything you know about ${niche} is wrong"

## Validate for free
- YouTube search autocomplete, Google Trends, competitor "Sort by Popular", vidIQ/TubeBuddy free tiers`, niche);
    },

    ideas([niche = "productivity", count = "10"]) {
      const n = Math.min(parseInt(count) || 10, 100);
      const rows = Array.from({ length: n }, (_, i) => {
        const a = pick(ANGLES, i + hash(niche));
        const t = `${a} ${niche}${i % 3 === 0 ? ` (${pick([3, 5, 7, 10], i)} things)` : ""}`;
        return `| ${i + 1} | ${cap(t)} | "${pick(["Stop scrolling — this changes everything about", "Nobody warned me about", "In 60 seconds you'll see why", "This one fact about", "Everyone gets this wrong about"], i)} ${niche}." | ${pick(["Curiosity", "How-to", "Listicle", "Contrarian", "Story"], i)} | ${pick(EMOTIONS, i)} face/object + ${pick(COLORS, i).join("/")} text "${pick(["NOBODY KNOWS", "STOP THIS", "IT WORKED?!", "THE TRUTH", "DON'T DO IT"], i)}" |`;
      });
      return out(`${n} Viral Video Ideas: ${cap(niche)}`, `| # | Title | Hook | Angle | Thumbnail Concept |\n|---|---|---|---|---|\n${rows.join("\n")}`, niche);
    },

    hook([...t]) {
      const topic = t.join(" ") || "this topic";
      return out(`5 Hooks: ${topic}`, `
1. **Pattern interrupt:** *[hard cut + sound hit]* "Stop. Everything about ${topic} you learned is backwards."
2. **Curiosity gap:** "There's one detail about ${topic} that 99% of people miss — and it's the only one that matters."
3. **Bold statement:** "${cap(topic)} isn't hard. It's just been explained badly. Until now."
4. **Stakes:** "Get ${topic} wrong and you lose months. Get it right in the next 8 minutes."
5. **Visual question:** *[on-screen text: "WHY?"]* "Why does ${topic} work for some people and fail for everyone else?"

**Tip:** Show the payoff visual in the first 2 seconds; keep hooks under 8s (~20 words).`, topic);
    },

    script(args) {
      const lens = { "60s": 60, "3min": 180, "8min": 480, "10min": 600 };
      let len = args[args.length - 1] in lens ? args.pop() : "8min";
      const topic = args.join(" ") || "this topic", total = lens[len];
      const nSec = total <= 60 ? 2 : total <= 180 ? 3 : total <= 480 ? 5 : 6;
      const per = Math.floor((total - 20 - 20) / nSec);
      const fmt = s => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
      let t = 20, secs = [];
      for (let i = 0; i < nSec; i++) {
        secs.push(`[${fmt(t)}] SECTION ${i + 1}: ${pick(["The core idea", "The common mistake", "The proof", "The method", "The advanced move", "The real-world example"], i)}
VO: Here's what most explanations skip about ${topic}. ${pick(["The basics look simple, but the details decide everything.", "The most common approach actually works against itself.", "The data tells a surprising story.", "It breaks down into three repeatable steps.", "Experts quietly do one thing differently.", "Picture this scenario playing out in real life."], i)}
B-ROLL: ${pick(["stock footage of hands working, close-up", "animated text infographic", "screen recording walkthrough", "timelapse city / nature", "split-screen comparison", "kinetic typography"], i)}
ON-SCREEN TEXT: "${pick(["KEY POINT", "MISTAKE #1", "THE DATA", "STEP-BY-STEP", "PRO MOVE", "REAL EXAMPLE"], i)}"
PATTERN INTERRUPT: ${pick(["zoom punch + whoosh SFX", "sudden silence then question on screen", "meme-style freeze frame", "color shift + counter graphic"], i)}`);
        t += per;
      }
      return out(`Script: ${topic} (${len})`, "```text\n" + `[0:00-0:08] HOOK
VO: Stop. There's one thing about ${topic} nobody explains properly — and it changes everything.
B-ROLL: fast-cut montage, bold text "${topic.toUpperCase()}"

[0:08-0:20] INTRO
VO: In the next ${len.replace("min", " minutes").replace("s", " seconds")}, this video breaks down ${topic} step by step — what works, what doesn't, and the one move that makes the difference. Stay to the end for the biggest takeaway.
B-ROLL: title card + preview of later sections

${secs.join("\n\n")}

[${fmt(total - 20)}-${fmt(total)}] CTA
VO: That's ${topic}, simplified. If this saved you time, subscribe — the next video goes even deeper. Drop your biggest question in the comments.
B-ROLL: end screen with next-video + subscribe element
` + "```\n\n**Production:** free AI voiceover (e.g. TTS tools), stock footage from Pexels/Pixabay, edit in CapCut/DaVinci Resolve.", topic);
    },

    title([...a]) {
      const [topic, kw = topic] = a.join(" ").split("|").map(s => s.trim());
      const T = topic || "this topic", K = (kw || T).split(",")[0].trim();
      const list = [
        `I Tried ${cap(T)} for 30 Days — This Happened (clickbait)`,
        `${cap(K)} Explained: Complete Beginner's Guide (educational)`,
        `Everyone Is Talking About ${cap(T)} in ${new Date().getFullYear()} — Here's Why (trending)`,
        `7 ${cap(K)} Mistakes Killing Your Results`,
        `${cap(K)}: The 5-Step Method That Actually Works`,
        `Why ${cap(T)} Fails for 90% of People`,
        `The Truth About ${cap(K)} Nobody Tells You`,
        `${cap(K)} in 10 Minutes (No Fluff)`,
        `3 ${cap(K)} Secrets Experts Won't Share`,
        `Stop Doing ${cap(T)} Like This`];
      return out(`10 Titles: ${T}`, list.map((x, i) => `${i + 1}. ${x}`).join("\n") + "\n\n**SEO:** keep under 60 chars, front-load the keyword, pair with thumbnail text (don't repeat it).", T);
    },

    thumbnail([...t]) {
      const topic = t.join(" ") || "this topic";
      return out(`Thumbnail Prompts: ${topic}`, [0, 1, 2].map(i => {
        const [c1, c2] = pick(COLORS, i);
        return `### Prompt ${i + 1}\n\`\`\`text\nYouTube thumbnail, 16:9, ${pick(["close-up of a " + pick(EMOTIONS, i) + " person (no real likeness), wide eyes", "single dramatic object representing " + topic + " on a glowing pedestal", "split-screen before vs after of " + topic], i)}, bold ${c1} text overlay "${pick(["NOBODY KNOWS", "STOP THIS", "IT WORKS?!"], i)}", high contrast ${c1} on ${c2} background, rule of thirds, subject left, text right, red arrow pointing to focal point, cinematic lighting, ultra sharp, vibrant, --ar 16:9\n\`\`\``;
      }).join("\n\n") + "\n\n**Free tools:** Bing Image Creator, Leonardo free tier, Canva for text overlay.", topic);
    },

    seo([...a]) {
      const [topic, kw = topic] = a.join(" ").split("|").map(s => s.trim());
      const T = topic || "this topic";
      const kws = (kw || T).split(/,\s*/);
      const main = kws[0];
      const tags = [main, `${main} tutorial`, `${main} for beginners`, `${main} ${new Date().getFullYear()}`, `how to ${main}`, `best ${main}`, `${main} tips`, `${main} explained`, `${main} guide`, `${main} mistakes`, `${main} step by step`, `${T}`, `${main} hacks`, `learn ${main}`, `${main} faceless`].slice(0, 15);
      return out(`SEO Pack: ${T}`, `
## Description
\`\`\`text
${cap(main)} explained simply: the exact steps behind ${T}, without the fluff.
Learn what works, what fails, and the one move most people miss.

In this video, we break down ${T} from the ground up. Whether you're just starting or stuck at a plateau, this guide covers the core principles of ${main}, the most common mistakes, and a practical step-by-step method you can apply today. Every section is designed to be clear, visual, and actionable, so you can follow along even if you're a complete beginner.

You'll learn:
• The core idea behind ${main}
• The #1 mistake that slows most people down
• A repeatable method that works
• Advanced tips to level up faster

⏱️ Chapters
0:00 Hook
0:08 Intro
0:20 The core idea
2:00 The common mistake
4:00 The method
6:30 Advanced tips
7:40 Final takeaway

If this helped, subscribe for weekly videos on ${main} and related topics. Comment your biggest question below — the best ones become future videos.

${kws.map(k => "#" + k.replace(/\s+/g, "")).slice(0, 3).join(" ")}

This is AI-generated content for educational purposes.
\`\`\`

## 15 Tags
\`${tags.join(", ")}\`

## Keyword List
- Primary: ${main}
- Secondary: ${kws.slice(1).join(", ") || `${main} tips, ${main} guide`}
- Long-tail: how to ${main} for beginners, ${main} step by step, best way to ${main}
- **First 2 lines** are written for search — keyword in line 1, benefit in line 2.`, T);
    },

    shorts([...s]) {
      const src = s.join(" ") || "your long video";
      const pts = src.split(/[.!?\n]+/).map(x => x.trim()).filter(x => x.length > 15);
      const p = i => pts[i] || pick(["the single biggest mistake", "the fastest method", "the surprising result"], i);
      return out("3 Shorts from Long Script", [0, 1, 2].map(i => "### Short " + (i + 1) + " (" + pick([30, 45, 60], i) + "s)\n```text\n" +
        `[0-3s] HOOK: ${pick(["Nobody tells you this…", "This took me way too long to learn.", "Stop scrolling if you want this to work."], i)}
[3-${pick([25, 38, 52], i)}s] PAYOFF: ${p(i)}. ${pick(["Here's the fix in one line.", "Here's why that matters.", "And the result surprised everyone."], i)}
[last 5s] CTA: The full breakdown is in the long video — tap the link above.
VISUALS: vertical 9:16, captions burned-in, B-roll every 2-3s\n` + "```").join("\n\n"));
    },

    "weekly-plan"([niche = "productivity"]) {
      const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
      const plan = [["Long", "Evergreen", `${cap(niche)} complete beginner guide`], ["Short", "Educational", `1 ${niche} tip in 30s`], ["Long", "Trending", `What's changing in ${niche} right now`], ["Short", "Trending", `Reacting to a viral ${niche} claim`], ["Short", "Evergreen", `${cap(niche)} myth busted`], ["Long", "Educational", `7 ${niche} mistakes to avoid`], ["Short", "Educational", `Best free ${niche} tool`]];
      return out(`7-Day Plan: ${cap(niche)}`, `| Day | Format | Type | Topic | Upload (local) |\n|---|---|---|---|---|\n${plan.map((p, i) => `| ${days[i]} | ${p[0]} | ${p[1]} | ${p[2]} | ${p[0] === "Long" ? "3–5 PM" : "12–2 PM"} |`).join("\n")}\n\n**Batch workflow:** Sun script all 3 longs → Mon voiceover → Tue-Wed edit → cut Shorts from longs.`, niche);
    },

    trends([niche = "productivity"]) {
      const y = new Date().getFullYear();
      return out(`Trends: ${cap(niche)}`, `
> Offline mode can't fetch live data. Verify with free sources: **Google Trends**, YouTube search autocomplete, YouTube "Explore → Trending", Reddit r/${niche.replace(/\s+/g, "")}, TikTok Creative Center, Exploding Topics.

## Evergreen trend patterns in ${niche}
- AI tools changing ${niche} in ${y}
- "Underrated / hidden gem" discoveries
- Challenges & 30-day experiments
- Budget / minimalist versions
- Myth-busting viral claims

## 5 Angles to Ride a Trend
1. **First explainer** — "${cap(niche)} trend explained in 60s" (post within 48h)
2. **Test it** — "I tried the viral ${niche} trend so you don't have to"
3. **Contrarian** — "Why the ${niche} trend is overrated"
4. **Data angle** — "The numbers behind the ${niche} hype"
5. **Prediction** — "Where ${niche} goes next (${y + 1})"`, niche);
    },

    "thumbnail-text"([...t]) {
      const topic = t.join(" ") || "this";
      return out(`Thumbnail Text: ${topic}`, ["NOBODY KNOWS THIS", "STOP DOING THIS", "IT ACTUALLY WORKED", "THE REAL TRUTH", `${(topic.split(" ")[0] || "IT").toUpperCase()} = WRONG?`].map((x, i) => `${i + 1}. **${x}**`).join("\n") + "\n\nRule: ≤4 words, don't repeat the title, max 2 colors.", topic);
    },

    cta([...v]) {
      const type = v.join(" ") || "tutorial";
      return out(`CTAs for: ${type}`, `
- **Subscribe (mid-video, after a win):** "If that tip just clicked, subscribe — there's a ${type} like this every week."
- **Like (after a payoff):** "Tap like if this made more sense than anything else you've watched on it."
- **Comment (question prompt):** "Comment the number 1, 2, or 3 — which method would you try first?"
- **Watch next (end screen):** "This next video picks up exactly where this one stops."
- **Soft open-loop:** "Stay till the end — the last point is the one people screenshot."`);
    },

    "comment-reply"([...c]) {
      const com = c.join(" ") || "Great video!";
      return out("5 Comment Replies", `> Comment: "${com}"\n
1. "Appreciate this! Which part was most useful? Thinking of doing a deep dive 👀"
2. "Thank you! Quick question back — what should the next video cover?"
3. "Love that. Pinning this so others see it — anyone else agree?"
4. "Great point. There's a full breakdown on exactly this in the video linked on screen at the end."
5. "This made our day 🙌 Drop a 🔥 if you want a part 2."

**Tip:** reply within the first hour; end replies with a question to restart the thread.`);
    },

    "upload-checklist"([...t]) {
      const topic = t.join(" ") || "your video";
      return out(`Upload Checklist: ${topic}`, `
- [ ] **Title** ≤60 chars, keyword first (\`/title\`)
- [ ] **Description** 200-300 words, keyword in line 1, chapters, disclaimer (\`/seo\`)
- [ ] **Tags** 15, mix broad + long-tail
- [ ] **Thumbnail** 1280×720, <2MB, readable at mobile size, A/B test (Test & Compare)
- [ ] **Captions** uploaded/auto-checked
- [ ] **Chapters** timestamps starting 0:00
- [ ] **End screen** subscribe + best-performing video (last 20s)
- [ ] **Cards** at 30% and 70% mark
- [ ] **Pinned comment** with question + link to related video
- [ ] **Playlist** added
- [ ] **Altered/synthetic content** disclosure toggled if realistic AI visuals used
- [ ] **Audience** "not made for kids" set correctly
- [ ] **Shorts** 3 cut and scheduled (\`/shorts\`)
- [ ] **Licenses** all stock/music royalty-free`, topic);
    },
  };

  const HELP = out("Claude YouTube — Commands", Object.keys(cmds).map(k => `- \`/${k}\``).join("\n") + "\n\nArgs with two parts use `|`: `/title topic | keyword1, keyword2`. Script length: 60s, 3min, 8min, 10min (last word).");

  function run(input) {
    const m = input.trim().match(/^\/?([\w-]+)\s*(.*)$/s);
    if (!m || !cmds[m[1]]) return HELP;
    const name = m[1], rest = m[2];
    if (name === "ideas") { const p = rest.trim().split(/\s+/); const last = p[p.length - 1]; return /^\d+$/.test(last) ? cmds.ideas([p.slice(0, -1).join(" "), last]) : cmds.ideas([rest || undefined]); }
    if (["channel-audit", "weekly-plan", "trends"].includes(name)) return cmds[name]([rest.trim() || undefined]);
    return cmds[name](rest.trim() ? rest.trim().split(/\s+/) : []);
  }

  const api = { run, commands: Object.keys(cmds), DISCLAIMER };
  if (typeof module !== "undefined") module.exports = api; else root.ClaudeYouTube = api;
})(this);
