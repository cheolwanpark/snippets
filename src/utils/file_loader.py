import glob
import logging
import os
from fnmatch import fnmatch
from pathlib import Path
from typing import List, NamedTuple, Sequence

from .chunker import chunk_file_data


class FileInfo(NamedTuple):
    """Information about a detected source file."""
    path: str
    size: int
    extension: str


class FileData(NamedTuple):
    """Pre-loaded file data for async processing."""
    path: str
    relative_path: str
    content: str
    size: int
    extension: str


class FileLoader:
    """Smart file discovery with filtering for source code analysis."""

    logger = logging.getLogger("snippet_extractor")

    # Supported file patterns
    DEFAULT_PATTERNS: Sequence[str] = (
        "*.py", "*.pyi", "*.js", "*.jsx", "*.ts", "*.tsx", "*.mjs", "*.cjs",
        "*.java", "*.kt", "*.go", "*.rs", "*.c", "*.cc", "*.cpp", "*.h",
        "*.hpp", "*.cs", "*.swift", "*.scala", "*.php", "*.rb", "*.pl", "*.sh",
        "*.json", "*.yaml", "*.yml", "*.toml", "Dockerfile", "Dockerfile.*", "*.md",
    )

    # Directories to exclude from search
    EXCLUDE_DIRS = {
        '__pycache__', '.venv', 'venv', 'node_modules', 'target', 'dist',
        'build', '.git', '.svn', '.hg', 'coverage', '.pytest_cache',
        '.tox', '.coverage', 'htmlcov', '.mypy_cache', '.DS_Store'
    }
    
    # Files to exclude (patterns)
    EXCLUDE_PATTERNS = {
        'test_', '_test.', '.test.', '.spec.', '_spec.',
        '.min.', '-min.', '.bundle.', '.chunk.'
    }
    
    # Default file size cap (≈500 KB) and chunk threshold (≈1.8 MB).
    DEFAULT_MAX_FILE_SIZE = 500 * 1024
    DEFAULT_MAX_CHUNK_SIZE = 1_800_000
    
    def __init__(self, patterns: Sequence[str] | None = None, max_file_size=None, exclude_tests=True):
        """Initialize file loader with optional custom settings.
        
        Args:
            patterns: Glob-style patterns to include (default: basic code file types)
            max_file_size: Optional maximum file size in bytes. Defaults to ~500 KB;
                pass 0 to disable the size cap. Chunking uses a 1.8 MB threshold
                for large files.
            exclude_tests: Whether to exclude test files (default: True)
        """
        self.patterns = list(patterns) if patterns else list(self.DEFAULT_PATTERNS)
        if max_file_size == 0:
            max_file_size = None

        if max_file_size is None:
            self.max_file_size = self.DEFAULT_MAX_FILE_SIZE
            self.max_chunk_size = self.DEFAULT_MAX_CHUNK_SIZE
        else:
            self.max_file_size = max_file_size
            self.max_chunk_size = max(self.DEFAULT_MAX_CHUNK_SIZE, max_file_size)
        self.exclude_tests = exclude_tests
    
    def detect_files(self, path: str) -> List[FileInfo]:
        """Detect source files in the given path (file or directory).

        Args:
            path: File or directory path to analyze

        Returns:
            List of FileInfo objects for discovered files
            
        Raises:
            FileNotFoundError: If path doesn't exist
            ValueError: If path is neither file nor directory
        """
        path_str = str(path)

        if glob.has_magic(path_str):
            matched_paths = sorted(Path(p) for p in glob.glob(path_str, recursive=True))
            if not matched_paths:
                raise FileNotFoundError(f"No files match pattern: {path}")

            files: List[FileInfo] = []
            base_dir = self._infer_base_dir_from_pattern(path_str)

            for match_path in matched_paths:
                if match_path.is_file():
                    files.extend(self._analyze_single_file(match_path, base_dir=base_dir))
                elif match_path.is_dir():
                    files.extend(self._analyze_directory(match_path))

            if not files:
                raise FileNotFoundError(f"No files match pattern: {path}")

            return files

        path_obj = Path(path)
        
        if not path_obj.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        
        if path_obj.is_file():
            return self._analyze_single_file(path_obj)
        elif path_obj.is_dir():
            return self._analyze_directory(path_obj)
        else:
            raise ValueError(f"Path is neither file nor directory: {path}")
    
    def _analyze_single_file(self, file_path: Path, base_dir: Path | None = None) -> List[FileInfo]:
        """Analyze a single file and return FileInfo if it qualifies."""
        relative_path = self._compute_relative_path(file_path, base_dir)
        if not self._should_include_file(file_path, relative_path):
            return []

        try:
            stat_info = file_path.stat()
            return [FileInfo(
                path=str(file_path.absolute()),
                size=stat_info.st_size,
                extension=file_path.suffix
            )]
        except (OSError, PermissionError):
            # Skip files we can't access
            return []
    
    def _analyze_directory(self, dir_path: Path) -> List[FileInfo]:
        """Recursively analyze directory and return qualifying files."""
        files = []
        
        try:
            for root, dirs, filenames in os.walk(dir_path):
                # Filter out excluded directories
                dirs[:] = [d for d in dirs if d not in self.EXCLUDE_DIRS]
                
                root_path = Path(root)
                
                for filename in filenames:
                    file_path = root_path / filename
                    try:
                        relative_path = file_path.relative_to(dir_path)
                    except ValueError:
                        relative_path = Path(filename)

                    if self._should_include_file(file_path, relative_path):
                        try:
                            stat_info = file_path.stat()
                            files.append(FileInfo(
                                path=str(file_path.absolute()),
                                size=stat_info.st_size,
                                extension=file_path.suffix
                            ))
                        except (OSError, PermissionError):
                            # Skip files we can't access
                            continue
        except (OSError, PermissionError):
            # Handle directory permission errors
            pass
        
        return files
    
    def load_files(self, path: str) -> List[FileData]:
        """Detect and load all files into memory.

        Args:
            path: File or directory path to analyze
            
        Returns:
            List of FileData objects with pre-loaded content
        """
        file_infos = self.detect_files(path)
        files_data = []
        
        path_str = str(path)
        if glob.has_magic(path_str):
            base_dir = self._infer_base_dir_from_pattern(path_str)
        else:
            base_input = Path(path_str).resolve()
            base_dir = base_input.parent if base_input.is_file() else base_input
        base_dir = base_dir.resolve()

        for file_info in file_infos:
            try:
                with open(file_info.path, 'r', encoding='utf-8') as f:
                    content = f.read()
                relative_path = Path(os.path.relpath(file_info.path, start=str(base_dir))).as_posix()
                file_data = FileData(
                    path=file_info.path,
                    relative_path=relative_path,
                    content=content,
                    size=len(content),  # Use actual content size
                    extension=file_info.extension
                )

                if file_data.size > self.max_chunk_size:
                    self.logger.info(
                        "Chunking %s (%d bytes) into pieces <= %d bytes",
                        file_data.relative_path,
                        file_data.size,
                        self.max_chunk_size,
                    )
                    chunked = chunk_file_data(file_data, max_chunk_size=self.max_chunk_size)
                    self.logger.info(
                        "Created %d chunks for %s",
                        len(chunked),
                        file_data.relative_path,
                    )
                    files_data.extend(chunked)
                else:
                    files_data.append(file_data)
            except Exception as e:
                self.logger.warning("Failed to load %s: %s", file_info.path, e)
                
        return files_data

    def _should_include_file(self, file_path: Path, relative_path: Path) -> bool:
        """Determine if a file should be included in processing."""

        if not self._matches_patterns(relative_path):
            return False

        if self.max_file_size is not None:
            try:
                if file_path.stat().st_size > self.max_file_size:
                    return False
            except (OSError, PermissionError):
                return False
        
        # Check if it's a test file (if exclusion is enabled)
        if self.exclude_tests:
            filename_lower = file_path.name.lower()
            if any(pattern in filename_lower for pattern in self.EXCLUDE_PATTERNS):
                return False
        
        # Check if it's a readable text file
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Try to read first 1KB to verify it's text
                f.read(1024)
            return True
        except (UnicodeDecodeError, OSError, PermissionError):
            return False

    def _matches_patterns(self, relative_path: Path) -> bool:
        """Return True if the relative path matches any configured patterns."""

        if not self.patterns:
            return True

        path_as_posix = relative_path.as_posix()
        filename = relative_path.name

        for pattern in self.patterns:
            normalized = pattern.replace('\\', '/').lstrip('/')
            candidate = path_as_posix if '/' in normalized else filename

            # Use fnmatch to apply glob semantics without pathlib quirks.
            if fnmatch(candidate, normalized):
                return True

        return False

    def _compute_relative_path(self, file_path: Path, base_dir: Path | None) -> Path:
        """Compute the path relative to the detected root for pattern handling."""
        if base_dir is None:
            return Path(file_path.name)

        resolved_file = file_path.resolve()
        resolved_base = base_dir.resolve()
        try:
            return resolved_file.relative_to(resolved_base)
        except ValueError:
            return Path(file_path.name)

    def _infer_base_dir_from_pattern(self, pattern: str) -> Path:
        """Infer the search root from the leading, non-glob portion of a pattern."""
        pattern_path = Path(pattern).expanduser()
        base_parts: list[str] = []

        for part in pattern_path.parts:
            if glob.has_magic(part):
                break
            base_parts.append(part)

        if not base_parts:
            return Path(".").resolve()

        return Path(*base_parts).resolve()
    
    def get_stats(self, files: List[FileInfo]) -> dict:
        """Get statistics about detected files."""
        if not files:
            return {
                "total_files": 0,
                "total_size": 0,
                "extensions": {},
                "largest_file": None,
                "average_size": 0
            }
        
        extensions = {}
        total_size = 0
        largest_file = files[0]
        
        for file_info in files:
            # Count extensions
            ext = file_info.extension
            extensions[ext] = extensions.get(ext, 0) + 1
            
            # Track size
            total_size += file_info.size
            
            # Track largest file
            if file_info.size > largest_file.size:
                largest_file = file_info
        
        return {
            "total_files": len(files),
            "total_size": total_size,
            "extensions": extensions,
            "largest_file": {
                "path": largest_file.path,
                "size": largest_file.size
            },
            "average_size": total_size // len(files)
        }
