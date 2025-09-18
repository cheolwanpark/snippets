import type { Repository, SearchResult } from "@/types"

/**
 * Simplified mock repositories for demonstration purposes
 */
export const mockRepositories: Repository[] = [
  {
    id: "1",
    url: "https://github.com/vercel/next.js",
    name: "vercel/next.js",
    status: "completed",
    addedAt: new Date(Date.now() - 3600000), // 1 hour ago
  },
  {
    id: "2",
    url: "https://github.com/facebook/react",
    name: "facebook/react",
    status: "processing",
    addedAt: new Date(Date.now() - 1800000), // 30 minutes ago
    progress: 65,
    logs: [
      "Analyzing file structure...",
      "Processing TypeScript files...",
      "Current progress: 65%",
    ],
  },
]

/**
 * Simplified mock search results for demonstration purposes
 */
export const mockSearchResults: SearchResult[] = [
  {
    id: "1",
    repo: "vercel/next.js",
    path: "packages/next/src/server/app-render.tsx",
    title: "App Router Rendering",
    description: "Core rendering logic for Next.js App Router",
    language: "TypeScript",
    snippet: `export async function renderToHTMLOrFlight(
  req: IncomingMessage,
  res: ServerResponse,
  pathname: string
) {
  const renderOpts = {
    supportsDynamicHTML: true,
    runtime: 'nodejs'
  }
  return await renderToString(tree, renderOpts)
}`,
  },
  {
    id: "2",
    repo: "facebook/react",
    path: "packages/react-dom/src/server/ReactDOMServer.js",
    title: "Server-Side Rendering",
    description: "Server rendering implementation for React",
    language: "JavaScript",
    snippet: `function renderToString(element, options) {
  const request = createRequest(
    element,
    createResponseState(),
    createRootFormatContext()
  )
  return readResult(request)
}`,
  },
]