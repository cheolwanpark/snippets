"use client"

import React, { useState, useMemo, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { GitBranch, Search, Code } from "lucide-react"
import { RepositoryList } from "./repository-list"
import { useRepositoryUtils } from "@/hooks/useRepositoryUtils"
import { mockRepositories, mockSearchResults } from "@/constants/mockData"
import type { Repository, SearchResult } from "@/types"

export function RepoEmbedder() {
  const [mode, setMode] = useState<"embed" | "query">("embed")
  const [repoUrl, setRepoUrl] = useState("")
  const [query, setQuery] = useState("")

  // Use simplified mock data from constants
  const repositories = mockRepositories
  const searchResults = mockSearchResults

  // Get utility functions from custom hook
  const { getStatusIcon, getStatusBadge, formatTimeAgo, filterRepositoriesByStatus } = useRepositoryUtils()

  // Memoized event handlers
  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault()
    // Demo functionality - prevent form submission
  }, [])

  const handleSearch = useCallback((e: React.FormEvent) => {
    e.preventDefault()
    // Demo functionality - prevent form submission
  }, [])

  const handleRemove = useCallback((id: string) => {
    // Demo functionality - no actual removal
  }, [])

  // Memoized filtered repository lists
  const processingRepos = useMemo(() => filterRepositoriesByStatus(repositories, "processing"), [repositories, filterRepositoriesByStatus])
  const completedRepos = useMemo(() => filterRepositoriesByStatus(repositories, "completed"), [repositories, filterRepositoriesByStatus])
  const errorRepos = useMemo(() => filterRepositoriesByStatus(repositories, "error"), [repositories, filterRepositoriesByStatus])

  return (
    <div className="space-y-8">
      <div className="flex justify-center">
        <div className="inline-flex rounded-lg border p-1">
          <Button
            variant={mode === "embed" ? "default" : "ghost"}
            size="sm"
            onClick={() => setMode("embed")}
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

      {mode === "embed" ? (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <GitBranch className="h-5 w-5" />
                Add Repository
              </CardTitle>
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
                <Button type="submit" disabled={!repoUrl.trim()}>
                  Embed Repository
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
              <CardTitle className="flex items-center gap-2">
                <Search className="h-5 w-5" />
                Search Code Snippets
              </CardTitle>
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
                <Button type="submit" disabled={!query.trim()}>
                  Search
                </Button>
              </form>
            </CardContent>
          </Card>

          <div className="space-y-4">
            {!query ? (
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
            ) : (
              searchResults.map((result) => (
                <Card key={result.id}>
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between">
                      <div className="space-y-1">
                        <CardTitle className="text-base">{result.title}</CardTitle>
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <Code className="h-3 w-3" />
                          <span>{result.repo}</span>
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
                        <code>{result.snippet}</code>
                      </pre>
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        </>
      )}
    </div>
  )
}