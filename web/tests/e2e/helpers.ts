import type { Page } from "@playwright/test";
import { fixtureDataset, fixtureSite, ONWARD_ID, RETURN_ID } from "../fixtures";

interface Options {
  siteStatus?: number;  // respond to site.json with this error status
  delay?: Record<string, number>;  // milliseconds to hold back a dataset's response
}

// Answers site.json and map_data/<id>.json with the test fixtures, and blocks Google's tag script
export async function serveFixtures(page: Page, opts: Options = {}) {
  await page.route("https://www.googletagmanager.com/**", (route) => route.abort());
  await page.route("**/site.json", (route) =>
    opts.siteStatus ? route.fulfill({ status: opts.siteStatus }) : route.fulfill({ json: fixtureSite() }));
  await page.route("**/map_data/*.json", async (route) => {
    const id = decodeURIComponent(new URL(route.request().url()).pathname.split("/").pop()!.replace(/\.json$/, ""));
    const data = id === ONWARD_ID ? fixtureDataset("onward") : id === RETURN_ID ? fixtureDataset("return") : null;
    const wait = opts.delay?.[id];
    if (wait) await new Promise((resolve) => setTimeout(resolve, wait));
    await (data ? route.fulfill({ json: data }) : route.fulfill({ status: 404 }));
  });
}

// Failed responses under the base path (the browser's own /favicon.ico probe is outside it),
// collected for the life of the page
export function failedRequests(page: Page): string[] {
  const failed: string[] = [];
  page.on("response", (res) => {
    if (res.status() >= 400 && new URL(res.url()).pathname.startsWith("/sydney-travel-time/")) failed.push(`${res.status()} ${res.url()}`);
  });
  return failed;
}
