"use client";

import type { ResearchProject } from "./projects";
import { LuFolderPlus, LuSearch, LuSparkles, LuArrowRight, LuFolderOpen } from "react-icons/lu";

type ProjectHomeProps = {
  projects: ResearchProject[];
  searchValue: string;
  onSearchChange: (value: string) => void;
  onOpenProject: (projectId: string) => void;
  onCreateProject: () => void;
};

export function ProjectHome({
  projects,
  searchValue,
  onSearchChange,
  onOpenProject,
  onCreateProject,
}: ProjectHomeProps) {
  const normalizedSearch = searchValue.trim().toLowerCase();
  const visibleProjects = normalizedSearch
    ? projects.filter((project) =>
        `${project.title} ${project.description}`.toLowerCase().includes(normalizedSearch),
      )
    : projects;

  return (
    <section className="main-home-screen">
      <div className="main-home-heading">
        <div className="home-badge">
          <LuSparkles size={14} />
          <span>Research Workspace</span>
        </div>
        <h1>What project are we<br />working on?</h1>
        <p className="home-subtitle">Select an existing project or create a new one to get started.</p>
      </div>

      <div className="home-search-row">
        <div className="home-search-box">
          <LuSearch size={18} className="home-search-icon" />
          <input
            value={searchValue}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Search projects by name..."
            suppressHydrationWarning={true}
          />
        </div>
        <button
          className="home-create-btn"
          type="button"
          onClick={onCreateProject}
          suppressHydrationWarning={true}
        >
          <LuFolderPlus size={18} />
          <span>New Project</span>
        </button>
      </div>

      <div className="home-project-grid">
        {visibleProjects.map((project, index) => (
          <button
            key={project.id}
            type="button"
            className="home-project-card"
            onClick={() => onOpenProject(project.id)}
            style={{ animationDelay: `${index * 60}ms` }}
          >
            <div className="home-project-card-icon">
              <LuFolderOpen size={20} />
            </div>
            <div className="home-project-card-body">
              <strong>{project.title}</strong>
              <span>{project.description || "No project description yet."}</span>
            </div>
            <div className="home-project-card-arrow">
              <LuArrowRight size={16} />
            </div>
          </button>
        ))}
      </div>

      {visibleProjects.length === 0 && normalizedSearch && (
        <div className="home-empty-state">
          <p>No projects match &ldquo;{searchValue}&rdquo;</p>
        </div>
      )}
    </section>
  );
}
