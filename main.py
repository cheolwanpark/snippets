import sys
import argparse
from src.snippet_extractor import extract_snippets_sync


def main():
    parser = argparse.ArgumentParser(description='Extract code snippets from source files')
    parser.add_argument('file_path', help='Path to the source code file to analyze')
    parser.add_argument('--top-n', type=int, default=10, 
                       help='Maximum number of snippets to extract (default: 10)')
    parser.add_argument('--output', '-o', type=str, 
                       help='Output file path (if not specified, prints to stdout)')
    
    args = parser.parse_args()
    
    # Extract snippets
    result = extract_snippets_sync(args.file_path, args.top_n)
    
    if result["success"]:
        if args.output:
            try:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(result["response"])
                print(f"Snippets extracted and saved to: {args.output}")
            except Exception as e:
                print(f"Error writing to output file: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            print(result["response"])
    else:
        print(f"Error: {result['response']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
