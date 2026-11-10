"""mlx_proxy's base-model wrapper repair: only bare claim objects are wrapped, nothing else changes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mlx_proxy import wrap_bare_objects  # noqa: E402


def test_bare_objects_are_wrapped_in_order():
    fixed = wrap_bare_objects('{"quote": "a"}\n\n```json\n{"quote": "b", "search_terms": ["x"]}\n```')
    assert json.loads(fixed) == {"claims": [{"quote": "a"}, {"quote": "b", "search_terms": ["x"]}]}


def test_a_reply_with_a_claims_list_is_left_alone():
    assert wrap_bare_objects('{"claims": [{"quote": "a"}]}') is None
    assert wrap_bare_objects('{"claims": []}') is None


def test_nothing_claim_shaped_is_not_invented():
    assert wrap_bare_objects("I cannot help with that.") is None
    assert wrap_bare_objects('{"account": "Insurance"}') is None
