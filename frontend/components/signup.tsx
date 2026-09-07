"use client";

import { type FormEvent, useState } from "react";

import { type AuthUser, signup } from "../lib/api";

type SignupProps = {
  onAuthenticated: (user: AuthUser) => void;
  onShowSignin: () => void;
};

export function Signup({ onAuthenticated, onShowSignin }: SignupProps) {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setError("");
    setIsSubmitting(true);

    try {
      const user = await signup({
        username: username.trim(),
        email: email.trim(),
        password,
      });
      onAuthenticated(user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Signup failed.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className="auth-form" onSubmit={onSubmit}>
      <label className="auth-field">
        <span>Username</span>
        <input
          type="text"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          autoComplete="username"
          minLength={3}
          maxLength={128}
          required
        />
      </label>

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
          autoComplete="new-password"
          minLength={8}
          maxLength={128}
          required
        />
      </label>

      {error && <p className="auth-error">{error}</p>}

      <button className="send-button auth-submit" type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Creating..." : "Sign Up"}
      </button>

      <button className="link-button" type="button" onClick={onShowSignin}>
        Already have an account?
      </button>
    </form>
  );
}
