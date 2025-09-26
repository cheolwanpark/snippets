# SNIPPETS

**Snippets** is an intelligent code repository system that automatically extracts, processes, and indexes code snippets from GitHub repositories into a searchable vector database. It combines AI-powered code analysis with semantic search capabilities to help developers quickly find relevant code examples and patterns.

<p align="center">
  <img src="https://github.com/user-attachments/assets/cb2e98d4-4396-4968-9d67-e46e09ad54c7" width="47%" />
  <img src="https://github.com/user-attachments/assets/cd7c2cd9-4786-4916-a29b-ea438ffc9c34" width="47%" />
</p>

### Key Features

- **🚀 Use Your Claude Subscription**: Access this tool with your Claude subscription plan. no extra cost!
- **🤖 Automated Repository Processing**: Extract meaningful code snippets from any GitHub repository
- **🔍 Semantic Search**: Find code by meaning, not just keywords, using vector embeddings
- **🔧 MCP Integration**: Seamless integration with Claude Code through Model Context Protocol
- **⚡ Background Processing**: Efficient queue-based processing for large repositories
- **🐳 Docker Ready**: Complete containerized setup for easy deployment

### How It Works

1. **Repository Ingestion**: Add GitHub repositories through the web interface
2. **AI Processing**: Claude Code agents analyze and extract meaningful code snippets
3. **Vector Embedding**: Code snippets are converted to semantic vectors using state-of-the-art models
4. **Smart Storage**: Snippets are indexed in Qdrant vector database for fast similarity search
5. **Easy Discovery**: Search and explore code through the web UI or integrate with Claude Code via MCP

## Quick Start

### Prerequisites

- **Docker & Docker Compose**: For containerized deployment
- **API Keys**:
  - Claude Code OAuth Token (from you subscription, `claude setup-token`)
  - Google Gemini API key (for embeddings, you can claim Free API Key)

### 1. Clone and Setup

```bash
git clone https://github.com/cheolwanpark/snippets
cd snippets
```

### 2. Environment Configuration

Create your environment file:

```bash
cp docker/.env.example docker/.env
```

Edit `docker/.env` with your API keys:

```env
# Required: Claude API for code analysis
CLAUDE_CODE_OAUTH_TOKEN=your_claude_token_here

# Required: Gemini API for embeddings
EMBEDDING_API_KEY=your_gemini_api_key_here

# Optional: GitHub PAT, required for PRIVATE repository access
GITHUB_TOKEN=your_github_pat_here

# Optional: Cohere API key, required for reranking
COHERE_API_KEY=your_cohere_api_key_here

# Optional: Customize ports
FRONT_PORT=3000
MCP_PORT=8080
```

### 3. Launch with Docker

```bash
cd docker
docker-compose up -d
```

This starts all services:
- **Frontend**: http://localhost:3000
- **API with MCP server**: http://localhost:8000 (api), http://localhost:8080/mcp (mcp)
- **Worker**: controlled by RQ
- **Qdrant**: http://localhost:6333
- **Redis**: localhost:6379

### 4. First Repository

1. Open http://localhost:3000 in your browser
2. Enter a GitHub repository URL (e.g., `https://github.com/user/repo`)
3. Click 'Embed'
4. Monitor progress in the dashboard
5. Search your snippets in 'Query' tab once processing completes!

### 5. Connect MCP server to claude

```bash
claude mcp add --transport http snippets http://localhost:8080/mcp
```

This enables Claude Code to search your processed snippets directly during development.

## Configuration

### Essential Environment Variables

The system requires minimal configuration for most use cases:

#### Required API Keys

```env
# Claude API token for AI-powered code analysis
CLAUDE_CODE_OAUTH_TOKEN=your_claude_api_token

# Google Gemini API key for generating embeddings
EMBEDDING_API_KEY=your_gemini_api_key
```

#### Optional Customization

```env
# Service Ports
FRONT_PORT=3000              # Frontend web interface
MCP_PORT=8080               # MCP server port

# Database Configuration (use defaults unless you have existing instances)
QDRANT_URL=http://qdrant:6333
REDIS_URL=redis://redis:6379

# Processing Settings
EMBEDDING_MODEL=gemini-pro    # Embedding model to use
MAX_FILE_SIZE_MB=1           # Maximum file size to process
```

