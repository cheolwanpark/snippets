import asyncio
import os
import sys
import argparse
from src.file_loader import FileLoader
from src.process_queue import ProcessQueue


def main():
    parser = argparse.ArgumentParser(description='Extract code snippets from source files or directories')
    parser.add_argument('path', help='Path to the source code file or directory to analyze')
    parser.add_argument('--top-n', type=int, default=10, 
                       help='Maximum number of snippets to extract per file (default: 10)')
    parser.add_argument('--output', '-o', type=str, 
                       help='Output file path (if not specified, prints to stdout)')
    parser.add_argument('--concurrency', type=int, default=5,
                       help='Maximum number of concurrent processing jobs (default: 5)')
    parser.add_argument('--max-file-size', type=int, default=1048576,
                       help='Maximum file size to process in bytes (default: 1MB)')
    parser.add_argument('--include-tests', action='store_true',
                       help='Include test files in processing (default: exclude)')
    parser.add_argument('--extensions', type=str, nargs='+',
                       help='File extensions to include (default: py js ts rs)')
    
    args = parser.parse_args()
    
    # Validate path
    if not os.path.exists(args.path):
        print(f"Error: Path does not exist: {args.path}", file=sys.stderr)
        sys.exit(1)
    
    # Prepare extensions
    extensions = {f".{ext.lstrip('.')}" for ext in args.extensions} if args.extensions else None
    
    # Load all files into memory
    print(f"📁 Loading files from: {args.path}")
    loader = FileLoader(
        extensions=extensions,
        max_file_size=args.max_file_size,
        exclude_tests=not args.include_tests
    )
    
    files_data = loader.load_files(args.path)
    
    if not files_data:
        print("❌ No qualifying files found", file=sys.stderr)
        sys.exit(1)
    
    print(f"📊 Loaded {len(files_data)} files into memory")
    
    # Process files concurrently
    try:
        with ProcessQueue(max_concurrency=args.concurrency) as queue:
            result = asyncio.run(queue.process(files_data, args.top_n))
            
            # Output results
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(result)
                print(f"✅ Results saved to: {args.output}")
            else:
                print(result)
                
    except KeyboardInterrupt:
        print("\n⚠️ Processing interrupted", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()