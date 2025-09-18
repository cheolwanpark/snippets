import React, { useMemo } from "react"
import { Badge } from "@/components/ui/badge"
import { Clock, CheckCircle, AlertCircle } from "lucide-react"
import type { RepoSummary } from "@/types"

/**
 * Custom hook for repository utility functions and status handling
 */
export function useRepositoryUtils() {
  /**
   * Get the appropriate icon for a repository status
   */
  const getStatusIcon = useMemo(() => (status: string): React.ReactNode => {
    switch (status.toLowerCase()) {
      case "pending":
      case "processing":
      case "in_progress":
        return <Clock className="h-4 w-4 text-muted-foreground animate-spin" />
      case "completed":
      case "done":
        return <CheckCircle className="h-4 w-4 text-foreground" />
      case "failed":
      case "error":
        return <AlertCircle className="h-4 w-4 text-destructive" />
      default:
        return <Clock className="h-4 w-4 text-muted-foreground" />
    }
  }, [])

  /**
   * Get the appropriate badge for a repository status
   */
  const getStatusBadge = useMemo(() => (status: string): React.ReactNode => {
    switch (status.toLowerCase()) {
      case "pending":
        return <Badge variant="secondary">Pending</Badge>
      case "processing":
      case "in_progress":
        return <Badge variant="secondary">Processing</Badge>
      case "completed":
      case "done":
        return <Badge variant="default">Completed</Badge>
      case "failed":
      case "error":
        return <Badge variant="destructive">Error</Badge>
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }, [])

  /**
   * Format a date to a human-readable "time ago" string
   */
  const formatTimeAgo = useMemo(() => (dateString: string | null) => {
    if (!dateString) return "Unknown"

    try {
      const date = new Date(dateString)
      const now = new Date()
      const diffInMinutes = Math.floor((now.getTime() - date.getTime()) / (1000 * 60))

      if (diffInMinutes < 1) return "Just now"
      if (diffInMinutes < 60) return `${diffInMinutes}m ago`

      const diffInHours = Math.floor(diffInMinutes / 60)
      if (diffInHours < 24) return `${diffInHours}h ago`

      const diffInDays = Math.floor(diffInHours / 24)
      return `${diffInDays}d ago`
    } catch {
      return "Unknown"
    }
  }, [])

  /**
   * Filter repositories by status
   */
  const filterRepositoriesByStatus = useMemo(() => (
    repositories: RepoSummary[],
    status?: string
  ) => {
    return status ? repositories.filter((repo) => repo.status.toLowerCase() === status.toLowerCase()) : repositories
  }, [])

  return {
    getStatusIcon,
    getStatusBadge,
    formatTimeAgo,
    filterRepositoriesByStatus,
  }
}