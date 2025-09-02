import os
from typing import List, NamedTuple
from pathlib import Path


class FileInfo(NamedTuple):
    """Information about a detected source file."""
    path: str
    size: int
    extension: str


class FileData(NamedTuple):
    """Pre-loaded file data for async processing."""
    path: str
    filename: str
    content: str
    size: int
    extension: str


class FileLoader:
    """Smart file discovery with filtering for source code analysis."""
    
    # Supported file extensions
    EXTENSIONS = {'.py', '.js', '.ts', '.rs'}
    
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
    
    # Maximum file size to process (1MB)
    MAX_FILE_SIZE = 1024 * 1024
    
    def __init__(self, extensions=None, max_file_size=None, exclude_tests=True):
        """Initialize file loader with optional custom settings.
        
        Args:
            extensions: Set of file extensions to include (default: .py, .js, .ts, .rs)
            max_file_size: Maximum file size in bytes (default: 1MB)
            exclude_tests: Whether to exclude test files (default: True)
        """
        self.extensions = extensions or self.EXTENSIONS
        self.max_file_size = max_file_size or self.MAX_FILE_SIZE
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
        path_obj = Path(path)
        
        if not path_obj.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        
        if path_obj.is_file():
            return self._analyze_single_file(path_obj)
        elif path_obj.is_dir():
            return self._analyze_directory(path_obj)
        else:
            raise ValueError(f"Path is neither file nor directory: {path}")
    
    def _analyze_single_file(self, file_path: Path) -> List[FileInfo]:
        """Analyze a single file and return FileInfo if it qualifies."""
        if not self._should_include_file(file_path):
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
                    
                    if self._should_include_file(file_path):
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
        
        for file_info in file_infos:
            try:
                with open(file_info.path, 'r', encoding='utf-8') as f:
                    content = f.read()
                files_data.append(FileData(
                    path=file_info.path,
                    filename=os.path.basename(file_info.path),
                    content=content,
                    size=len(content),  # Use actual content size
                    extension=file_info.extension
                ))
            except Exception as e:
                from tqdm import tqdm
                tqdm.write(f"⚠️ Failed to load {file_info.path}: {e}")
                
        return files_data
    
    def _should_include_file(self, file_path: Path) -> bool:
        """Determine if a file should be included in processing."""
        # Check extension
        if file_path.suffix not in self.extensions:
            return False
        
        # Check file size
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