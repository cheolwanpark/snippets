/**
 * Shared TypeScript interfaces for the repository embedder application
 */

/**
 * Represents a GitHub repository in various processing states
 */
export interface Repository {
  /** Unique identifier for the repository */
  id: string
  /** GitHub repository URL */
  url: string
  /** Repository name in format "owner/repo" */
  name: string
  /** Current processing status */
  status: "processing" | "completed" | "error"
  /** Timestamp when repository was added */
  addedAt: Date
  /** Processing progress percentage (0-100) */
  progress?: number
  /** Error message if status is "error" */
  error?: string
  /** Processing logs for status updates */
  logs?: string[]
}

/**
 * Represents a code search result from embedded repositories
 */
export interface SearchResult {
  /** Unique identifier for the search result */
  id: string
  /** Repository name where the code was found */
  repo: string
  /** File path within the repository */
  path: string
  /** Title/summary of the code snippet */
  title: string
  /** Description of what the code does */
  description: string
  /** Programming language of the code */
  language: string
  /** The actual code snippet */
  snippet: string
}

/**
 * Props for the RepositoryList component
 */
export interface RepositoryListProps {
  repositories: Repository[]
  onRemove: (id: string) => void
  formatTimeAgo: (date: Date) => string
  getStatusIcon: (status: Repository["status"]) => React.ReactNode
  getStatusBadge: (status: Repository["status"]) => React.ReactNode
}