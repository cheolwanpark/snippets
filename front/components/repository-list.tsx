"use client"

import React, { useState, memo } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { Trash2, ChevronDown, ChevronUp } from "lucide-react"
import type { RepositoryListProps } from "@/types"

const RepositoryListComponent = ({
  repositories,
  onRemove,
  formatTimeAgo,
  getStatusIcon,
  getStatusBadge,
}: RepositoryListProps) => {
  const [expandedOutputs, setExpandedOutputs] = useState<Set<string>>(new Set())

  const toggleOutput = (repoId: string) => {
    const newExpanded = new Set(expandedOutputs)
    if (newExpanded.has(repoId)) {
      newExpanded.delete(repoId)
    } else {
      newExpanded.add(repoId)
    }
    setExpandedOutputs(newExpanded)
  }

  if (repositories.length === 0) {
    return (
      <Card className="bg-card border-border">
        <CardContent className="py-12 text-center">
          <p className="text-muted-foreground">No repositories found</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-3">
      {repositories.map((repo) => (
        <Card key={repo.id} className="bg-card border-border">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3 mb-2">
                  {getStatusIcon(repo.status)}
                  <h3 className="font-mono text-sm font-medium text-card-foreground truncate">{repo.name}</h3>
                  {getStatusBadge(repo.status)}
                </div>

                <p className="text-xs text-muted-foreground mb-2 truncate">{repo.url}</p>

                {repo.status === "processing" && repo.progress !== undefined && (
                  <div className="mb-2">
                    <Progress value={repo.progress} className="h-2" />
                    <p className="text-xs text-muted-foreground mt-1">{repo.progress}% complete</p>
                  </div>
                )}

                {repo.status === "error" && repo.error && (
                  <p className="text-xs text-destructive mb-2">Error: {repo.error}</p>
                )}

                {repo.status === "processing" && repo.logs && repo.logs.length > 0 && (
                  <div className="mt-3 border-t border-border pt-3">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => toggleOutput(repo.id)}
                      className="h-6 px-2 text-xs text-muted-foreground hover:text-foreground mb-2"
                    >
                      {expandedOutputs.has(repo.id) ? (
                        <>
                          <ChevronUp className="h-3 w-3 mr-1" />
                          Hide Output
                        </>
                      ) : (
                        <>
                          <ChevronDown className="h-3 w-3 mr-1" />
                          Show Output ({repo.logs.length})
                        </>
                      )}
                    </Button>

                    {expandedOutputs.has(repo.id) && (
                      <div className="bg-muted/30 rounded-md p-3 max-h-32 overflow-y-auto">
                        <div className="space-y-1">
                          {repo.logs.slice(-5).map((log, index) => (
                            <p key={index} className="text-xs font-mono text-muted-foreground leading-relaxed">
                              {log}
                            </p>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                <p className="text-xs text-muted-foreground">Added {formatTimeAgo(repo.addedAt)}</p>
              </div>

              <Button
                variant="ghost"
                size="sm"
                onClick={() => onRemove(repo.id)}
                className="ml-4 text-muted-foreground hover:text-destructive"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

export const RepositoryList = memo(RepositoryListComponent)
