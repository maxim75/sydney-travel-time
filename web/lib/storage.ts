// The chosen dataset is remembered per viewer. Storage can be missing or throw (private
// windows, blocked site data), so reads and writes never fail.
const STORE_KEY = "sydney-travel-times:dataset";

function localStore(): Storage | null {
  try { return window.localStorage; } catch { return null; }
}

export function rememberedDataset(storage: Storage | null = localStore()): string | null {
  try { return storage?.getItem(STORE_KEY) ?? null; } catch { return null; }
}

export function rememberDataset(id: string, storage: Storage | null = localStore()): void {
  try { storage?.setItem(STORE_KEY, id); } catch { /* storage unavailable */ }
}
