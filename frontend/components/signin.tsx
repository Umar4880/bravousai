"use client";

import { type FormEvent, useState } from "react";

import { type AuthUser, signin } from "../lib/api";

type SigninProps = {
  onAuthenticated: (user: AuthUser) => void;
  onShowSignup: () => void;
};

export function Signin({ onAuthenticated, onShowSignup }: SigninProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setError("");
    setIsSubmitting(true);

    try {
      const user = await signin({
        email: email.trim(),
        password,
      });
      onAuthenticated(user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Signin failed.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className="auth-form" onSubmit={onSubmit}>
      <label className="auth-field">
        <span>Email</span>
        <input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          autoComplete="email"
          required
        />
      </label>

      <label className="auth-field">
        <span>Password</span>
        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="current-password"
          required
        />
      </label>

      {error && <p className="auth-error">{error}</p>}

      <button className="send-button auth-submit" type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Signing in..." : "Sign In"}
      </button>

      <button className="link-button" type="button" onClick={onShowSignup}>
        Create an account
      </button>
    </form>
  );
}
