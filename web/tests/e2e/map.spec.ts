import { expect, test, type Page } from "@playwright/test";
import { ONWARD_ID } from "../fixtures";
import { serveFixtures } from "./helpers";

// Canvas pixel at CSS coordinates relative to the canvas
async function pixel(page: Page, x: number, y: number) {
  return page.locator("canvas").evaluate((c: HTMLCanvasElement, [x, y]) => {
    const d = c.getContext("2d")!.getImageData(Math.round(x * devicePixelRatio), Math.round(y * devicePixelRatio), 1, 1).data;
    return [d[0], d[1], d[2]];
  }, [x, y]);
}
// A point inside hexagon 0, below the building marker and the rail line through its centre
async function insideFirstHexagon(page: Page) {
  const box = (await page.locator("canvas").boundingBox())!;
  return { x: box.width / 2, y: box.height / 2 + 30, pageX: box.x + box.width / 2, pageY: box.y + box.height / 2 + 30 };
}
async function open(page: Page) {
  await serveFixtures(page);
  await page.goto("./");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Test Building");
}

test("colours a hexagon with a 25-minute trip in the first ramp colour", async ({ page }) => {
  await open(page);
  const p = await insideFirstHexagon(page);
  await expect.poll(() => pixel(page, p.x, p.y)).toEqual([246, 211, 26]);  // --r0 in the light theme
});

test("hovering a hexagon shows its trip", async ({ page }) => {
  await open(page);
  const p = await insideFirstHexagon(page);
  await page.mouse.move(p.pageX, p.pageY);
  const tip = page.locator(".tip");
  await expect(tip).toBeVisible();
  await expect(tip).toContainText("1 TEST STREET, SYDNEY");
  await expect(tip).toContainText("25 min");
  await expect(tip).toContainText("Train T1");
  await expect(tip).toContainText("Central Station → Town Hall Station");
  await page.mouse.move(1, 1);
  await expect(tip).toBeHidden();
});

test("clicking a hexagon sends a hexagon_click event to Google Analytics", async ({ page }) => {
  await open(page);
  await page.waitForFunction(() => typeof window.gtag === "function");
  const p = await insideFirstHexagon(page);
  await page.mouse.click(p.pageX, p.pageY);
  const events = await page.evaluate(() =>
    (window as unknown as { dataLayer: IArguments[] }).dataLayer.map((a) => Array.from(a)).filter((a) => a[1] === "hexagon_click"));
  expect(events).toEqual([["event", "hexagon_click", { latitude: -33.87174, longitude: 151.20669, suburb: "Sydney", dataset: ONWARD_ID }]]);
});

test("redraws in the dark palette when the colour scheme changes", async ({ page }) => {
  await open(page);
  await expect.poll(() => pixel(page, 5, 5)).toEqual([252, 252, 251]);  // --surface, light
  await page.emulateMedia({ colorScheme: "dark" });
  await expect.poll(() => pixel(page, 5, 5)).toEqual([26, 26, 25]);  // --surface, dark
});

test("labels use the Barlow web fonts", async ({ page }) => {
  await open(page);
  const fonts = await page.evaluate(async () => {
    await document.fonts.ready;
    const cs = getComputedStyle(document.documentElement);
    return { cond: cs.getPropertyValue("--cond"), sans: cs.getPropertyValue("--sans"),
      loaded: [...document.fonts].filter((f) => f.status === "loaded").map((f) => f.family) };
  });
  expect(fonts.cond).toContain("Barlow");
  expect(fonts.sans).toContain("Barlow");
  expect(fonts.loaded.some((f) => f.includes("Barlow"))).toBe(true);
});

test("zoom buttons and suburb rows move the map", async ({ page }) => {
  await open(page);
  const canvas = page.locator("canvas");
  await page.waitForTimeout(300);
  const before = await canvas.screenshot();
  await page.getByRole("button", { name: "Zoom in" }).click();
  await page.waitForTimeout(300);
  const zoomed = await canvas.screenshot();
  expect(zoomed.equals(before)).toBe(false);
  await page.getByRole("button", { name: "Show all of Sydney" }).click();
  await page.locator(".tablebox tbody tr", { hasText: "Sydney" }).click();
  await page.waitForTimeout(300);
  expect((await canvas.screenshot()).equals(before)).toBe(false);
});
