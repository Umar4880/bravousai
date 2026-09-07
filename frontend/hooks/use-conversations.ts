"use client";

import { useCallback, useEffect, useState } from "react";
import {
  type AuthUser,
  type ConversationSummary,
  deleteConversation as apiDeleteConversation,
  getConversations as apiGetConversations,
  isValidUuid,
  renameConversation as apiRenameConversation,
} from "../lib/chat-api";
import { deleteStoredWorkflowTrace } from "../components/chat/storage";

export function useConversations(
  authUser: AuthUser | null,
  activeProjectId: string | null,
  onOpenConversation?: (conversationId: string) => void,
) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [conversationsByProject, setConversationsByProject] = useState<
    Record<string, ConversationSummary[]>
  >({});
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isLoadingConversations, setIsLoadingConversations] = useState(false);
  const [isMutatingChat, setIsMutatingChat] = useState(false);
  const [chatMenuId, setChatMenuId] = useState<string | null>(null);
  const [renamingChatId, setRenamingChatId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<ConversationSummary | null>(null);
  const [pendingConversationIds, setPendingConversationIds] = useState<Set<string>>(new Set());

  // Load conversations for active project
  const loadConversations = useCallback(
    async (projectId: string | null = activeProjectId) => {
      if (!authUser || !projectId) {
        setConversations([]);
        return;
      }

      if (!isValidUuid(authUser.user_id) || !isValidUuid(projectId)) {
        setConversations([]);
        return;
      }

      setIsLoadingConversations(true);
      try {
        const res = await apiGetConversations(authUser.user_id, projectId);
        setConversations(res.conversations);
        setConversationsByProject((prev) => ({
          ...prev,
          [projectId]: res.conversations,
        }));
      } catch (err) {
        console.error("Failed to load conversations:", err);
      } finally {
        setIsLoadingConversations(false);
      }
    },
    [authUser, activeProjectId],
  );

  // Load conversations for multiple projects (used on sidebar init)
  const loadAllProjectConversations = useCallback(
    async (projectIds: string[]) => {
      if (!authUser || projectIds.length === 0 || !isValidUuid(authUser.user_id)) return;

      const validProjectIds = projectIds.filter(isValidUuid);
      if (validProjectIds.length === 0) return;

      const promises = validProjectIds.map(async (pId) => {
        try {
          const res = await apiGetConversations(authUser.user_id, pId);
          return { projectId: pId, conversations: res.conversations };
        } catch {
          return { projectId: pId, conversations: [] };
        }
      });

      const results = await Promise.all(promises);
      const mapping: Record<string, ConversationSummary[]> = {};
      for (const item of results) {
        mapping[item.projectId] = item.conversations;
      }
      setConversationsByProject((prev) => ({ ...prev, ...mapping }));
    },
    [authUser],
  );

  useEffect(() => {
    if (authUser && activeProjectId) {
      void loadConversations(activeProjectId);
    } else {
      setConversations([]);
    }
  }, [authUser, activeProjectId, loadConversations]);

  const markConversationPending = useCallback((id: string) => {
    setPendingConversationIds((prev) => new Set(prev).add(id));
  }, []);

  const clearConversationPending = useCallback((id: string) => {
    setPendingConversationIds((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  }, []);

  const openConversation = useCallback(
    (targetId: string) => {
      setChatMenuId(null);
      setRenamingChatId(null);
      setConversationId(targetId);
      onOpenConversation?.(targetId);
    },
    [onOpenConversation],
  );

  // Rename Handlers
  const startRename = useCallback((chat: ConversationSummary) => {
    setChatMenuId(null);
    setRenamingChatId(chat.id);
    setRenameDraft(chat.title || "Untitled chat");
  }, []);

  const cancelRename = useCallback(() => {
    setRenamingChatId(null);
    setRenameDraft("");
  }, []);

  const commitRename = useCallback(
    async (chat: ConversationSummary) => {
      if (!authUser || isMutatingChat || renamingChatId !== chat.id) return;

      const nextTitle = renameDraft.trim().slice(0, 128);
      if (!nextTitle || nextTitle === chat.title) {
        cancelRename();
        return;
      }

      setIsMutatingChat(true);
      setRenamingChatId(null);
      setRenameDraft("");

      try {
        const updated = await apiRenameConversation(authUser.user_id, chat.id, nextTitle);
        const updatedTitle = updated.title;

        setConversations((prev) =>
          prev.map((item) => (item.id === chat.id ? { ...item, title: updatedTitle } : item)),
        );

        if (chat.project_id) {
          setConversationsByProject((prev) => {
            const list = prev[chat.project_id!] || [];
            return {
              ...prev,
              [chat.project_id!]: list.map((item) =>
                item.id === chat.id ? { ...item, title: updatedTitle } : item,
              ),
            };
          });
        }
      } catch (err) {
        console.error("Failed to rename conversation:", err);
        setRenamingChatId(chat.id);
        setRenameDraft(nextTitle);
      } finally {
        setIsMutatingChat(false);
      }
    },
    [authUser, isMutatingChat, renamingChatId, renameDraft, cancelRename],
  );

  // Delete Handlers
  const requestDelete = useCallback((chat: ConversationSummary) => {
    setChatMenuId(null);
    setDeleteTarget(chat);
  }, []);

  const cancelDelete = useCallback(() => {
    setDeleteTarget(null);
  }, []);

  const confirmDelete = useCallback(
    async (onResetCurrentChat?: () => void) => {
      if (!authUser || !deleteTarget || isMutatingChat) return;

      const targetId = deleteTarget.id;
      const targetProjectId = deleteTarget.project_id;
      setIsMutatingChat(true);

      try {
        await apiDeleteConversation(authUser.user_id, targetId);

        setConversations((prev) => prev.filter((c) => c.id !== targetId));
        if (targetProjectId) {
          setConversationsByProject((prev) => {
            const list = prev[targetProjectId] || [];
            return {
              ...prev,
              [targetProjectId]: list.filter((c) => c.id !== targetId),
            };
          });
        }

        if (typeof window !== "undefined") {
          deleteStoredWorkflowTrace(targetId);
        }

        clearConversationPending(targetId);

        if (targetId === conversationId) {
          setConversationId(null);
          onResetCurrentChat?.();
        }

        setDeleteTarget(null);
        setChatMenuId(null);
      } catch (err) {
        console.error("Failed to delete conversation:", err);
      } finally {
        setIsMutatingChat(false);
      }
    },
    [authUser, deleteTarget, isMutatingChat, conversationId, clearConversationPending],
  );

  // Add a newly created conversation to the state
  const addConversationLocally = useCallback(
    (item: ConversationSummary) => {
      setConversations((prev) => [item, ...prev.filter((c) => c.id !== item.id)]);
      if (item.project_id) {
        setConversationsByProject((prev) => {
          const list = prev[item.project_id!] || [];
          return {
            ...prev,
            [item.project_id!]: [item, ...list.filter((c) => c.id !== item.id)],
          };
        });
      }
    },
    [],
  );

  return {
    conversations,
    conversationsByProject,
    conversationId,
    setConversationId,
    isLoadingConversations,
    isMutatingChat,
    chatMenuId,
    setChatMenuId,
    renamingChatId,
    renameDraft,
    setRenameDraft,
    deleteTarget,
    pendingConversationIds,

    loadConversations,
    loadAllProjectConversations,
    openConversation,
    startRename,
    cancelRename,
    commitRename,
    requestDelete,
    cancelDelete,
    confirmDelete,
    markConversationPending,
    clearConversationPending,
    addConversationLocally,
  };
}
