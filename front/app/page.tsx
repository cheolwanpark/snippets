import { RepoEmbedder } from "@/components/repo-embedder"

export default function Home() {
  return (
    <main className="min-h-screen bg-background">
      <div className="container mx-auto px-4 py-12">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-12">
            <h1 className="text-4xl font-bold text-foreground mb-4 text-balance">GitHub Repository Embedder</h1>
            <p className="text-lg text-muted-foreground text-pretty">
              Transform GitHub repositories into searchable code snippets for your vector database
            </p>
          </div>

          <RepoEmbedder />
        </div>
      </div>
    </main>
  )
}