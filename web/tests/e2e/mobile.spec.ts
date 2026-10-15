import { devices, expect, test } from "@playwright/test";
import { serveFixtures } from "./helpers";

// defaultBrowserType would force a new worker inside a describe group
const { defaultBrowserType: _browser, ...pixel7 } = devices["Pixel 7"];
const phones = {
  "Pixel 7 (412px)": pixel7,
  "375px phone": { ...pixel7, viewport: { width: 375, height: 812 } },
};

for (const [name, device] of Object.entries(phones)) {
  test.describe(name, () => {
    test.use({ ...device });

    async function open(page: import("@playwright/test").Page) {
      await serveFixtures(page);
      await page.goto("./");
      await expect(page.getByRole("heading", { level: 1 })).toContainText("Test Building");
    }

    test("does not scroll sideways", async ({ page }) => {
      await open(page);
      // A mobile browser widens window.innerWidth to fit overflowing content, so compare with the device width
      const scroll = await page.evaluate(() => document.documentElement.scrollWidth);
      expect(scroll).toBeLessThanOrEqual(page.viewportSize()!.width);
    });

    test("tapping a hexagon pins its tooltip", async ({ page }) => {
      await open(page);
      // The phone-sized canvas draws the hexagons smaller than the desktop one, so tap closer to the centre
      const box = (await page.locator("canvas").boundingBox())!;
      await page.tap("canvas", { position: { x: box.width / 2, y: box.height / 2 + 15 } });
      const tip = page.locator(".tip");
      await expect(tip).toBeVisible();
      await expect(tip).toContainText("1 TEST STREET, SYDNEY");
    });
  });
}
