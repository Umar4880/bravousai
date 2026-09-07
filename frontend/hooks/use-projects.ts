"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  type AuthUser,
  createProject as apiCreateProject,
  deleteProject as apiDeleteProject,
  deleteProjectFile as apiDeleteProjectFile,
  getProjects as apiGetProjects,
  updateProject as apiUpdateProject,
  updateProjectInstructions as apiUpdateProjectInstructions,
  uploadProjectFile as apiUploadProjectFile,
} from "../lib/chat-api";
import {
  ACTIVE_PROJECT_STORAGE_KEY,
  DEFAULT_PROJECTS,
  type ResearchProject,
} from "../components/chat/projects";

export function useProjects(authUser: AuthUser | null) {
  const [projects, setProjects] = useState<ResearchProject[]>(() =>
    authUser ? [] : DEFAULT_PROJECTS,
  );
  const [activeProjectId, setActiveProjectIdState] = useState<string | null>(null);
  const [isLoadingProjects, setIsLoadingProjects] = useState(false);
  const [projectSearch, setProjectSearch] = useState("");

  // Create Modal
  const [isCreateProjectOpen, setIsCreateProjectOpen] = useState(false);
  const [projectTitleDraft, setProjectTitleDraft] = useState("");
  const [projectDescriptionDraft, setProjectDescriptionDraft] = useState("");

  // Rename Project
  const [renamingProjectId, setRenamingProjectId] = useState<string | null>(null);
  const [renameProjectDraft, setRenameProjectDraft] = useState("");

  // Delete Project Modal
  const [deleteProjectTarget, setDeleteProjectTarget] = useState<ResearchProject | null>(null);
  const [isMutatingProject, setIsMutatingProject] = useState(false);

  // Sync active project id with localStorage
  const setActiveProjectId = useCallback((id: string | null) => {
    setActiveProjectIdState(id);
    if (typeof window !== "undefined") {
      if (id) {
        window.localStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, id);
      } else {
        window.localStorage.removeItem(ACTIVE_PROJECT_STORAGE_KEY);
      }
    }
  }, []);

  // Fetch projects when authUser changes
  useEffect(() => {
    let isCancelled = false;

    async function load() {
      if (!authUser) {
        setProjects(DEFAULT_PROJECTS);
        const stored = typeof window !== "undefined" ? window.localStorage.getItem(ACTIVE_PROJECT_STORAGE_KEY) : null;
        if (stored && DEFAULT_PROJECTS.some((p) => p.id === stored)) {
          setActiveProjectIdState(stored);
        } else {
          setActiveProjectIdState(DEFAULT_PROJECTS[0]?.id ?? null);
        }
        return;
      }

      setIsLoadingProjects(true);
      try {
        const res = await apiGetProjects(authUser.user_id);
        if (isCancelled) return;

        const serverProjects: ResearchProject[] = res.projects.map((p) => ({
          ...p,
          files: p.files.map((f) => ({
            ...f,
            status: f.status || "uploaded",
          })),
        }));

        setProjects(serverProjects);

        const stored = typeof window !== "undefined" ? window.localStorage.getItem(ACTIVE_PROJECT_STORAGE_KEY) : null;
        if (stored && serverProjects.some((p) => p.id === stored)) {
          setActiveProjectIdState(stored);
        } else {
          setActiveProjectIdState(serverProjects[0]?.id ?? null);
        }
      } catch (err) {
        console.error("Failed to load projects:", err);
      } finally {
        if (!isCancelled) {
          setIsLoadingProjects(false);
        }
      }
    }

    void load();
    return () => {
      isCancelled = true;
    };
  }, [authUser]);

  const activeProject = useMemo(() => {
    return projects.find((p) => p.id === activeProjectId) ?? projects[0] ?? null;
  }, [projects, activeProjectId]);

  // Project Creation
  const openCreateModal = useCallback(() => {
    setProjectTitleDraft("");
    setProjectDescriptionDraft("");
    setIsCreateProjectOpen(true);
  }, []);

  const closeCreateModal = useCallback(() => {
    setIsCreateProjectOpen(false);
    setProjectTitleDraft("");
    setProjectDescriptionDraft("");
  }, []);

  const createProjectFromDraft = useCallback(async (): Promise<string | null> => {
    const trimmedTitle = projectTitleDraft.trim();
    if (!trimmedTitle) return null;

    if (!authUser) {
      const newProj: ResearchProject = {
        id: `guest-proj-${Date.now().toString(36)}`,
        user_id: "",
        title: trimmedTitle,
        description: projectDescriptionDraft.trim(),
        instructions: "",
        files: [],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      setProjects((prev) => [newProj, ...prev]);
      setActiveProjectId(newProj.id);
      closeCreateModal();
      return newProj.id;
    }

    setIsMutatingProject(true);
    try {
      const created = await apiCreateProject({
        user_id: authUser.user_id,
        title: trimmedTitle,
        description: projectDescriptionDraft.trim(),
      });

      const newProj: ResearchProject = {
        ...created,
        files: created.files.map((f) => ({
          ...f,
          status: f.status || "uploaded",
        })),
      };

      setProjects((prev) => [newProj, ...prev]);
      setActiveProjectId(newProj.id);
      closeCreateModal();
      return newProj.id;
    } catch (err) {
      console.error("Failed to create project:", err);
      return null;
    } finally {
      setIsMutatingProject(false);
    }
  }, [projectTitleDraft, projectDescriptionDraft, authUser, setActiveProjectId, closeCreateModal]);

  // Project Rename
  const startRenameProject = useCallback((project: ResearchProject) => {
    setRenamingProjectId(project.id);
    setRenameProjectDraft(project.title);
  }, []);

  const cancelRenameProject = useCallback(() => {
    setRenamingProjectId(null);
    setRenameProjectDraft("");
  }, []);

  const commitRenameProject = useCallback(async (project: ResearchProject) => {
    const trimmed = renameProjectDraft.trim();
    if (!trimmed || trimmed === project.title) {
      cancelRenameProject();
      return;
    }

    if (!authUser) {
      setProjects((prev) =>
        prev.map((p) => (p.id === project.id ? { ...p, title: trimmed } : p)),
      );
      cancelRenameProject();
      return;
    }

    setIsMutatingProject(true);
    try {
      const updated = await apiUpdateProject(authUser.user_id, project.id, {
        title: trimmed,
      });
      setProjects((prev) =>
        prev.map((p) => (p.id === project.id ? { ...p, title: updated.title } : p)),
      );
      cancelRenameProject();
    } catch (err) {
      console.error("Failed to rename project:", err);
    } finally {
      setIsMutatingProject(false);
    }
  }, [renameProjectDraft, authUser, cancelRenameProject]);

  // Project Delete
  const requestDeleteProject = useCallback((project: ResearchProject) => {
    setDeleteProjectTarget(project);
  }, []);

  const cancelDeleteProject = useCallback(() => {
    setDeleteProjectTarget(null);
  }, []);

  const confirmDeleteProject = useCallback(async () => {
    if (!deleteProjectTarget) return;

    if (!authUser) {
      setProjects((prev) => prev.filter((p) => p.id !== deleteProjectTarget.id));
      if (activeProjectId === deleteProjectTarget.id) {
        const remaining = projects.filter((p) => p.id !== deleteProjectTarget.id);
        setActiveProjectId(remaining[0]?.id ?? null);
      }
      setDeleteProjectTarget(null);
      return;
    }

    setIsMutatingProject(true);
    try {
      await apiDeleteProject(authUser.user_id, deleteProjectTarget.id);
      setProjects((prev) => prev.filter((p) => p.id !== deleteProjectTarget.id));
      if (activeProjectId === deleteProjectTarget.id) {
        const remaining = projects.filter((p) => p.id !== deleteProjectTarget.id);
        setActiveProjectId(remaining[0]?.id ?? null);
      }
      setDeleteProjectTarget(null);
    } catch (err) {
      console.error("Failed to delete project:", err);
    } finally {
      setIsMutatingProject(false);
    }
  }, [deleteProjectTarget, authUser, activeProjectId, projects, setActiveProjectId]);

  // Project Instructions
  const updateActiveProjectInstructions = useCallback(async (instructions: string) => {
    if (!activeProject) return;

    if (!authUser) {
      setProjects((prev) =>
        prev.map((p) => (p.id === activeProject.id ? { ...p, instructions } : p)),
      );
      return;
    }

    try {
      const updated = await apiUpdateProjectInstructions(
        authUser.user_id,
        activeProject.id,
        instructions,
      );
      setProjects((prev) =>
        prev.map((p) => (p.id === activeProject.id ? { ...p, instructions: updated.instructions } : p)),
      );
    } catch (err) {
      console.error("Failed to update instructions:", err);
    }
  }, [activeProject, authUser]);

  // Project Files
  const addActiveProjectFiles = useCallback(async (files: File[]) => {
    if (!activeProject || !authUser) return;

    for (const file of files) {
      try {
        const uploaded = await apiUploadProjectFile(authUser.user_id, activeProject.id, file);
        setProjects((prev) =>
          prev.map((p) => {
            if (p.id !== activeProject.id) return p;
            return {
              ...p,
              files: [
                ...p.files,
                {
                  ...uploaded,
                  status: uploaded.status || "uploaded",
                },
              ],
            };
          }),
        );
      } catch (err) {
        console.error("Failed to upload file:", err);
      }
    }
  }, [activeProject, authUser]);

  const deleteActiveProjectFile = useCallback(async (fileId: string) => {
    if (!activeProject || !authUser) return;

    try {
      await apiDeleteProjectFile(authUser.user_id, activeProject.id, fileId);
      setProjects((prev) =>
        prev.map((p) => {
          if (p.id !== activeProject.id) return p;
          return {
            ...p,
            files: p.files.filter((f) => f.id !== fileId),
          };
        }),
      );
    } catch (err) {
      console.error("Failed to delete file:", err);
    }
  }, [activeProject, authUser]);

  return {
    projects,
    activeProjectId,
    activeProject,
    isLoadingProjects,
    projectSearch,
    setProjectSearch,
    setActiveProjectId,

    isCreateProjectOpen,
    projectTitleDraft,
    projectDescriptionDraft,
    setProjectTitleDraft,
    setProjectDescriptionDraft,
    openCreateModal,
    closeCreateModal,
    createProjectFromDraft,

    renamingProjectId,
    renameProjectDraft,
    setRenameProjectDraft,
    startRenameProject,
    cancelRenameProject,
    commitRenameProject,

    deleteProjectTarget,
    isMutatingProject,
    requestDeleteProject,
    cancelDeleteProject,
    confirmDeleteProject,

    updateActiveProjectInstructions,
    addActiveProjectFiles,
    deleteActiveProjectFile,
  };
}
