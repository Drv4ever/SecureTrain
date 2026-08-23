import os
import sys

# makes the flat modules in ai-service/ importable from tests/ no matter
# where pytest is invoked from
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