### Getting API Keys

- **Claude API Token**: type `claude setup-token` in your terminal
- **Gemini API Key**: Get one from [Google AI Studio](https://aistudio.google.com/app/apikey)

## Usage

### Web Interface

The web interface at http://localhost:3000 provides a complete repository management experience:

#### Repository Management

1. **Add Repository**:
   - Go to 'Embed' Tab
   - Enter GitHub URL (private repositories supported with your PAT token)
   - Optional: Configure processing options (file filters, size limits)
   - Start processing

2. **Monitor Progress**:
   - Real-time processing status
   - Progress indicators for extraction phases
   - Error reporting for failed repositories

3. **Repository Settings**:
   - Edit processing configuration
   - Re-process with different settings
   - Remove repositories and their snippets

#### Snippet Search

1. **Semantic Search**:
   - Go to 'Query' Tab
   - Enter natural language queries ("authentication middleware", "error handling")
   - Use technical terms ("async function", "React hooks")
   - Search by programming concepts
   - Optional: Configure search options (repository name, language)

2. **Explore Snippets**:
   - View code with syntax highlighting
   - See file context and repository source
   - Copy snippets for use in your projects

### MCP Integration with Claude Code

The Snippets MCP server enables seamless integration with Claude Code for enhanced development workflows.

#### Setup MCP Connection

```bash
# in your project directory
claude mcp add --transport http snippets http://localhost:8080/mcp
# OR configure the mcp server for user scope
claude mcp add -s user --transport http snippets http://localhost:8080/mcp
```

#### Using the Search Tool

Once connected, Claude Code gains access to the `search` tool:

```
# Find error handling patterns
search error handling patterns in Python. use snippets.

# Find authentication patterns
search JWT authentication middleware. use snippets.

# Language-specific search
search async database queries. use snippets.

# Repository-specific search
search React component patterns. use snippets.
```

**Search Parameters (will be configured automatically by claude code)**:
- `query`: Natural language description of what you're looking for
- `limit`: Number of results (default: 10, max: 50)
- `repo_name`: Filter to specific repository
- `language`: Filter by programming language

#### Workflow Integration

Use the MCP integration for:
- **Code Discovery**: Find examples before implementing new features
- **Pattern Research**: Explore different approaches to common problems
- **Learning**: Understand how concepts are implemented across repositories
- **Code Review**: Find similar implementations for comparison

## Troubleshooting

### Common Issues

#### Repository Processing Fails

**Problem**: Repository gets stuck in "Processing" state
**Solutions**:
- Check API key validity in docker logs: `docker-compose logs api`
- Verify repository is public and accessible
- Check file size limits - large repositories may timeout
- Restart worker: `docker-compose restart worker`

#### Empty Search Results

**Problem**: Search returns no snippets
**Solutions**:
- Verify repository processing completed successfully
- Check if files were actually processed (some file types are filtered)
- Try broader search terms
- Increase result limit to 50

#### MCP Connection Issues

**Problem**: Claude Code cannot connect to MCP server
**Solutions**:
- Verify MCP port is exposed: `docker-compose ps`
- Check MCP server logs: `docker-compose logs api`
- Ensure firewall allows connections to port 8080
- Try direct HTTP connection to http://localhost:8080/mcp

#### Performance Issues

**Problem**: Slow search or processing
**Solutions**:
- Monitor resource usage: `docker stats`
- Increase Docker memory allocation
- Reduce concurrent processing in worker settings
- Consider using faster embedding models

### Debugging Tips

#### Check Service Health

```bash
# View all service status
docker-compose ps

# Check specific service logs
docker-compose logs -f api
docker-compose logs -f worker
docker-compose logs -f front

# Monitor resource usage
docker stats
```

#### Database Inspection

```bash
# Access Qdrant dashboard
open http://localhost:6333/dashboard

# Check Redis queue status
docker-compose exec redis redis-cli
> LLEN repo-ingest  # Check queue length
```

#### Reset Everything

```bash
# Nuclear option: reset all data
docker-compose down -v
docker-compose up -d
```

### Performance Optimization

#### Processing Large Repositories

- Set reasonable file size limits (default: 500KB)
- Use file filters to exclude irrelevant files
- Process repositories during off-peak hours
- Monitor worker memory usage
- consider using large PIPELINE_MAX_CONCURRENCY

#### Search Performance

- Use specific search terms rather than very broad queries
- Filter by language or repository when possible
- Consider the trade-off between result quality and quantity

## Architecture

### System Overview

Snippets is built as a microservices architecture with clear separation of concerns:

```
┌─────────────────┐    ┌───────────────────┐    ┌─────────────────┐
│   Frontend      │    │  API/MCP Server   │    │   Worker Pool   │
│   (Next.js)     │◄──►│ (FastAPI/FastMCP) │◄──►│   (RQ/Redis)    │
└─────────────────┘    └───────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │   Vector DB      │    │   Message Queue │
                       │   (Qdrant)       │    │   (Redis)       │
                       └──────────────────┘    └─────────────────┘
```

### Components

#### Frontend (Next.js)
- **Location**: `front/`
- **Purpose**: Web interface for repository management and snippet search
- **Technology**: Next.js 14, React, TypeScript, Tailwind CSS
- **Features**:
  - Repository CRUD operations
  - Real-time processing status
  - Semantic search interface
  - Responsive design with dark/light themes

#### API Server (FastAPI)
- **Location**: `src/api/`
- **Purpose**: REST API for all backend operations
- **Technology**: FastAPI, Python 3.12, Pydantic
- **Endpoints**:
  - Repository management (`/repo`)
  - Snippet search (`/snippets`)

#### Worker System (RQ/Redis)
- **Location**: `src/worker/`
- **Purpose**: Background processing of repositories
- **Technology**: RQ (Redis Queue), Redis
- **Responsibilities**:
  - Repository cloning and analysis
  - Code snippet extraction using AI agents
  - Vector embedding generation
  - Database storage operations

#### Vector Database (Qdrant)
- **Purpose**: Store and search code snippet embeddings
- **Technology**: Qdrant vector database
- **Features**:
  - High-performance similarity search
  - Metadata filtering (language, repository)
  - Scalable vector storage
  - Built-in clustering and indexing

#### MCP Server (FastMCP)
- **Location**: `src/mcpserver/`
- **Purpose**: Model Context Protocol integration
- **Technology**: FastMCP, mounted on main API
- **Tools Provided**:
  - `search`: Semantic snippet search for Claude Code

### Data Flow

#### Repository Processing Flow

1. **User Input**: Repository URL submitted via web interface
2. **API Validation**: URL validation and repository metadata extraction
3. **Queue Job**: Processing job added to Redis queue
4. **Worker Processing**:
   - Clone repository to temporary storage
   - Filter files by type and size
   - Extract meaningful code snippets using Claude Code Agents
   - Generate vector embeddings for each snippet
   - Store in Qdrant with metadata
5. **Status Updates**: Real-time status updates via polling
6. **Completion**: Repository marked as processed, snippets available for search

#### Search Flow

1. **Query Input**: User enters search query (Web UI or MCP)
2. **Query Embedding**: Convert query to vector using same embedding model
3. **Vector Search**: Qdrant performs similarity search with filters
4. **Result Ranking**: Results reranked by cohere rerank API
5. **Response**: Formatted results returned with snippet metadata

### Technology Stack

#### Backend
- **Python 3.12**: Core runtime
- **FastAPI**: Web framework and API server
- **RQ + Redis**: Task queue and caching
- **Qdrant**: Vector database
- **Claude Agent Toolkit**: AI-powered code analysis
- **Google Gemini**: Text embedding generation

#### Frontend
- **Next.js 14**: React framework
- **TypeScript**: Type safety
- **Tailwind CSS**: Styling framework
- **Radix UI**: Component primitives
- **Lucide**: Icon library

#### Infrastructure
- **Docker**: Containerization
- **Docker Compose**: Multi-service orchestration
- **Redis**: Message broker and cache
- **Nginx**: Reverse proxy (production)
