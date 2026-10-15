import { expect, test } from "@playwright/test";
import { fixtureSite, RETURN_ID } from "../fixtures";
import { failedRequests, serveFixtures } from "./helpers";

const [ONWARD_LABEL, RETURN_LABEL] = fixtureSite().datasets.map((d) => d.label);

test("loads every asset and the data under the base path", async ({ page }) => {
  const failed = failedRequests(page);
  await serveFixtures(page);
  await page.goto("./");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("How long does it take to get to Test Building?");
  expect(failed).toEqual([]);
});

test("shows the first dataset's statistics", async ({ page }) => {
  await serveFixtures(page);
  await page.goto("./");
  const stats = page.locator(".stats");
  await expect(stats).toContainText("6 of 7");
  await expect(stats).toContainText("50 min");
  await expect(stats).toContainText("with no journey found");
});

test("switching to a return dataset retitles the page and offers night filters", async ({ page }) => {
  await serveFixtures(page);
  await page.goto("./");
  await expect(page.getByRole("button", { name: "Tonight" })).toBeHidden();
  await page.getByLabel("Dataset").selectOption({ label: RETURN_LABEL });
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("How long does it take to get home from Test Building?");
  await expect(page.getByRole("button", { name: "Tonight" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Time to get there" })).toBeVisible();
  await page.getByRole("button", { name: "Next morning" }).click();
  await page.getByLabel("Dataset").selectOption({ label: ONWARD_LABEL });
  await expect(page.getByRole("button", { name: "All trips" })).toHaveAttribute("aria-pressed", "true");
});

test("the legend follows the colour-by choice", async ({ page }) => {
  await serveFixtures(page);
  await page.goto("./");
  await page.getByRole("button", { name: "Rides" }).click();
  await expect(page.locator("#legend-title")).toHaveText("Rides taken");
  await expect(page.locator(".key")).toContainText("Rides taken");
});

test("the suburb table searches and sorts", async ({ page }) => {
  await serveFixtures(page);
  await page.goto("./");
  const rows = page.locator(".tablebox tbody");
  await expect(rows).toContainText("Sydney");
  await page.getByLabel("Find a suburb").fill("hay");
  await expect(rows).toContainText("No suburb matches that search.");
  await page.getByLabel("Find a suburb").fill("");
  await page.getByRole("button", { name: "Suburb", exact: true }).click();
  // Once sorted, the CSS arrow becomes part of the button's accessible name ("Suburb ↑")
  await expect(page.getByRole("button", { name: /^Suburb/ })).toHaveAttribute("aria-sort", "ascending");
});

test("a slow earlier dataset does not replace a later pick", async ({ page }) => {
  await serveFixtures(page, { delay: { [fixtureSite().datasets[0].id]: 1500 } });
  await page.goto("./");
  await page.getByLabel("Dataset").selectOption({ label: RETURN_LABEL });
  await expect(page.getByRole("heading", { level: 1 })).toContainText("get home from");
  await page.waitForTimeout(2000);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("get home from");
  await expect(page.getByLabel("Dataset")).toHaveValue(RETURN_ID);
});

test("restores the remembered dataset, and ignores one that no longer exists", async ({ page }) => {
  await serveFixtures(page);
  await page.addInitScript((id) => localStorage.setItem("sydney-travel-times:dataset", id), RETURN_ID);
  await page.goto("./");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("get home from");
  await page.evaluate(() => localStorage.setItem("sydney-travel-times:dataset", "GONE"));
  await page.addInitScript(() => localStorage.setItem("sydney-travel-times:dataset", "GONE"));
  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("get to Test Building");
});

test("says so when the site data can't be loaded", async ({ page }) => {
  await serveFixtures(page, { siteStatus: 404 });
  await page.goto("./");
  await expect(page.locator(".sub")).toHaveText("Couldn't load the map data (HTTP 404).");
});
