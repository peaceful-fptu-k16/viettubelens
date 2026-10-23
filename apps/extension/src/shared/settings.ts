import type { ExtensionSettings } from "./types";

export const DEFAULT_SETTINGS: ExtensionSettings = {
  enabled: true,
  showToxicity: true,
  animations: true,
  maxCards: 12,
  backendUrl: "http://127.0.0.1:8000",
};

const SETTINGS_VERSION = 2;

function normalizedMaxCards(value: unknown): number {
  const numeric = typeof value === "number" ? value : DEFAULT_SETTINGS.maxCards;
  return Math.min(12, Math.max(3, Math.round(numeric)));
}

function hasExtensionStorage(): boolean {
  return typeof chrome !== "undefined" && Boolean(chrome.storage?.sync);
}

export async function getSettings(): Promise<ExtensionSettings> {
  if (!hasExtensionStorage()) {
    const stored = globalThis.localStorage?.getItem("vtl-preview-settings");
    return stored ? { ...DEFAULT_SETTINGS, ...JSON.parse(stored) } : DEFAULT_SETTINGS;
  }
  const stored = await chrome.storage.sync.get({ ...DEFAULT_SETTINGS, settingsVersion: 0 });
  const needsMigration = Number(stored.settingsVersion) < SETTINGS_VERSION;
  const next = {
    ...DEFAULT_SETTINGS,
    ...stored,
    maxCards: needsMigration ? DEFAULT_SETTINGS.maxCards : normalizedMaxCards(stored.maxCards),
  } as ExtensionSettings;
  if (needsMigration) {
    await chrome.storage.sync.set({ maxCards: next.maxCards, settingsVersion: SETTINGS_VERSION });
  }
  return next;
}

export async function saveSettings(settings: Partial<ExtensionSettings>): Promise<ExtensionSettings> {
  const next = { ...(await getSettings()), ...settings };
  next.maxCards = normalizedMaxCards(next.maxCards);
  if (!hasExtensionStorage()) {
    globalThis.localStorage?.setItem("vtl-preview-settings", JSON.stringify(next));
    return next;
  }
  await chrome.storage.sync.set({ ...next, settingsVersion: SETTINGS_VERSION });
  return next;
}
