import React from "react";
import { LuSparkles, LuArrowRight, LuLayoutDashboard, LuBrainCircuit } from "react-icons/lu";

type LandingPageProps = {
  onSignIn: () => void;
  onSignUp: () => void;
};

export function LandingPage({ onSignIn, onSignUp }: LandingPageProps) {
  return (
    <div className="landing-page-scroll-wrapper">
      <section className="landing-page-container">
      <div className="landing-page-content">
        <div className="landing-badge">
          <LuSparkles size={14} />
          <span>BravousAI</span>
        </div>
        
        <h1 className="landing-hero-title">
          Your Intelligent<br />
          <span>Research Workspace</span>
        </h1>
        
        <p className="landing-hero-subtitle">
          Collaborate with AI specialists to plan, execute, and synthesize complex research tasks. 
          Everything you need in one powerful platform.
        </p>

        <div className="landing-actions">
          <button className="landing-btn-primary" onClick={onSignUp} suppressHydrationWarning={true}>
            Get Started
            <LuArrowRight size={18} />
          </button>
          <button className="landing-btn-secondary" onClick={onSignIn} suppressHydrationWarning={true}>
            Sign In
          </button>
        </div>

        <div className="landing-features">
          <div className="landing-feature-card">
            <div className="landing-feature-icon">
              <LuBrainCircuit size={24} />
            </div>
            <h3>Autonomous Agents</h3>
            <p>Our AI specialists handle research, writing, and analysis while you focus on the big picture.</p>
          </div>
          
          <div className="landing-feature-card">
            <div className="landing-feature-icon">
              <LuLayoutDashboard size={24} />
            </div>
            <h3>Organized Projects</h3>
            <p>Keep your conversations and research artifacts neatly organized in dedicated project spaces.</p>
          </div>
        </div>
      </div>
      </section>
    </div>
  );
}
