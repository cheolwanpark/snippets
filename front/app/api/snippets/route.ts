/**
 * API route handler for /api/snippets
 * Handles searching code snippets by proxying to Python FastAPI backend
 */

import { NextRequest } from 'next/server'

// Get backend URL from environment
const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000'

/**
 * GET /api/snippets
 * Search for code snippets using natural language queries
 */
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const query = searchParams.get('query')
    const limitParam = searchParams.get('limit')
    const repoName = searchParams.get('repo_name')?.trim()
    const language = searchParams.get('language')?.trim()

    // Validate required query parameter
    if (!query || typeof query !== 'string' || query.trim() === '') {
      return Response.json(
        { detail: 'Query parameter is required and must be non-empty' },
        { status: 400 }
      )
    }

    // Validate and parse limit parameter
    let limit = 5 // default value
    if (limitParam) {
      const parsedLimit = parseInt(limitParam, 10)
      if (isNaN(parsedLimit) || parsedLimit < 1 || parsedLimit > 50) {
        return Response.json(
          { detail: 'Limit must be a number between 1 and 50' },
          { status: 400 }
        )
      }
      limit = parsedLimit
    }

    // Call Python FastAPI backend directly
    const backendUrl = new URL('/snippets', API_BASE_URL)
    backendUrl.searchParams.set('query', query.trim())
    backendUrl.searchParams.set('limit', limit.toString())

    // Add optional filters if provided
    if (repoName) {
      backendUrl.searchParams.set('repo_name', repoName)
    }
    if (language) {
      backendUrl.searchParams.set('language', language)
    }

    const response = await fetch(backendUrl.toString())

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }))
      return Response.json(errorData, { status: response.status })
    }

    const results = await response.json()
    return Response.json(results)
  } catch (error) {
    console.error('Error searching snippets:', error)
    return Response.json(
      { detail: 'Internal server error' },
      { status: 500 }
    )
  }
}
