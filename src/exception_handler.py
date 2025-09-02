import logging
import traceback
from typing import Dict, Any, List, Optional
from pathlib import Path


class ErrorHandler:
    """Centralized error handling and logging for snippet extraction."""
    
    def __init__(self, log_level: str = "INFO"):
        self.logger = self._setup_logging(log_level)
        self.errors: List[Dict[str, Any]] = []
    
    def _setup_logging(self, level: str) -> logging.Logger:
        """Configure structured logging."""
        logger = logging.getLogger("snippet_extractor")
        logger.setLevel(getattr(logging, level.upper()))
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def handle_error(self, error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process and log error with context information."""
        error_info = {
            "type": type(error).__name__,
            "message": str(error),
            "context": context,
            "traceback": traceback.format_exc() if self.logger.level <= logging.DEBUG else None
        }
        
        # Log the error
        self.logger.error(
            f"{error_info['type']}: {error_info['message']} | Context: {context}"
        )
        
        # Store for aggregation
        self.errors.append(error_info)
        
        return error_info
    
    def collect_file_error(self, error: Exception, file_path: str, operation: str) -> Dict[str, Any]:
        """Collect file operation error with context."""
        context = {
            "file_path": file_path,
            "operation": operation,
            "file_name": Path(file_path).name if file_path else "unknown"
        }
        return self.handle_error(error, context)
    
    def collect_processing_error(self, error: Exception, filename: str, stage: str) -> Dict[str, Any]:
        """Collect processing error with context."""
        context = {
            "filename": filename,
            "stage": stage,
            "processing": True
        }
        return self.handle_error(error, context)
    
    def should_retry(self, error: Exception) -> bool:
        """Determine if error is retryable."""
        from claude_agent_toolkit import ConnectionError
        
        retryable_types = (
            ConnectionError,
            TimeoutError,
            OSError  # Network-related OS errors
        )
        
        return isinstance(error, retryable_types)
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Generate summary of all collected errors."""
        if not self.errors:
            return {"total_errors": 0, "error_types": {}, "failed_files": []}
        
        error_types = {}
        failed_files = []
        
        for error in self.errors:
            error_type = error["type"]
            error_types[error_type] = error_types.get(error_type, 0) + 1
            
            # Collect failed files
            context = error.get("context", {})
            if "file_path" in context:
                failed_files.append({
                    "file": context["file_path"],
                    "error": error["message"],
                    "operation": context.get("operation", "unknown")
                })
            elif "filename" in context:
                failed_files.append({
                    "file": context["filename"],
                    "error": error["message"],
                    "stage": context.get("stage", "unknown")
                })
        
        return {
            "total_errors": len(self.errors),
            "error_types": error_types,
            "failed_files": failed_files
        }
    
    def clear_errors(self):
        """Clear collected errors."""
        self.errors.clear()
    
    def format_error_report(self) -> str:
        """Format user-friendly error report."""
        summary = self.get_error_summary()
        
        if summary["total_errors"] == 0:
            return ""
        
        lines = [
            f"\n⚠️  Error Summary: {summary['total_errors']} errors occurred",
            ""
        ]
        
        # Error types breakdown
        if summary["error_types"]:
            lines.append("Error Types:")
            for error_type, count in summary["error_types"].items():
                lines.append(f"  • {error_type}: {count}")
            lines.append("")
        
        # Failed files
        if summary["failed_files"]:
            lines.append("Failed Files:")
            for failure in summary["failed_files"][:5]:  # Show first 5
                file_name = Path(failure["file"]).name
                lines.append(f"  • {file_name}: {failure['error']}")
            
            if len(summary["failed_files"]) > 5:
                lines.append(f"  ... and {len(summary['failed_files']) - 5} more")
        
        return "\n".join(lines)


# Global error handler instance
error_handler = ErrorHandler()