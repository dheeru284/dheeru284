import { expect, test, type Page } from "@playwright/test";
import { execSync } from "node:child_process";

// Requires a migrated + seeded database (npm run db:seed). Clears rate-limit buckets and resets matching settings to defaults so runs are repeatable.
test.beforeAll(() => {
  execSync(`npx tsx -e "import('@prisma/client').then(async ({PrismaClient}) => { const p = new PrismaClient(); await p.rateLimitBucket.deleteMany(); await p.platformSetting.deleteMany({ where: { key: 'matching' } }); await p.\\$disconnect(); })"`, { stdio: "inherit" });
});

async function login(page: Page, phone: string) {
  await page.goto("/login");
  await page.getByLabel("Mobile number").fill(phone);
  await page.getByRole("button", { name: "Send code" }).click();
  const code = await page.locator("text=/your code is/").locator("b").textContent();
  await page.getByLabel("6-digit code").fill(code!);
  await page.getByRole("button", { name: "Verify and continue" }).click();
  await page.waitForURL((u) => !u.pathname.startsWith("/login"));
}

function nextWeekday(dow: number, minDays: number) {
  const d = new Date(Date.now() + minDays * 86_400_000);
  while (d.getUTCDay() !== dow) d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}

test("public pages show the emergency notice and no horizontal overflow", async ({ page }) => {
  for (const path of ["/", "/services", "/stays", "/hospitals", "/safety", "/privacy"]) {
    await page.goto(path);
    await expect(page.getByText(/not an emergency service/i)).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  }
});

test("patient finds eligible nurses, requests a visit, nurse accepts", async ({ page, browser }, info) => {
  await login(page, "+919000000010");
  await page.goto("/patient/book");
  await page.getByLabel("Date").fill(nextWeekday(info.project.name === "mobile" ? 4 : 5, 5 + Math.floor(Math.random() * 40)));
  await page.getByLabel("Start time (IST)").fill(["09:15", "11:45", "14:30", "16:15"][Math.floor(Math.random() * 4)]!);
  await page.getByRole("button", { name: "Find available nurses" }).click();
  await expect(page.getByText(/within 120 minutes/)).toBeVisible();
  await expect(page.getByText("Demo Nurse Pending")).toHaveCount(0);
  await expect(page.getByText("Demo Nurse Far Away")).toHaveCount(0);
  const first = page.locator("li.card").first();
  const nurseName = (await first.locator("p.font-semibold a").textContent())!.trim();
  await first.getByRole("button", { name: "Request visit" }).click();
  await expect(page.getByText(/Request .* sent/)).toBeVisible();
  await page.getByRole("link", { name: "View appointment" }).click();
  await page.waitForURL(/\/patient\/appointments\/[^/]+$/);
  const apptUrl = page.url();
  await expect(page.locator(".badge", { hasText: /awaiting nurse acceptance/i })).toBeVisible();

  const phones: Record<string, string> = { "Demo Nurse Asha": "+919000000101", "Demo Nurse Ravi": "+919000000102", "Demo Nurse Meera": "+919000000103" };
  const nctx = await browser.newContext();
  const npage = await nctx.newPage();
  await login(npage, phones[nurseName]!);
  await npage.goto(apptUrl.replace("/patient/", "/nurse/"));
  await expect(npage.getByText("(full address shown after acceptance)")).toBeVisible();
  await npage.getByRole("button", { name: "Accept" }).click();
  await expect(npage.getByRole("button", { name: "I'm on my way" })).toBeVisible();
  await expect(npage.getByText(/12 Demo Street/)).toBeVisible();
  await nctx.close();

  await page.reload();
  await expect(page.locator(".badge", { hasText: /^confirmed$/ })).toBeVisible();
});

test("admin changes the travel-time limit from the console", async ({ page }) => {
  await login(page, "+919000000001");
  await page.goto("/admin");
  await page.getByRole("button", { name: "Travel & matching" }).click();
  const field = page.getByLabel("Maximum road travel time (minutes)");
  await expect(field).toHaveValue("120");
  await field.fill("90");
  await page.getByRole("button", { name: "Save settings" }).click();
  await expect(page.getByText("Saved.")).toBeVisible();
  await field.fill("120");
  await page.getByRole("button", { name: "Save settings" }).click();
  await expect(page.getByText("Saved.")).toBeVisible();
});

test("patient cannot open the admin console", async ({ page }) => {
  await login(page, "+919000000010");
  await page.goto("/admin");
  await expect(page).toHaveURL(/\/$/);
});
