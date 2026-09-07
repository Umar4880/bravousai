export interface UserSettings {
  tavilyApiKey: string;
  providerApiKey: string;
  providerModels: string[];
  selectedModel: string;
}

const DEFAULT_SETTINGS: UserSettings = {
  tavilyApiKey: "",
  providerApiKey: "",
  providerModels: [],
  selectedModel: "",
};

export function getUserSettings(): UserSettings {
  if (typeof window === "undefined") {
    return DEFAULT_SETTINGS;
  }
  
  try {
    const data = localStorage.getItem("bravous_user_settings");
    if (data) {
      const parsed = JSON.parse(data);
      return { ...DEFAULT_SETTINGS, ...parsed };
    }
  } catch (error) {
    console.error("Failed to parse user settings from localStorage", error);
  }
  
  return DEFAULT_SETTINGS;
}

export function saveUserSettings(settings: Partial<UserSettings>): void {
  if (typeof window === "undefined") return;
  
  const current = getUserSettings();
  const next = { ...current, ...settings };
  
  try {
    localStorage.setItem("bravous_user_settings", JSON.stringify(next));
  } catch (error) {
    console.error("Failed to save user settings to localStorage", error);
  }
}
