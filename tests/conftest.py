import sys
from pathlib import Path

# Make the crumb-llm package importable when tests run from the repo without an
# editable install. CRUMB parsing delegates to crumb_core, the single normative
# implementation of the grammar.
_PKG_ROOT = Path(__file__).resolve().parent.parent
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

import pytest  # noqa: E402

EXAMPLES = _PKG_ROOT / "examples"


@pytest.fixture
def basic_crumb() -> Path:
    return EXAMPLES / "basic.crumb"


@pytest.fixture
def example_pack() -> Path:
    return EXAMPLES / "pack"
