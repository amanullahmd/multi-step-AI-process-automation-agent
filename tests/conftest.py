"""Shared test fixtures."""

import os
import sys
from pathlib import Path

# Ensure src/ is on the path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Set a dummy API key for tests that don't actually call OpenAI
os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy-key-for-testing")
