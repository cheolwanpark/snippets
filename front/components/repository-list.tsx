"use client"

import React, { memo } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { Trash2 } from "lucide-react"
import type { RepositoryListProps } from "@/types"

const RepositoryListComponent = ({
  repositories,
  onRemove,
  formatTimeAgo,
  getStatusIcon,
  getStatusBadge,
}: RepositoryListProps) => {

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
                  <h3 className="font-mono text-sm font-medium text-card-foreground truncate">{repo.repo_name || 'Unknown'}</h3>
                  {getStatusBadge(repo.status)}
                </div>

                <p className="text-xs text-muted-foreground mb-2 truncate">{repo.url}</p>

                {repo.status === "processing" && repo.progress !== undefined && (
                  <div className="mb-2">
                    <Progress value={repo.progress} className="h-2" />
                    <p className="text-xs text-muted-foreground mt-1">{repo.progress}% complete</p>
                  </div>
                )}

                {repo.status === "error" && repo.fail_reason && (
                  <p className="text-xs text-destructive mb-2">Error: {repo.fail_reason}</p>
                )}

                {repo.process_message && (
                  <div className="mt-2">
                    <p className="text-xs text-muted-foreground">{repo.process_message}</p>
                  </div>
                )}

                <p className="text-xs text-muted-foreground">Added {formatTimeAgo(repo.created_at)}</p>
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
