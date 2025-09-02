import asyncio
import time
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
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
        
        # Create progress bar with detailed formatting
        pbar = tqdm(
            total=len(files_data),
            desc="Processing files",
            unit="file",
            bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]',
            position=0,
            leave=True
        )
        
        # Process with progress updates
        async def process_with_progress(file_data):
            from .exception_handler import error_handler
            try:
                result = await self._process_file(file_data, top_n, storage)
                pbar.update(1)
                # Update description with current file (truncated)
                filename = file_data.filename.split('/')[-1][:30]
                pbar.set_postfix(file=filename, refresh=False)
                return result
            except Exception as e:
                error_handler.collect_processing_error(e, file_data.filename, "processing")
                pbar.update(1)
                return False
        
        tasks = [process_with_progress(file_data) for file_data in files_data]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Close progress bar
        pbar.close()
        
        # Count successes and failures
        successful = sum(1 for r in results if r is True)
        failed = len(results) - successful
        
        total_time = time.time() - start_time
        
        # Display final summary using tqdm.write
        tqdm.write(f"\n✅ Processing complete!")
        tqdm.write(f"📈 Files: {successful}/{len(files_data)} | 🔢 Snippets: {storage.get_snippet_count()} | ⏱️ Time: {total_time:.1f}s")
        if failed > 0:
            tqdm.write(f"⚠️  Failed: {failed} files")
        
        # Return formatted output
        return storage.to_file()
    
    def _run_extractor_sync(self, file_data: FileData, top_n: int, storage) -> bool:
        """Run snippet extraction synchronously in a thread - bypasses Docker blocking."""
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            extractor = SnippetExtractor()
            result = loop.run_until_complete(
                extractor.extract_from_content(
                    filename=file_data.filename,
                    content=file_data.content,
                    storage=storage,
                    top_n=top_n
                )
            )
            return result
        finally:
            loop.close()
    
    async def _process_file(self, file_data: FileData, top_n: int, storage) -> bool:
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