import { useState, useEffect } from "react";
import { LuX } from "react-icons/lu";
import { getUserSettings, saveUserSettings, type UserSettings } from "../../lib/settings";

type SettingsModalProps = {
  isOpen: boolean;
  onClose: () => void;
};

export function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const [tavilyApiKey, setTavilyApiKey] = useState("");
  const [providerApiKey, setProviderApiKey] = useState("");
  const [providerModelsStr, setProviderModelsStr] = useState("");

  useEffect(() => {
    if (isOpen) {
      const current = getUserSettings();
      setTavilyApiKey(current.tavilyApiKey || "");
      setProviderApiKey(current.providerApiKey || "");
      setProviderModelsStr(current.providerModels?.join(", ") || "");
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSave = () => {
    const models = providerModelsStr
      .split(",")
      .map(s => s.trim())
      .filter(s => s.length > 0);

    saveUserSettings({
      tavilyApiKey,
      providerApiKey,
      providerModels: models,
      selectedModel: models.length > 0 ? models[0] : "", // Reset selection to first available
    });
    
    // dispatch an event so other components know settings updated
    window.dispatchEvent(new Event("bravous_settings_updated"));
    
    onClose();
  };

  return (
    <div className="modal-backdrop">
      <div className="modal-content" style={{ maxWidth: "500px" }}>
        <button className="modal-close-button" onClick={onClose} aria-label="Close">
          <LuX size={20} />
        </button>
        
        <h2 style={{ marginBottom: "20px" }}>User Settings</h2>
        
        <div style={{ marginBottom: "16px" }}>
          <label style={{ display: "block", marginBottom: "8px", fontWeight: "bold" }}>
            Tavily Search API Key
          </label>
          <input 
            type="password"
            className="transparent-input"
            style={{ width: "100%", padding: "8px", border: "1px solid #444", borderRadius: "4px" }}
            placeholder="tvly-..."
            value={tavilyApiKey}
            onChange={(e) => setTavilyApiKey(e.target.value)}
          />
          <small style={{ color: "#888", display: "block", marginTop: "4px" }}>
            Required for deep research web searches.
          </small>
        </div>

        <div style={{ marginBottom: "16px" }}>
          <label style={{ display: "block", marginBottom: "8px", fontWeight: "bold" }}>
            Inference Provider API Key (e.g. Digital Ocean)
          </label>
          <input 
            type="password"
            className="transparent-input"
            style={{ width: "100%", padding: "8px", border: "1px solid #444", borderRadius: "4px" }}
            placeholder="do-..."
            value={providerApiKey}
            onChange={(e) => setProviderApiKey(e.target.value)}
          />
        </div>

        <div style={{ marginBottom: "24px" }}>
          <label style={{ display: "block", marginBottom: "8px", fontWeight: "bold" }}>
            Provider Model IDs (comma separated)
          </label>
          <textarea 
            className="transparent-input"
            style={{ width: "100%", padding: "8px", border: "1px solid #444", borderRadius: "4px", minHeight: "80px" }}
            placeholder="meta-llama-3-8b-instruct, mistral-7b-instruct..."
            value={providerModelsStr}
            onChange={(e) => setProviderModelsStr(e.target.value)}
          />
          <small style={{ color: "#888", display: "block", marginTop: "4px" }}>
            These models will appear in your chat composer dropdown.
          </small>
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end", gap: "12px" }}>
          <button className="text-button" onClick={onClose}>
            Cancel
          </button>
          <button className="primary-button" onClick={handleSave}>
            Save Settings
          </button>
        </div>
      </div>
    </div>
  );
}
