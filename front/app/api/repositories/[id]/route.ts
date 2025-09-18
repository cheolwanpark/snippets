/**
 * API route handler for /api/repositories/[id]
 * Handles fetching individual repository details by proxying to Python FastAPI backend
 */

import { NextRequest } from 'next/server'

interface RouteParams {
  params: {
    id: string
  }
}

// Get backend URL from environment
const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000'

/**
 * GET /api/repositories/[id]
 * Get detailed information about a specific repository
 */
export async function GET(
  request: NextRequest,
  { params }: RouteParams
) {
  try {
    const { id } = params

    // Validate repository ID
    if (!id || typeof id !== 'string' || id.trim() === '') {
      return Response.json(
        { detail: 'Repository ID is required' },
        { status: 400 }
      )
    }

    // Call Python FastAPI backend directly
    const response = await fetch(`${API_BASE_URL}/repo/${id.trim()}`)

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }))
      return Response.json(errorData, { status: response.status })
    }

    const repository = await response.json()
    return Response.json(repository)
  } catch (error) {
    console.error(`Error fetching repository ${params.id}:`, error)
    return Response.json(
      { detail: 'Internal server error' },
      { status: 500 }
    )
  }
}