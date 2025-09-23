"use client"

import React, { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Settings } from "lucide-react"
import { toast } from "sonner"
import type { RepoConfig, SearchConfig } from "@/types"

interface RepoConfigDialogProps {
  config: RepoConfig
  onConfigChange: (config: RepoConfig) => void
}

interface SearchConfigDialogProps {
  config: SearchConfig
  onConfigChange: (config: SearchConfig) => void
}

export function RepoConfigDialog({ config, onConfigChange }: RepoConfigDialogProps) {
  const [open, setOpen] = useState(false)
  const [localConfig, setLocalConfig] = useState<RepoConfig>(config)

  // Sync localConfig with config prop changes
  useEffect(() => {
    setLocalConfig(config)
  }, [config])

  const handleApply = () => {
    onConfigChange(localConfig)
    toast.success("Repository configuration applied")
    setOpen(false)
  }

  const handleReset = () => {
    const resetConfig: RepoConfig = { include_tests: false }
    setLocalConfig(resetConfig)
    toast.success("Repository configuration reset")
  }

  const handleOpenChange = (isOpen: boolean) => {
    if (!isOpen) {
      // Discard local changes when closing
      setLocalConfig(config)
    }
    setOpen(isOpen)
  }

  const handlePatternsChange = (value: string) => {
    const patterns = value.trim() ? value.split(',').map(pattern => pattern.trim()) : undefined
    setLocalConfig(prev => ({ ...prev, patterns }))
  }


  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm" className="h-6 w-6 p-0">
          <Settings className="h-4 w-4" />
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Repository Configuration</DialogTitle>
          <DialogDescription>
            Configure advanced options for repository processing.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="branch">Branch</Label>
            <Input
              id="branch"
              placeholder="main, develop, feature/branch"
              className="placeholder:text-gray-400"
              value={localConfig.branch || ""}
              onChange={(e) => setLocalConfig(prev => ({ ...prev, branch: e.target.value || undefined }))}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="patterns">File Patterns</Label>
            <Input
              id="patterns"
              placeholder="*.py, *.js, *.tsx, *.ts"
              className="placeholder:text-gray-400"
              value={localConfig.patterns?.join(',') || ""}
              onChange={(e) => handlePatternsChange(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="maxFileSize">Max File Size (bytes)</Label>
            <Input
              id="maxFileSize"
              type="number"
              placeholder="512000"
              className="placeholder:text-gray-400"
              value={localConfig.max_file_size || ""}
              onChange={(e) => setLocalConfig(prev => ({
                ...prev,
                max_file_size: e.target.value ? parseInt(e.target.value) : undefined
              }))}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="includeTests">Include Tests</Label>
            <Select
              value={localConfig.include_tests?.toString() || "false"}
              onValueChange={(value) => setLocalConfig(prev => ({
                ...prev,
                include_tests: value === "true"
              }))}
            >
              <SelectTrigger>
                <SelectValue placeholder="Exclude tests (default)" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="false">Exclude tests (default)</SelectItem>
                <SelectItem value="true">Include tests</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={handleReset}>
            Reset
          </Button>
          <Button onClick={handleApply}>
            Apply
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function SearchConfigDialog({ config, onConfigChange }: SearchConfigDialogProps) {
  const [open, setOpen] = useState(false)
  const [localConfig, setLocalConfig] = useState<SearchConfig>(config)

  // Sync localConfig with config prop changes
  useEffect(() => {
    setLocalConfig(config)
  }, [config])

  const handleApply = () => {
    onConfigChange(localConfig)
    toast.success("Search configuration applied")
    setOpen(false)
  }

  const handleReset = () => {
    const resetConfig: SearchConfig = { limit: 5 }
    setLocalConfig(resetConfig)
    toast.success("Search configuration reset")
  }

  const handleOpenChange = (isOpen: boolean) => {
    if (!isOpen) {
      // Discard local changes when closing
      setLocalConfig(config)
    }
    setOpen(isOpen)
  }


  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm" className="h-6 w-6 p-0">
          <Settings className="h-4 w-4" />
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Search Configuration</DialogTitle>
          <DialogDescription>
            Configure advanced options for snippet search.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="repoName">Repository Name Filter</Label>
            <Input
              id="repoName"
              placeholder="my-repo, organization/repo"
              className="placeholder:text-gray-400"
              value={localConfig.repo_name || ""}
              onChange={(e) => setLocalConfig(prev => ({ ...prev, repo_name: e.target.value || undefined }))}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="language">Language Filter</Label>
            <Input
              id="language"
              placeholder="python, javascript, typescript"
              className="placeholder:text-gray-400"
              value={localConfig.language || ""}
              onChange={(e) => setLocalConfig(prev => ({ ...prev, language: e.target.value || undefined }))}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="limit">Results Limit</Label>
            <Input
              id="limit"
              type="number"
              min="1"
              max="50"
              value={localConfig.limit || 5}
              onChange={(e) => setLocalConfig(prev => ({
                ...prev,
                limit: e.target.value ? Math.max(1, Math.min(50, parseInt(e.target.value))) : 5
              }))}
            />
          </div>
        </div>
        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={handleReset}>
            Reset
          </Button>
          <Button onClick={handleApply}>
            Apply
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
