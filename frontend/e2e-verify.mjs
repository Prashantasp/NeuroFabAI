/**
 * Manual end-to-end verification driver.
 *
 * Not part of the test suite: it drives a real browser against locally running
 * frontend + backend to confirm the flows work, and captures screenshots at each
 * breakpoint. Run with:  node e2e-verify.mjs
 */

import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const APP = process.env.APP_URL ?? "http://127.0.0.1:3000";
const SHOTS = "e2e-shots";
mkdirSync(SHOTS, { recursive: true });

const stamp = Date.now();
const EMAIL = `verify_${stamp}@neurofab-verify.example.com`;
const PASSWORD = "Correct-Horse-9";

const results = [];
const record = (name, ok, detail = "") => {
  results.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();

const consoleErrors = [];
page.on("console", (msg) => {
  if (msg.type() === "error") consoleErrors.push(msg.text());
});
page.on("pageerror", (err) => consoleErrors.push(`pageerror: ${err.message}`));

try {
  // --- landing -------------------------------------------------------------
  await page.goto(APP, { waitUntil: "networkidle" });
  record("landing renders", await page.getByRole("heading", { level: 1 }).isVisible());
  await page.screenshot({ path: `${SHOTS}/01-landing-desktop.png`, fullPage: true });

  // --- protected route redirects ------------------------------------------
  await page.goto(`${APP}/dashboard`, { waitUntil: "networkidle" });
  record("unauthenticated /dashboard redirects to login", page.url().includes("/login"));

  // --- registration --------------------------------------------------------
  await page.goto(`${APP}/register`, { waitUntil: "networkidle" });
  await page.fill("#full-name", "Verify Engineer");
  await page.fill("#email", EMAIL);

  // Weak password must keep the submit disabled.
  await page.fill("#password", "short");
  await page.fill("#confirm", "short");
  record(
    "weak password blocks submit",
    await page.getByRole("button", { name: /create account/i }).isDisabled(),
  );
  await page.screenshot({ path: `${SHOTS}/02-register-validation.png` });

  await page.fill("#password", PASSWORD);
  await page.fill("#confirm", PASSWORD);
  await page.getByRole("button", { name: /create account/i }).click();
  await page.waitForURL(/\/login/, { timeout: 20_000 });
  record("registration succeeds", true, "redirected to login");

  // --- login ---------------------------------------------------------------
  await page.fill("#email", EMAIL);
  await page.fill("#password", PASSWORD);
  await page.getByRole("button", { name: /^sign in$/i }).click();
  await page.waitForURL(/\/dashboard/, { timeout: 25_000 });
  record("login succeeds", true);

  // Dashboard data is fetched only once the workspace list resolves, so wait
  // for the resolved state rather than the first network idle.
  const emptyState = page.getByText(/this workspace is empty/i);
  await emptyState.waitFor({ state: "visible", timeout: 20_000 }).catch(() => {});
  await page.screenshot({ path: `${SHOTS}/03-dashboard-empty.png`, fullPage: true });

  // Empty state must guide the user, not show a blank page.
  record("dashboard shows an actionable empty state", await emptyState.isVisible());

  // --- session survives a hard refresh (token is not in localStorage) ------
  await page.reload({ waitUntil: "networkidle" });
  record("session survives a hard reload", page.url().includes("/dashboard"));

  const tokenInStorage = await page.evaluate(() =>
    Object.keys(window.localStorage).some((k) => /token/i.test(k)),
  );
  record("no access token in localStorage", !tokenInStorage);

  // The refresh token must be HttpOnly; only the non-secret hint is scriptable.
  const scriptableCookies = await page.evaluate(() => document.cookie);
  record(
    "refresh token is not readable by JavaScript",
    !scriptableCookies.includes("refresh_token"),
  );

  // --- navigation ----------------------------------------------------------
  for (const [name, path, expect] of [
    ["Documents", "/hub", /no documents yet/i],
    ["Knowledge graph", "/graph", /no entities extracted yet/i],
    ["Analytics", "/analytics", /nothing to measure yet/i],
    ["Copilot", "/copilot", /ask about your documents/i],
  ]) {
    await page.goto(`${APP}${path}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(800);
    const visible = await page.getByText(expect).first().isVisible().catch(() => false);
    record(`${name} page renders its empty state`, visible);
    await page.screenshot({ path: `${SHOTS}/04-${path.slice(1)}.png`, fullPage: true });
  }

  // --- settings ------------------------------------------------------------
  await page.goto(`${APP}/settings`, { waitUntil: "networkidle" });
  await page.waitForTimeout(500);
  record("settings profile loads", await page.locator("#full-name").isVisible());

  await page.getByRole("button", { name: "System" }).click();
  await page.waitForTimeout(1500);
  const online = await page.getByText("Online").count();
  record("settings reports live dependency status", online > 0, `${online} components online`);
  await page.screenshot({ path: `${SHOTS}/05-settings-system.png`, fullPage: true });

  // --- theme ---------------------------------------------------------------
  await page.getByRole("button", { name: "Appearance" }).click();
  await page.waitForTimeout(300);
  await page.getByRole("radio", { name: "Dark" }).click();
  await page.waitForTimeout(400);
  const isDark = await page.evaluate(() =>
    document.documentElement.classList.contains("dark"),
  );
  record("dark theme applies", isDark);
  await page.screenshot({ path: `${SHOTS}/06-settings-dark.png`, fullPage: true });

  await page.getByRole("radio", { name: "Light" }).click();
  await page.waitForTimeout(400);
  const isLight = await page.evaluate(
    () => !document.documentElement.classList.contains("dark"),
  );
  record("light theme applies", isLight);

  // --- command palette -----------------------------------------------------
  await page.goto(`${APP}/dashboard`, { waitUntil: "networkidle" });
  await page.keyboard.press("Control+k");
  await page.waitForTimeout(600);
  const paletteOpen = await page
    .getByRole("dialog", { name: /search and commands/i })
    .isVisible()
    .catch(() => false);
  record("command palette opens with Ctrl+K", paletteOpen);
  await page.screenshot({ path: `${SHOTS}/07-command-palette.png` });
  await page.keyboard.press("Escape");

  // --- copilot without documents ------------------------------------------
  await page.goto(`${APP}/copilot`, { waitUntil: "networkidle" });
  await page.fill("#copilot-input", "What equipment is documented here?");
  await page.getByRole("button", { name: /send question/i }).click();

  // The loading state must appear immediately, before the model responds.
  const thinking = page.getByRole("status").filter({ hasText: /retriev|synthes|analys/i });
  record(
    "copilot shows progress while working",
    await thinking.first().isVisible({ timeout: 5_000 }).catch(() => false),
  );

  // Then wait for a real outcome. A model round trip can take a while, and the
  // provider may 503 and be retried, so this window is generous.
  const answer = page.locator("article").first();
  const failure = page.getByText(/the copilot could not answer/i);
  const outcome = await Promise.race([
    answer.waitFor({ state: "visible", timeout: 90_000 }).then(() => "answer"),
    failure.waitFor({ state: "visible", timeout: 90_000 }).then(() => "error"),
  ]).catch(() => "timeout");

  record("copilot resolves to an answer or a clear error", outcome !== "timeout", outcome);
  if (outcome === "answer") {
    const text = (await answer.innerText()).trim();
    record("answer is non-empty and cites its confidence", /confidence/i.test(text) && text.length > 60);
  }
  await page.screenshot({ path: `${SHOTS}/08-copilot-answer.png`, fullPage: true });

  // --- responsive ----------------------------------------------------------
  for (const [label, width, height] of [
    ["mobile", 390, 844],
    ["tablet", 820, 1180],
  ]) {
    await page.setViewportSize({ width, height });
    await page.goto(`${APP}/dashboard`, { waitUntil: "networkidle" });
    await page.waitForTimeout(700);

    const hasHorizontalScroll = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
    );
    record(`${label}: no horizontal overflow`, !hasHorizontalScroll);
    await page.screenshot({ path: `${SHOTS}/09-dashboard-${label}.png`, fullPage: true });

    if (label === "mobile") {
      const menu = page.getByRole("button", { name: /open navigation/i });
      record("mobile: navigation button present", await menu.isVisible());
      await menu.click();
      await page.waitForTimeout(500);
      record(
        "mobile: navigation drawer opens",
        await page.getByRole("dialog", { name: "Navigation" }).isVisible(),
      );
      await page.screenshot({ path: `${SHOTS}/10-mobile-drawer.png` });
      await page.keyboard.press("Escape");
    }
  }

  await page.setViewportSize({ width: 1440, height: 900 });

  // --- sign out ------------------------------------------------------------
  await page.goto(`${APP}/dashboard`, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: /account menu/i }).click();
  await page.waitForTimeout(300);
  await page.getByRole("menuitem", { name: /sign out/i }).click();
  await page.waitForURL(/\/login/, { timeout: 15_000 });
  record("sign out returns to login", true);

  await page.goto(`${APP}/dashboard`, { waitUntil: "networkidle" });
  record("session is gone after sign out", page.url().includes("/login"));
} catch (error) {
  record("run completed without exception", false, String(error).slice(0, 300));
  await page.screenshot({ path: `${SHOTS}/99-failure.png`, fullPage: true }).catch(() => {});
} finally {
  // Ignore benign noise: aborted in-flight fetches on navigation.
  const realErrors = consoleErrors.filter(
    (e) => !/aborted|AbortError|Failed to fetch|net::ERR_ABORTED/i.test(e),
  );
  record("no unexpected console errors", realErrors.length === 0, realErrors.slice(0, 3).join(" | "));

  await browser.close();

  const failed = results.filter((r) => !r.ok);
  console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
  process.exit(failed.length === 0 ? 0 : 1);
}
