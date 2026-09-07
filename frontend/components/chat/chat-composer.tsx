"use client";

import { useState, useEffect } from "react";
import type { FormEvent, KeyboardEvent, RefObject } from "react";
import { LuChevronDown, LuChevronUp } from "react-icons/lu";
import type { ChatMode } from "../../lib/api";
import { getUserSettings, saveUserSettings } from "../../lib/settings";

type ChatComposerProps = {
  draft: string;
  selectedMode: ChatMode;
  isModeMenuOpen: boolean;
  canSend: boolean;
  isActiveSending: boolean;
  isLoadingConversation: boolean;
  composerHeight: number;
  isFreshConversation: boolean;
  inputRef: RefObject<HTMLTextAreaElement | null>;
  onDraftChange: (value: string) => void;
  onModeChange: (mode: ChatMode) => void;
  onModeMenuToggle: () => void;
  onModeMenuClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
  onStop?: () => void;
  disabled?: boolean;
  placeholder?: string;
};

export function ChatComposer({
  draft,
  selectedMode,
  isModeMenuOpen,
  canSend,
  isActiveSending,
  isLoadingConversation,
  composerHeight,
  isFreshConversation,
  inputRef,
  onDraftChange,
  onModeChange,
  onModeMenuToggle,
  onModeMenuClose,
  onSubmit,
  onKeyDown,
  onStop,
  disabled = false,
  placeholder,
}: ChatComposerProps) {
  const isInputDisabled = disabled || isActiveSending || isLoadingConversation;
  const inputPlaceholder = placeholder || "Type your message here...";

  // Dynamic Models State
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [selectedProviderModel, setSelectedProviderModel] = useState<string>("");
  const [isModelMenuOpen, setIsModelMenuOpen] = useState(false);

  useEffect(() => {
    const loadSettings = () => {
      const settings = getUserSettings();
      setAvailableModels(settings.providerModels || []);
      setSelectedProviderModel(settings.selectedModel || "");
    };
    loadSettings();
    window.addEventListener("bravous_settings_updated", loadSettings);
    return () => window.removeEventListener("bravous_settings_updated", loadSettings);
  }, []);

  const handleModelSelect = (model: string) => {
    saveUserSettings({ selectedModel: model });
    setSelectedProviderModel(model);
    setIsModelMenuOpen(false);
  };

  return (
    <form className={`unified-composer ${isFreshConversation ? "composer-centered" : ""}`} onSubmit={onSubmit}>
      
      <textarea
        ref={inputRef}
        value={draft}
        onChange={(event) => onDraftChange(event.target.value)}
        onKeyDown={onKeyDown}
        placeholder={inputPlaceholder}
        className="transparent-input"
        rows={1}
        disabled={isInputDisabled}
        // Maintains your external height calculation logic
        style={{ height: composerHeight ? `${composerHeight}px` : 'auto' }}
      />

      <div className="composer-toolbar">
        <div style={{ display: "flex", gap: "8px" }}>
          <div className="mode-picker">
            <button
              className="mode-picker-trigger"
              type="button"
              onClick={onModeMenuToggle}
              disabled={isInputDisabled}
              aria-haspopup="menu"
              aria-expanded={isModeMenuOpen}
            >
              {selectedMode === "instant" ? "Instant" : "Extended"}
              <span aria-hidden="true"><LuChevronDown size={16}/></span>
            </button>
            
            {isModeMenuOpen && (
              <div className="mode-menu" role="menu">
                <button 
                  type="button" 
                  role="menuitem"
                  className={selectedMode === "instant" ? "active" : ""}
                  onClick={() => { onModeChange("instant"); onModeMenuClose(); }}
                >
                  Instant
                </button>
                <button 
                  type="button" 
                  role="menuitem"
                  className={selectedMode === "extended" ? "active" : ""}
                  onClick={() => { onModeChange("extended"); onModeMenuClose(); }}
                >
                  Extended
                </button>
              </div>
            )}
          </div>

          {availableModels.length > 0 && (
            <div className="mode-picker">
              <button
                className="mode-picker-trigger"
                type="button"
                onClick={() => setIsModelMenuOpen(!isModelMenuOpen)}
                disabled={isInputDisabled}
                aria-haspopup="menu"
                aria-expanded={isModelMenuOpen}
              >
                <span style={{ maxWidth: "120px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {selectedProviderModel || "Select Model"}
                </span>
                <span aria-hidden="true"><LuChevronDown size={16}/></span>
              </button>
              
              {isModelMenuOpen && (
                <div className="mode-menu" role="menu" style={{ bottom: "100%", top: "auto", marginBottom: "8px", maxHeight: "200px", overflowY: "auto" }}>
                  {availableModels.map((model) => (
                    <button 
                      key={model}
                      type="button" 
                      role="menuitem"
                      className={selectedProviderModel === model ? "active" : ""}
                      onClick={() => handleModelSelect(model)}
                    >
                      {model}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
        
        {isActiveSending && onStop ? (
          <button className="send-button stop-button" type="button" onClick={onStop} style={{ backgroundColor: "#e25555", color: "white" }}>
            Stop Generating
          </button>
        ) : (
          <button className="send-button" type="submit" disabled={!canSend || isInputDisabled}>
            Send
          </button>
        )}
      </div>
      
    </form>
  );
}