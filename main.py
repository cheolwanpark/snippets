import argparse
import logging
import os
import sys

from tqdm import tqdm

from src.orchestration import ExtractionPipeline


logger = logging.getLogger("snippet_extractor")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract code snippets from source files or directories"
    )
    parser.add_argument(
        "path",
        help="Path to the source code file or directory to analyze",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Maximum number of snippets to extract per file (default: 10)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output file path (if not specified, prints to stdout)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Maximum number of concurrent processing jobs (default: 5)",
    )
    parser.add_argument(
        "--max-file-size",
        type=int,
        default=1_048_576,
        help="Maximum file size to process in bytes (default: 1MB)",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test files in processing (default: exclude)",
    )
    parser.add_argument(
        "--extensions",
        type=str,
        nargs="+",
        help="File extensions to include (default: py js ts rs)",
    )

    args = parser.parse_args()

    if not os.path.exists(args.path):
        print(f"Error: Path does not exist: {args.path}", file=sys.stderr)
        sys.exit(1)

    extensions = args.extensions if args.extensions else None

    pipeline = ExtractionPipeline(
        max_concurrency=args.concurrency,
        extensions=extensions,
        max_file_size=args.max_file_size,
        include_tests=args.include_tests,
    )

    try:
        snippets = pipeline.run(args.path, top_n=args.top_n)
    except KeyboardInterrupt:
        print("\n⚠️ Processing interrupted", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception:
        logger.exception("Fatal error during snippet extraction")
        print("\n❌ Fatal error occurred. See log for details.", file=sys.stderr)
        sys.exit(1)

    stats = pipeline.last_run_stats or {}
    if stats.get("total_files", 0) == 0:
        print("❌ No qualifying files found", file=sys.stderr)
        sys.exit(1)

    output_text = pipeline.storage.to_file()

    if args.output:
        with open(args.output, "w", encoding="utf-8") as file_handle:
            file_handle.write(output_text)
        tqdm.write(f"✅ Results saved to: {args.output}")
    else:
        print(output_text)

    if pipeline.errors:
        tqdm.write("\n⚠️  Error Summary:")
        for message in pipeline.errors[:5]:
            tqdm.write(f"  • {message}")
        if len(pipeline.errors) > 5:
            remaining = len(pipeline.errors) - 5
            tqdm.write(f"  ... and {remaining} more")

    if snippets:
        logger.debug("Extracted %d snippets", len(snippets))


if __name__ == "__main__":
    main()
