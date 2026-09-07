"use client";

import type { AuthUser } from "../../lib/api";
import type { ResearchProject } from "./projects";

type ProjectHeaderProps = {
  authUser: AuthUser | null;
  project: ResearchProject;
  onBack: () => void;
  onSignIn: () => void;
  onSignUp: () => void;
  onSignOut: () => void;
};

export function ProjectHeader({ authUser, project, onBack, onSignIn, onSignUp, onSignOut }: ProjectHeaderProps) {
  return (
    <header className="project-header">
      <div className="project-title-row">
        <div>
          <h1>{project.title}</h1>
          <p>{project.description || "Add project instructions and files, then start a focused research chat."}</p>
          <button className="show-more-button" type="button">
            Show more
          </button>
        </div>
      </div>
    </header>
  );
}
