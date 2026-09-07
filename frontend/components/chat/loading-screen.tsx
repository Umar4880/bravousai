"use client";

type LoadingScreenProps = {
  label?: string;
  variant?: "workspace" | "sidebar" | "inline";
};

export function LoadingScreen({
  label = "Loading...",
  variant = "workspace",
}: LoadingScreenProps) {
  return (
    <div
      className={`loading-screen loading-screen--${variant}`}
      role="status"
      aria-live="polite"
      aria-label={label}
    >
      <div className="loading-screen__spinner" aria-hidden="true" />
      {variant !== "sidebar" && <p className="loading-screen__label">{label}</p>}
    </div>
  );
}
