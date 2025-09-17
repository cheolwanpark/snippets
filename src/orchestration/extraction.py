import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Sequence, Set, Union

from tqdm import tqdm

from ..agent.snippet_extractor import SnippetExtractor
from ..snippet.snippet_storage import Snippet, SnippetStorage
from ..utils.file_loader import FileData, FileLoader


logger = logging.getLogger("snippet_extractor")


class ExtractionPipeline:
    """High-level orchestrator that runs the full snippet extraction pipeline."""

    def __init__(
        self,
        *,
        max_concurrency: int = 5,
        extensions: Optional[Sequence[str]] = None,
        max_file_size: Optional[int] = None,
        include_tests: bool = False,
    ) -> None:
        self.max_concurrency = max_concurrency
        self.extensions = self._normalize_extensions(extensions)
        self.max_file_size = max_file_size
        self.include_tests = include_tests
        self.executor: Optional[ThreadPoolExecutor] = None
        self.errors: List[str] = []
        self.storage = SnippetStorage()
        self._last_run_stats: Optional[Dict[str, Union[int, float]]] = None

    def run(self, path: str) -> List[Snippet]:
        """Extract snippets from files under the provided path."""
        loader = FileLoader(
            extensions=self.extensions,
            max_file_size=self.max_file_size,
            exclude_tests=not self.include_tests,
        )

        files_data = loader.load_files(path)
        self.storage.clear_snippets()
        for file_data in files_data:
            self.storage.register_file(file_data.filename)

        if files_data:
            tqdm.write(f"📁 Loaded {len(files_data)} files from: {path}")

        stats: Dict[str, Union[int, float]] = {
            "successful": 0,
            "failed": 0,
            "duration": 0.0,
        }

        if files_data:
            self.executor = ThreadPoolExecutor(max_workers=self.max_concurrency)
            try:
                stats = asyncio.run(self._process_files(files_data))
            finally:
                self.cleanup()
        else:
            self.errors.clear()

        stats.update(
            {
                "total_files": len(files_data),
                "total_snippets": self.storage.get_snippet_count(),
            }
        )
        self._last_run_stats = stats

        return self.storage.get_all_snippets()

    def cleanup(self) -> None:
        """Shutdown executor resources."""
        if self.executor is not None:
            self.executor.shutdown(wait=True)
            self.executor = None

    async def _process_files(
        self, files_data: List[FileData]
    ) -> Dict[str, Union[int, float]]:
        assert self.executor is not None, "Executor must be initialized before processing"

        semaphore = asyncio.Semaphore(self.max_concurrency)
        self.errors.clear()
        start_time = time.time()

        pbar = tqdm(
            total=len(files_data),
            desc="Processing files",
            unit="file",
            bar_format=(
                "{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} "
                "[{elapsed}<{remaining}, {rate_fmt}]"
            ),
            position=0,
            leave=True,
        )

        async def process_with_progress(file_data: FileData) -> bool:
            filename_display = file_data.filename.split("/")[-1][:30]
            async with semaphore:
                result = await self._process_single_file(file_data)
            pbar.update(1)
            pbar.set_postfix(file=filename_display, refresh=False)
            return result

        try:
            results = await asyncio.gather(*(process_with_progress(fd) for fd in files_data))
        finally:
            pbar.close()

        successful = sum(1 for r in results if r)
        failed = len(files_data) - successful
        duration = time.time() - start_time
        snippet_count = self.storage.get_snippet_count()

        tqdm.write("\n✅ Processing complete!")
        tqdm.write(
            "📈 Files: %s/%s | 🔢 Snippets: %s | ⏱️ Time: %.1fs"
            % (successful, len(files_data), snippet_count, duration)
        )
        if failed > 0:
            tqdm.write(f"⚠️  Failed: {failed} files")

        return {"successful": successful, "failed": failed, "duration": duration}

    async def _process_single_file(self, file_data: FileData) -> bool:
        loop = asyncio.get_running_loop()
        try:
            assert self.executor is not None, "Executor must be initialized before processing"
            return await loop.run_in_executor(
                self.executor,
                self._run_extractor_sync,
                file_data,
            )
        except Exception as exc:  # pragma: no cover - best effort logging
            logger.exception("Failed to process %s", file_data.filename)
            self.errors.append(f"{file_data.filename}: {exc}")
            return False

    def _run_extractor_sync(self, file_data: FileData) -> bool:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            extractor = SnippetExtractor()
            return loop.run_until_complete(
                extractor.extract_from_content(
                    filename=file_data.filename,
                    content=file_data.content,
                    storage=self.storage,
                )
            )
        finally:
            loop.close()

    @property
    def last_run_stats(self) -> Optional[Dict[str, Union[int, float]]]:
        """Return summary statistics for the last pipeline run."""
        return self._last_run_stats

    @staticmethod
    def _normalize_extensions(extensions: Optional[Sequence[str]]) -> Optional[Set[str]]:
        if not extensions:
            return None
        normalized = set()
        for ext in extensions:
            if not ext:
                continue
            normalized.add(ext if ext.startswith('.') else f'.{ext}')
        return normalized or None


def extract_snippets_from_path(
    path: str,
    *,
    max_concurrency: int = 5,
    extensions: Optional[Sequence[str]] = None,
    max_file_size: Optional[int] = None,
    include_tests: bool = False,
) -> List[Snippet]:
    """Convenience helper to run the extraction pipeline and return snippets."""
    pipeline = ExtractionPipeline(
        max_concurrency=max_concurrency,
        extensions=extensions,
        max_file_size=max_file_size,
        include_tests=include_tests,
    )
    return pipeline.run(path=path)
