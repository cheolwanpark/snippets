import React, { useMemo } from "react"
import { Badge } from "@/components/ui/badge"
import { Clock, CheckCircle, AlertCircle } from "lucide-react"
import type { Repository } from "@/types"

/**
 * Custom hook for repository utility functions and status handling
 */
export function useRepositoryUtils() {
  /**
   * Get the appropriate icon for a repository status
   */
  const getStatusIcon = useMemo(() => (status: Repository["status"]): React.ReactNode => {
    switch (status) {
      case "processing":
        return <Clock className="h-4 w-4 text-muted-foreground animate-spin" />
      case "completed":
        return <CheckCircle className="h-4 w-4 text-foreground" />
      case "error":
        return <AlertCircle className="h-4 w-4 text-destructive" />
    }
  }, [])

  /**
   * Get the appropriate badge for a repository status
   */
  const getStatusBadge = useMemo(() => (status: Repository["status"]): React.ReactNode => {
    switch (status) {
      case "processing":
        return <Badge variant="secondary">Processing</Badge>
      case "completed":
        return <Badge variant="default">Completed</Badge>
      case "error":
        return <Badge variant="destructive">Error</Badge>
    }
  }, [])

  /**
   * Format a date to a human-readable "time ago" string
   */
  const formatTimeAgo = useMemo(() => (date: Date) => {
    const now = new Date()
    const diffInMinutes = Math.floor((now.getTime() - date.getTime()) / (1000 * 60))

    if (diffInMinutes < 1) return "Just now"
    if (diffInMinutes < 60) return `${diffInMinutes}m ago`

    const diffInHours = Math.floor(diffInMinutes / 60)
    if (diffInHours < 24) return `${diffInHours}h ago`

    const diffInDays = Math.floor(diffInHours / 24)
    return `${diffInDays}d ago`
  }, [])

  /**
   * Filter repositories by status
   */
  const filterRepositoriesByStatus = useMemo(() => (
    repositories: Repository[],
    status?: Repository["status"]
  ) => {
    return status ? repositories.filter((repo) => repo.status === status) : repositories
  }, [])

  return {
    getStatusIcon,
    getStatusBadge,
    formatTimeAgo,
    filterRepositoriesByStatus,
  }
}