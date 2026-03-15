"""
conftest.py
-----------
Stubs out heavy ML dependencies (torch, segment_anything) so that the
FastAPI application can be imported and tested without a GPU or full
PyTorch installation.
"""
from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock


def _make_torch_stub() -> types.ModuleType:
    """Return a minimal torch stub sufficient for main.py to import."""
    torch = types.ModuleType("torch")
    torch.cuda = MagicMock()
    torch.cuda.is_available = MagicMock(return_value=False)
    torch.no_grad = MagicMock()
    # Add sub-modules that segment_anything may reference
    for sub in ("nn", "optim", "utils", "Tensor"):
        setattr(torch, sub, MagicMock())
    return torch


def _make_segment_anything_stub() -> types.ModuleType:
    """Return a minimal segment_anything stub."""
    sa = types.ModuleType("segment_anything")
    sa.SamPredictor = MagicMock()
    sa.sam_model_registry = MagicMock()
    return sa


# Register stubs *before* any test imports main.py
if "torch" not in sys.modules:
    sys.modules["torch"] = _make_torch_stub()
    sys.modules["torch.nn"] = MagicMock()
    sys.modules["torch.optim"] = MagicMock()
    sys.modules["torch.utils"] = MagicMock()
    sys.modules["torch.utils.data"] = MagicMock()

if "segment_anything" not in sys.modules:
    sys.modules["segment_anything"] = _make_segment_anything_stub()
