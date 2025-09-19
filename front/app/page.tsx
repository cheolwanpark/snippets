import { RepoEmbedder } from "@/components/repo-embedder"
import Image from "next/image"

export default function Home() {
  return (
    <main className="min-h-screen bg-background">
      <div className="container mx-auto px-4 py-12">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-12">
            <div className="flex items-center justify-center gap-1 mb-4">
              <Image
                src="/snippets.png"
                alt="Snippets Logo"
                width={48}
                height={48}
                className="w-12 h-12"
              />
              <h1 className="text-4xl font-bold text-foreground text-balance">SNIPPETS</h1>
            </div>
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