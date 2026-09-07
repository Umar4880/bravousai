export type ParsedAppRoute =
  | { type: "home" }
  | { type: "project"; projectId: string }
  | { type: "chat"; chatId: string };

export function projectHomePath(): string {
  return "/project";
}

export function projectPath(projectId: string): string {
  return `/project/${encodeURIComponent(projectId)}`;
}

export function chatPath(chatId: string): string {
  return `/project/c/${encodeURIComponent(chatId)}`;
}

export function parseAppRoute(pathname: string): ParsedAppRoute {
  const normalized = pathname.replace(/\/+$/, "") || "/";

  if (normalized === "/" || normalized === "/project") {
    return { type: "home" };
  }

  const chatMatch = normalized.match(/^\/project\/c\/([^/]+)$/);
  if (chatMatch?.[1]) {
    return { type: "chat", chatId: decodeURIComponent(chatMatch[1]) };
  }

  const projectMatch = normalized.match(/^\/project\/([^/]+)$/);
  if (projectMatch?.[1]) {
    return { type: "project", projectId: decodeURIComponent(projectMatch[1]) };
  }

  const legacyChatMatch = normalized.match(/^\/c\/([^/]+)$/);
  if (legacyChatMatch?.[1]) {
    return { type: "chat", chatId: decodeURIComponent(legacyChatMatch[1]) };
  }

  return { type: "home" };
}
