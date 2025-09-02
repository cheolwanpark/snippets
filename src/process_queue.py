import asyncio
import time
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from claude_agent_toolkit import ConnectionError
from .file_loader import FileData
from .snippet_extractor import SnippetExtractor  
from .snippet_storage import SnippetStorage


class ProcessQueue:
    """Orchestrator for concurrent snippet extraction."""
    
    def __init__(self, max_concurrency: int = 5):
        self.max_concurrency = max_concurrency
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.executor = ThreadPoolExecutor(max_workers=max_concurrency)
    
    async def process(self, files_data: List[FileData], top_n: int = 10) -> str:
        """Process pre-loaded files concurrently and return results."""
        start_time = time.time()
        
        # Initialize shared storage
        storage = SnippetStorage()
        storage.run(workers=self.max_concurrency * 2)
        
        print(f"⚡ Processing {len(files_data)} files (concurrency: {self.max_concurrency})...")
        
        # Create tasks for all files
        tasks = [
            self._process_file(file_data, top_n, storage)
            for file_data in files_data
        ]
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count successes and failures
        successful = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
        failed = len(results) - successful
        
        total_time = time.time() - start_time
        
        # Summary
        print(f"\n✅ Processing complete!")
        print(f"📈 Files processed: {successful}/{len(files_data)}")
        print(f"🔢 Total snippets: {storage.get_snippet_count()}")
        print(f"⏱️  Total time: {total_time:.1f}s")
        if failed > 0:
            print(f"⚠️  Failed files: {failed}")
        
        # Return formatted output
        return storage.to_file()
    
    def _run_extractor_sync(self, file_data: FileData, top_n: int, storage) -> Dict[str, Any]:
        """Run snippet extraction synchronously in a thread - bypasses Docker blocking."""
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                extractor = SnippetExtractor()
                result = loop.run_until_complete(
                    extractor.extract_from_content(
                        filename=file_data.filename,
                        content=file_data.content,
                        top_n=top_n,
                        storage=storage
                    )
                )
                return result
            finally:
                loop.close()
                
        except ConnectionError as e:
            return {
                "success": False,
                "filename": file_data.filename,
                "error": f"Docker/network issue: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "filename": file_data.filename,
                "error": str(e)
            }
    
    async def _process_file(self, file_data: FileData, top_n: int, storage) -> Dict[str, Any]:
        """Process single file with pre-loaded content using ThreadPoolExecutor."""
        async with self.semaphore:
            # Run the blocking Docker operation in a separate thread
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self.executor,
                self._run_extractor_sync,
                file_data,
                top_n,
                storage
            )
    
    def cleanup(self):
        """Cleanup resources - shutdown ThreadPoolExecutor."""
        if hasattr(self, 'executor') and self.executor:
            self.executor.shutdown(wait=True)
    
    def __del__(self):
        """Cleanup on garbage collection."""
        self.cleanup()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures cleanup."""
        self.cleanup()
        return False