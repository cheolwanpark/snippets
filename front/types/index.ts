/**
 * TypeScript interfaces matching the Python FastAPI backend models
 */

// Request Models

/**
 * Request payload for creating/enqueueing a repository
 */
export interface RepoCreateRequest {
  /** GitHub repository URL */
  url: string
  /** Repository branch or ref to clone */
  branch?: string | null
  /** Include test directories when extracting */
  include_tests?: boolean
  /** Optional list of file extensions to include */
  extensions?: string[] | null
  /** Maximum file size (bytes) to consider */
  max_file_size?: number | null
  /** Optional repository identifier to store alongside snippets */
  repo_name?: string | null
}

// Response Models

/**
 * Base repository summary information
 */
export interface RepoSummary {
  /** Unique identifier for the repository */
  id: string
  /** GitHub repository URL */
  url: string
  /** Repository name identifier */
  repo_name: string | null
  /** Current processing status */
  status: string
  /** Processing status message */
  process_message: string | null
  /** Failure reason if processing failed */
  fail_reason: string | null
  /** Processing progress percentage (0-100) */
  progress: number | null
}

/**
 * Detailed repository response with timestamps and counts
 */
export interface RepoDetailResponse extends RepoSummary {
  /** ISO timestamp when repository was created */
  created_at: string | null
  /** ISO timestamp when repository was last updated */
  updated_at: string | null
  /** Number of snippets extracted from repository */
  snippet_count: number | null
}

/**
 * Response for repository creation requests
 */
export interface RepoCreateResponse extends RepoSummary {}

/**
 * Individual code snippet response
 */
export interface SnippetResponse {
  /** Title/summary of the code snippet */
  title: string
  /** Description of what the code does */
  description: string
  /** Programming language of the code */
  language: string
  /** The actual code content */
  code: string
  /** File path within the repository */
  path: string
  /** Repository name where the code was found */
  repo_name: string | null
  /** Repository URL where the code was found */
  repo_url: string | null
}

/**
 * Response for snippet search queries
 */
export interface SnippetQueryResponse {
  /** The search query that was executed */
  query: string
  /** Array of matching code snippets */
  results: SnippetResponse[]
}

// API Error Response
export interface ApiError {
  /** Error message */
  detail: string
  /** HTTP status code */
  status?: number
}

// Configuration types for dialogs
export interface RepoConfig {
  branch?: string
  extensions?: string[]
  max_file_size?: number
  include_tests?: boolean
}

export interface SearchConfig {
  repo_name?: string
  language?: string
  limit?: number
}

// Utility types for component props
export interface RepositoryListProps {
  repositories: RepoSummary[]
  onRemove: (id: string) => void
  formatTimeAgo: (date: string | null) => string
  getStatusIcon: (status: string) => React.ReactNode
  getStatusBadge: (status: string) => React.ReactNode
}