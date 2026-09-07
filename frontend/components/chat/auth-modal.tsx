"use client";

import type { AuthUser } from "../../lib/api";
import { Signin } from "../signin";
import { Signup } from "../signup";

type AuthModalProps = {
  mode: "signin" | "signup";
  error: string;
  onClose: () => void;
  onAuthenticated: (user: AuthUser) => void;
  onShowSignin: () => void;
  onShowSignup: () => void;
};

export function AuthModal({
  mode,
  error,
  onClose,
  onAuthenticated,
  onShowSignin,
  onShowSignup,
}: AuthModalProps) {
  return (
    <div className="auth-modal-layer">
      <div className="auth-modal" role="dialog" aria-modal="true" aria-labelledby="auth-modal-title">
        <button className="auth-modal-close" type="button" onClick={onClose} aria-label="Close authentication modal">
          x
        </button>

        <div className="auth-modal-heading">
          <p className="empty-eyebrow">Welcome to</p>
          <h2 id="auth-modal-title">BravousAI</h2>
        </div>

        {error && <p className="auth-error">{error}</p>}

        {mode === "signin" ? (
          <Signin onAuthenticated={onAuthenticated} onShowSignup={onShowSignup} />
        ) : (
          <Signup onAuthenticated={onAuthenticated} onShowSignin={onShowSignin} />
        )}
      </div>
    </div>
  );
}
