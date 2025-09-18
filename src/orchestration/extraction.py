import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List, Optional, Sequence, Set, Union

from ..agent.snippet_extractor import SnippetExtractor
from ..snippet import Snippet, SnippetStorage
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

    def run(
        self,
        path: str,
        *,
        on_file_complete: Optional[Callable[[str, bool, int, int], None]] = None,
    ) -> List[Snippet]:
        """Extract snippets from files under the provided path."""
        loader = FileLoader(
            extensions=self.extensions,
            max_file_size=self.max_file_size,
            exclude_tests=not self.include_tests,
        )

        files_data = loader.load_files(path)
        self.storage.clear_snippets()
        for file_data in files_data:
            self.storage.register_file(file_data.relative_path)

        if files_data:
            logger.info("Loaded %d files from %s", len(files_data), path)

        stats: Dict[str, Union[int, float]] = {
            "successful": 0,
            "failed": 0,
            "duration": 0.0,
        }

        if files_data:
            self.executor = ThreadPoolExecutor(max_workers=self.max_concurrency)
            try:
                stats = asyncio.run(
                    self._process_files(files_data, on_file_complete=on_file_complete)
                )
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
        self,
        files_data: List[FileData],
        *,
        on_file_complete: Optional[Callable[[str, bool, int, int], None]] = None,
    ) -> Dict[str, Union[int, float]]:
        assert self.executor is not None, "Executor must be initialized before processing"

        semaphore = asyncio.Semaphore(self.max_concurrency)
        self.errors.clear()
        start_time = time.time()
        processed_count = 0
        progress_lock = asyncio.Lock()
        total_files = len(files_data)

        async def process_with_progress(file_data: FileData) -> bool:
            nonlocal processed_count
            async with semaphore:
                result = await self._process_single_file(file_data)
            async with progress_lock:
                processed_count += 1
                current_index = processed_count
            if on_file_complete is not None:
                try:
                    on_file_complete(
                        file_data.relative_path, result, current_index, total_files
                    )
                except Exception:  # pragma: no cover - defensive callback handling
                    logger.exception("on_file_complete callback failed")
            return result

        results = await asyncio.gather(*(process_with_progress(fd) for fd in files_data))

        successful = sum(1 for r in results if r)
        failed = len(files_data) - successful
        duration = time.time() - start_time
        snippet_count = self.storage.get_snippet_count()

        logger.info(
            "Processing complete: %d/%d files succeeded, %d snippets, %.1fs elapsed",
            successful,
            len(files_data),
            snippet_count,
            duration,
        )
        if failed > 0:
            logger.warning("%d files failed during extraction", failed)

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
            logger.exception("Failed to process %s", file_data.relative_path)
            self.errors.append(f"{file_data.relative_path}: {exc}")
            return False

    def _run_extractor_sync(self, file_data: FileData) -> bool:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            extractor = SnippetExtractor()
            return loop.run_until_complete(
                extractor.extract_from_content(
                    path=file_data.relative_path,
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
    on_file_complete: Optional[Callable[[str, bool, int, int], None]] = None,
) -> List[Snippet]:
    """Convenience helper to run the extraction pipeline and return snippets."""
    pipeline = ExtractionPipeline(
        max_concurrency=max_concurrency,
        extensions=extensions,
        max_file_size=max_file_size,
        include_tests=include_tests,
    )
    return pipeline.run(path=path, on_file_complete=on_file_complete)
