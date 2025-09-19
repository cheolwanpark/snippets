"use client"

import { useState, useEffect, useCallback } from "react"
import type { RepoSummary, RepoCreateRequest, SnippetQueryResponse } from "@/types"

interface UseRepositoriesState {
  repositories: RepoSummary[]
  loading: boolean
  error: string | null
  searchResults: SnippetQueryResponse | null
  searchLoading: boolean
  searchError: string | null
}

interface UseRepositoriesActions {
  fetchRepositories: () => Promise<void>
  createRepository: (data: RepoCreateRequest) => Promise<void>
  searchSnippets: (query: string, limit?: number, repoName?: string, language?: string) => Promise<void>
  clearSearch: () => void
  clearError: () => void
  refreshRepository: (id: string) => Promise<void>
  deleteRepository: (id: string) => Promise<void>
}

/**
 * Custom hook for managing repository state and API interactions
 */
export function useRepositories(): UseRepositoriesState & UseRepositoriesActions {
  const [state, setState] = useState<UseRepositoriesState>({
    repositories: [],
    loading: false,
    error: null,
    searchResults: null,
    searchLoading: false,
    searchError: null,
  })

  /**
   * Fetch all repositories
   */
  const fetchRepositories = useCallback(async () => {
    setState(prev => ({ ...prev, loading: true, error: null }))

    try {
      const response = await fetch('/api/repositories')
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      const repositories = await response.json()
      setState(prev => ({
        ...prev,
        repositories,
        loading: false,
      }))
    } catch (error) {
      const errorMessage = error instanceof Error
        ? error.message
        : 'Failed to fetch repositories'

      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage,
      }))
    }
  }, [])

  /**
   * Create a new repository
   */
  const createRepository = useCallback(async (data: RepoCreateRequest) => {
    setState(prev => ({ ...prev, loading: true, error: null }))

    try {
      const response = await fetch('/api/repositories', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }))
        throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
      }
      const newRepo = await response.json()
      setState(prev => ({
        ...prev,
        repositories: [newRepo, ...prev.repositories],
        loading: false,
      }))

      // Auto-refresh repositories to get updated status
      setTimeout(fetchRepositories, 2000)
    } catch (error) {
      const errorMessage = error instanceof Error
        ? error.message
        : 'Failed to create repository'

      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage,
      }))
      throw error // Re-throw to allow component to handle
    }
  }, [fetchRepositories])

  /**
   * Search code snippets
   */
  const searchSnippets = useCallback(async (query: string, limit: number = 5, repoName?: string, language?: string) => {
    setState(prev => ({ ...prev, searchLoading: true, searchError: null }))

    try {
      const params = new URLSearchParams({
        query,
        limit: limit.toString(),
      })

      if (repoName) {
        params.set('repo_name', repoName)
      }
      if (language) {
        params.set('language', language)
      }

      const response = await fetch(`/api/snippets?${params}`)
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      const results = await response.json()
      setState(prev => ({
        ...prev,
        searchResults: results,
        searchLoading: false,
      }))
    } catch (error) {
      const errorMessage = error instanceof Error
        ? error.message
        : 'Failed to search snippets'

      setState(prev => ({
        ...prev,
        searchLoading: false,
        searchError: errorMessage,
      }))
    }
  }, [])

  /**
   * Clear search results
   */
  const clearSearch = useCallback(() => {
    setState(prev => ({
      ...prev,
      searchResults: null,
      searchError: null,
    }))
  }, [])

  /**
   * Clear error state
   */
  const clearError = useCallback(() => {
    setState(prev => ({ ...prev, error: null, searchError: null }))
  }, [])

  /**
   * Refresh a specific repository (useful for polling status)
   */
  const refreshRepository = useCallback(async (id: string) => {
    try {
      const response = await fetch(`/api/repositories/${id}`)
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      const updatedRepo = await response.json()
      setState(prev => ({
        ...prev,
        repositories: prev.repositories.map(repo =>
          repo.id === id ? updatedRepo : repo
        ),
      }))
    } catch (error) {
      console.error('Failed to refresh repository:', error)
      // Don't update error state for background refreshes
    }
  }, [])

  /**
   * Delete a repository by ID
   */
  const deleteRepository = useCallback(async (id: string) => {
    setState(prev => ({ ...prev, loading: true, error: null }))

    try {
      const response = await fetch(`/api/repositories/${id}`, { method: 'DELETE' })
      if (!response.ok && response.status !== 204) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }))
        throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
      }

      setState(prev => ({
        ...prev,
        repositories: prev.repositories.filter(repo => repo.id !== id),
        loading: false,
      }))
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to delete repository'
      setState(prev => ({ ...prev, loading: false, error: errorMessage }))
      throw error
    }
  }, [])

  /**
   * Auto-refresh processing repositories
   */
  useEffect(() => {
    const processingRepos = state.repositories.filter(repo =>
      repo.status.toLowerCase() === 'processing' ||
      repo.status.toLowerCase() === 'pending'
    )

    if (processingRepos.length === 0) return

    const interval = setInterval(() => {
      processingRepos.forEach(repo => {
        refreshRepository(repo.id)
      })
    }, 5000) // Poll every 5 seconds

    return () => clearInterval(interval)
  }, [state.repositories, refreshRepository])

  /**
   * Initial load
   */
  useEffect(() => {
    fetchRepositories()
  }, [fetchRepositories])

  return {
    ...state,
    fetchRepositories,
    createRepository,
    searchSnippets,
    clearSearch,
    clearError,
    refreshRepository,
    deleteRepository,
  }
}
