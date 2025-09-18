/**
 * API route handlers for /api/repositories
 * Handles repository creation and listing by proxying to Python FastAPI backend
 */

import { NextRequest } from 'next/server'
import type { RepoCreateRequest } from '@/types'

// Get backend URL from environment
const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000'

/**
 * POST /api/repositories
 * Create/enqueue a repository for processing
 */
export async function POST(request: NextRequest) {
  try {
    const body: RepoCreateRequest = await request.json()

    // Validate required fields
    if (!body.url || typeof body.url !== 'string') {
      return Response.json(
        { detail: 'Repository URL is required' },
        { status: 400 }
      )
    }

    // Optional field validation
    if (body.max_file_size !== undefined && body.max_file_size < 0) {
      return Response.json(
        { detail: 'max_file_size must be non-negative' },
        { status: 400 }
      )
    }

    // Call Python FastAPI backend directly
    const response = await fetch(`${API_BASE_URL}/repo`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }))
      return Response.json(errorData, { status: response.status })
    }

    const result = await response.json()
    return Response.json(result, { status: 202 })
  } catch (error) {
    console.error('Error creating repository:', error)
    return Response.json(
      { detail: 'Internal server error' },
      { status: 500 }
    )
  }
}

/**
 * GET /api/repositories
 * List all repositories with their current status
 */
export async function GET() {
  try {
    // Call Python FastAPI backend directly
    const response = await fetch(`${API_BASE_URL}/repo`)

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }))
      return Response.json(errorData, { status: response.status })
    }

    const repositories = await response.json()
    return Response.json(repositories)
  } catch (error) {
    console.error('Error listing repositories:', error)
    return Response.json(
      { detail: 'Internal server error' },
      { status: 500 }
    )
  }
}