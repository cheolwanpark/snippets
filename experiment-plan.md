# Minimal Pattern Extractor - Simple Implementation Plan

## Overview
A bare-bones pattern extractor using Claude Code SDK. No bells and whistles - just extract patterns from code files and save the results.

## Project Structure (3 files only)
```
minimal-extractor/
├── extractor.py       # Main script - everything in one file
├── config.py          # Hardcoded configuration
└── prompt.txt         # The extraction prompt template
```

## File 1: `config.py`
```python
# Configuration - all hardcoded values
SUPPORTED_EXTENSIONS = ['.py', '.js', '.ts']
IGNORE_PATTERNS = ['node_modules', '.git', '__pycache__', 'venv']
RATE_LIMIT_SECONDS = 1
OUTPUT_DIR = './extracted_patterns'
```

## File 2: `prompt.txt`
```
You are a code pattern extraction expert. Extract useful code snippets from the following file.

File: {filename}
Content:
{content}

Find patterns that show:
- How libraries/APIs are used
- Best practices (error handling, retries, resource management)

For each pattern, output in this YAML format:
---
name: <short descriptive name>
snippet: |
  <exact code from file>
description: >
  <what it does and why it's useful>

Output only YAML, nothing else. If no patterns found, output:
---
name: none
snippet: |
  # no patterns found
description: >
  No qualifying patterns in this file.
```

## File 3: `extractor.py`
```python
import asyncio
import os
import sys
from pathlib import Path
from claude_code_sdk import query, ClaudeCodeOptions, AssistantMessage, TextBlock
import logging
import time

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

# Import config
from config import *

class SimpleExtractor:
    def __init__(self):
        # Load prompt template
        with open('prompt.txt', 'r') as f:
            self.prompt_template = f.read()
        
        # Create output directory
        Path(OUTPUT_DIR).mkdir(exist_ok=True)
    
    def find_files(self, directory):
        """Find all code files to process."""
        files = []
        path = Path(directory)
        
        for ext in SUPPORTED_EXTENSIONS:
            for file_path in path.rglob(f'*{ext}'):
                # Skip ignored directories
                if any(ignore in str(file_path) for ignore in IGNORE_PATTERNS):
                    continue
                files.append(file_path)
        
        return files
    
    async def extract_from_file(self, file_path):
        """Extract patterns from a single file using Claude Code SDK."""
        logging.info(f"Processing: {file_path}")
        
        # Read file
        try:
            content = file_path.read_text()
        except Exception as e:
            logging.error(f"Can't read {file_path}: {e}")
            return None
        
        # Format prompt
        prompt = self.prompt_template.format(
            filename=file_path.name,
            content=content
        )
        
        # Call Claude Code SDK
        options = ClaudeCodeOptions(max_turns=1)
        
        final_response = ""
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        # Log intermediate output
                        logging.debug(f"Received: {block.text[:100]}...")
                        final_response += block.text
        
        return final_response
    
    async def run(self, directory):
        """Main extraction process."""
        # Find files
        files = self.find_files(directory)
        logging.info(f"Found {len(files)} files to process")
        
        if not files:
            logging.info("No files found")
            return
        
        # Process each file
        for i, file_path in enumerate(files, 1):
            logging.info(f"[{i}/{len(files)}] {file_path.name}")
            
            # Extract patterns
            result = await self.extract_from_file(file_path)
            
            if result:
                # Save result
                output_file = Path(OUTPUT_DIR) / f"{file_path.stem}_patterns.yaml"
                output_file.write_text(result)
                logging.info(f"  → Saved to {output_file}")
            
            # Rate limit
            if i < len(files):
                time.sleep(RATE_LIMIT_SECONDS)
        
        logging.info(f"\n✓ Done! Results in {OUTPUT_DIR}/")

async def main():
    if len(sys.argv) != 2:
        print("Usage: python extractor.py <directory>")
        sys.exit(1)
    
    directory = sys.argv[1]
    if not Path(directory).exists():
        print(f"Error: {directory} doesn't exist")
        sys.exit(1)
    
    # Check Claude Code CLI
    try:
        import subprocess
        subprocess.run(['claude', '--version'], capture_output=True, check=True)
    except:
        print("Error: Install Claude Code first: npm install -g @anthropic-ai/claude-code")
        sys.exit(1)
    
    # Check API key
    if not os.getenv('ANTHROPIC_API_KEY'):
        print("Error: Set ANTHROPIC_API_KEY environment variable")
        sys.exit(1)
    
    # Run extractor
    extractor = SimpleExtractor()
    await extractor.run(directory)

if __name__ == '__main__':
    asyncio.run(main())
```

## Installation & Usage

### 1. Install Requirements
```bash
# Install Python dependencies
pip install claude-code-sdk

# Install Claude Code CLI
npm install -g @anthropic-ai/claude-code
```

### 2. Set API Key
```bash
export ANTHROPIC_API_KEY="your-api-key"
```

### 3. Run Extractor
```bash
python extractor.py /path/to/code/directory
```

## How It Works

1. **Find Files**: Recursively search for `.py`, `.js`, `.ts` files
2. **Extract Patterns**: Send each file to Claude with the prompt
3. **Save Results**: Write Claude's response to `extracted_patterns/{filename}_patterns.yaml`
4. **Rate Limit**: Wait 1 second between files

## Example Output

Running on a small project:
```
$ python extractor.py ./my-project

Found 3 files to process
[1/3] auth.py
  → Saved to extracted_patterns/auth_patterns.yaml
[2/3] database.js
  → Saved to extracted_patterns/database_patterns.yaml
[3/3] api.ts
  → Saved to extracted_patterns/api_patterns.yaml

✓ Done! Results in extracted_patterns/
```

Each output file contains:
```yaml
---
name: Database connection with retry
snippet: |
  async function connectDB(retries = 3) {
    for (let i = 0; i < retries; i++) {
      try {
        await mongoose.connect(url);
        break;
      } catch (err) {
        if (i === retries - 1) throw err;
        await sleep(1000 * Math.pow(2, i));
      }
    }
  }
description: >
  MongoDB connection with exponential backoff retry logic.
  Attempts connection 3 times with increasing delays.
---
name: API error handler middleware
snippet: |
  app.use((err, req, res, next) => {
    logger.error(err.stack);
    res.status(err.status || 500).json({
      error: err.message || 'Internal server error'
    });
  });
description: >
  Express error handling middleware that logs errors
  and returns standardized JSON error responses.
```

## Key Simplifications

1. **No language detection** - Process all supported files the same way
2. **No YAML parsing** - Save Claude's response directly
3. **No external config** - Everything hardcoded in `config.py`
4. **No min/max lines** - Let Claude decide pattern boundaries
5. **No deduplication** - Each file processed independently
6. **No async concurrency** - Simple sequential processing
7. **No complex error handling** - Just log and continue
8. **Final response only** - Intermediate streaming logged but not processed

## Total Lines of Code
- `extractor.py`: ~100 lines
- `config.py`: ~5 lines  
- `prompt.txt`: ~20 lines
- **Total**: ~125 lines

## Future Extensions (if needed)
- Add file consolidation: `cat extracted_patterns/*.yaml > all_patterns.yaml`
- Add file filtering: `python extractor.py ./src --filter "*.py"`
- Add progress bar: Use `tqdm` for visual progress
- Add parallel processing: Use `asyncio.gather()` for multiple files