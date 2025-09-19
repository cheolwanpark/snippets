"use client"

import React, { useState, useMemo, useCallback, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { GitBranch, Search, Code, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { RepositoryList } from "./repository-list"
import { useRepositoryUtils } from "@/hooks/useRepositoryUtils"
import { useRepositories } from "@/hooks/useRepositories"
import { RepoConfigDialog, SearchConfigDialog } from "./config-dialogs"
import type { RepoCreateRequest, RepoConfig, SearchConfig } from "@/types"

export function RepoEmbedder() {
  const [mode, setMode] = useState<"embed" | "query">("embed")
  const [repoUrl, setRepoUrl] = useState("")
  const [query, setQuery] = useState("")
  const [repoConfig, setRepoConfig] = useState<RepoConfig>({})
  const [searchConfig, setSearchConfig] = useState<SearchConfig>({ limit: 5 })

  // Real API integration
  const {
    repositories,
    loading,
    error,
    searchResults,
    searchLoading,
    searchError,
    createRepository,
    searchSnippets,
    clearSearch,
    clearError,
    deleteRepository,
  } = useRepositories()

  // Get utility functions from custom hook
  const { getStatusIcon, getStatusBadge, formatTimeAgo, filterRepositoriesByStatus } = useRepositoryUtils()

  // Show toast notifications for errors
  useEffect(() => {
    if (error) {
      toast.error(error)
      clearError()
    }
  }, [error, clearError])

  useEffect(() => {
    if (searchError) {
      toast.error(searchError)
      clearError()
    }
  }, [searchError, clearError])

  // Memoized event handlers
  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    if (!repoUrl.trim()) return

    try {
      const repoData: RepoCreateRequest = {
        url: repoUrl.trim(),
        ...repoConfig,
      }

      await createRepository(repoData)
      setRepoUrl("") // Clear form on success
      toast.success("Repository added for processing")
    } catch (error) {
      // Error is already handled by the hook
      console.error('Failed to create repository:', error)
    }
  }, [repoUrl, createRepository])

  const handleSearch = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return

    await searchSnippets(
      query.trim(),
      searchConfig.limit || 5,
      searchConfig.repo_name,
      searchConfig.language
    )
  }, [query, searchSnippets, searchConfig])

  // Show search completion toast
  useEffect(() => {
    if (searchResults && !searchLoading) {
      const count = searchResults.results.length
      if (count === 0) {
        toast(`No snippets found for "${searchResults.query}"`)
      } else {
        toast.success(`Found ${count} snippet${count === 1 ? '' : 's'} for "${searchResults.query}"`)
      }
    }
  }, [searchResults, searchLoading])

  const handleRemove = useCallback(async (id: string) => {
    try {
      await deleteRepository(id)
      toast.success("Repository deleted successfully")
    } catch (error) {
      // Error state is already set in the hook; keep console for dev visibility
      console.error('Failed to delete repository:', error)
    }
  }, [deleteRepository])

  // Memoized filtered repository lists
  const processingRepos = useMemo(() => filterRepositoriesByStatus(repositories, "processing"), [repositories, filterRepositoriesByStatus])
  const completedRepos = useMemo(() => filterRepositoriesByStatus(repositories, "completed"), [repositories, filterRepositoriesByStatus])
  const errorRepos = useMemo(() => filterRepositoriesByStatus(repositories, "error"), [repositories, filterRepositoriesByStatus])

  return (
    <div className="space-y-8">

      {mode === "embed" ? (
        <>
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <GitBranch className="h-5 w-5" />
                  Add Repository
                  <RepoConfigDialog config={repoConfig} onConfigChange={setRepoConfig} />
                </CardTitle>
                <div className="inline-flex gap-1 rounded-lg border p-1.5">
                  <Button
                    variant={mode === "embed" ? "default" : "ghost"}
                    size="sm"
                    onClick={() => {
                      setMode("embed")
                      clearSearch()
                    }}
                    className="rounded-md"
                  >
                    <GitBranch className="h-4 w-4 mr-2" />
                    Embed
                  </Button>
                  <Button
                    variant={mode === "query" ? "default" : "ghost"}
                    size="sm"
                    onClick={() => setMode("query")}
                    className="rounded-md"
                  >
                    <Search className="h-4 w-4 mr-2" />
                    Query
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="flex gap-4">
                <Input
                  type="url"
                  placeholder="https://github.com/username/repository"
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.target.value)}
                  className="flex-1"
                />
                <Button type="submit" disabled={!repoUrl.trim() || loading}>
                  {loading ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Creating...
                    </>
                  ) : (
                    "Embed Repository"
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Tabs defaultValue="all" className="w-full">
            <TabsList className="grid w-full grid-cols-4">
              <TabsTrigger value="all">All ({repositories.length})</TabsTrigger>
              <TabsTrigger value="processing">Processing ({processingRepos.length})</TabsTrigger>
              <TabsTrigger value="completed">Completed ({completedRepos.length})</TabsTrigger>
              <TabsTrigger value="error">Errors ({errorRepos.length})</TabsTrigger>
            </TabsList>

            <TabsContent value="all" className="space-y-4">
              <RepositoryList
                repositories={repositories}
                onRemove={handleRemove}
                formatTimeAgo={formatTimeAgo}
                getStatusIcon={getStatusIcon}
                getStatusBadge={getStatusBadge}
              />
            </TabsContent>

            <TabsContent value="processing" className="space-y-4">
              <RepositoryList
                repositories={processingRepos}
                onRemove={handleRemove}
                formatTimeAgo={formatTimeAgo}
                getStatusIcon={getStatusIcon}
                getStatusBadge={getStatusBadge}
              />
            </TabsContent>

            <TabsContent value="completed" className="space-y-4">
              <RepositoryList
                repositories={completedRepos}
                onRemove={handleRemove}
                formatTimeAgo={formatTimeAgo}
                getStatusIcon={getStatusIcon}
                getStatusBadge={getStatusBadge}
              />
            </TabsContent>

            <TabsContent value="error" className="space-y-4">
              <RepositoryList
                repositories={errorRepos}
                onRemove={handleRemove}
                formatTimeAgo={formatTimeAgo}
                getStatusIcon={getStatusIcon}
                getStatusBadge={getStatusBadge}
              />
            </TabsContent>
          </Tabs>
        </>
      ) : (
        <>
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <Search className="h-5 w-5" />
                  Search Code Snippets
                  <SearchConfigDialog config={searchConfig} onConfigChange={setSearchConfig} />
                </CardTitle>
                <div className="inline-flex gap-1 rounded-lg border p-1.5">
                  <Button
                    variant={mode === "embed" ? "default" : "ghost"}
                    size="sm"
                    onClick={() => {
                      setMode("embed")
                      clearSearch()
                    }}
                    className="rounded-md"
                  >
                    <GitBranch className="h-4 w-4 mr-2" />
                    Embed
                  </Button>
                  <Button
                    variant={mode === "query" ? "default" : "ghost"}
                    size="sm"
                    onClick={() => setMode("query")}
                    className="rounded-md"
                  >
                    <Search className="h-4 w-4 mr-2" />
                    Query
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSearch} className="flex gap-4">
                <Input
                  type="text"
                  placeholder="Search for code snippets, functions, or patterns..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="flex-1"
                />
                <Button type="submit" disabled={!query.trim() || searchLoading}>
                  {searchLoading ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Searching...
                    </>
                  ) : (
                    "Search"
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>

          <div className="space-y-4">
            {!searchResults ? (
              <Card>
                <CardContent className="flex flex-col items-center justify-center py-12 text-center">
                  <Search className="h-12 w-12 text-muted-foreground mb-4" />
                  <h3 className="text-lg font-medium mb-2">Search Code Snippets</h3>
                  <p className="text-muted-foreground max-w-md">
                    Enter a query above to search through embedded code repositories for relevant snippets, functions,
                    and patterns.
                  </p>
                </CardContent>
              </Card>
            ) : searchResults.results.length === 0 ? (
              <Card>
                <CardContent className="flex flex-col items-center justify-center py-12 text-center">
                  <Search className="h-12 w-12 text-muted-foreground mb-4" />
                  <h3 className="text-lg font-medium mb-2">No Results Found</h3>
                  <p className="text-muted-foreground max-w-md">
                    No code snippets found for "{searchResults.query}". Try a different search term.
                  </p>
                </CardContent>
              </Card>
            ) : (
              <>
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <span>Found {searchResults.results.length} results for "{searchResults.query}"</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={clearSearch}
                    className="h-6 px-2"
                  >
                    Clear
                  </Button>
                </div>
                {searchResults.results.map((result, index) => (
                  <Card key={index}>
                    <CardHeader className="pb-3">
                      <div className="flex items-start justify-between">
                        <div className="space-y-1">
                          <CardTitle className="text-base">{result.title}</CardTitle>
                          <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <Code className="h-3 w-3" />
                            <span>{result.repo_name}</span>
                            <span>•</span>
                            <span>{result.path}</span>
                          </div>
                        </div>
                        <Badge variant="outline">{result.language}</Badge>
                      </div>
                      <p className="text-sm text-muted-foreground">{result.description}</p>
                    </CardHeader>
                    <CardContent>
                      <div className="rounded-md bg-muted p-4">
                        <pre className="text-sm overflow-x-auto">
                          <code>{result.code}</code>
                        </pre>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </>
            )}
          </div>
        </>
      )}
    </div>
  )
}
