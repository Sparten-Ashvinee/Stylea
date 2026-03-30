"""
tests/test_api.py
-----------------
Unit tests for the Stylea backend API.

Run with:
    pytest tests/test_api.py -v
"""
from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_jpeg_bytes(width: int = 200, height: int = 200, color=(100, 149, 237)) -> bytes:
    """Create a solid-colour JPEG image and return its bytes."""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture()
def client():
    """Return a TestClient with a mocked SAM predictor so no GPU/checkpoint is needed."""
    mock_predictor = MagicMock()

    h, w = 200, 200
    # Return three masks + scores; the first mask covers the full image
    full_mask = np.ones((h, w), dtype=bool)
    mock_predictor.predict.return_value = (
        np.array([full_mask, full_mask, full_mask]),
        np.array([0.9, 0.7, 0.5]),
        None,
    )

    with patch("main._get_predictor", return_value=mock_predictor):
        from main import app  # import after the patch is active

        yield TestClient(app)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# /segment
# ---------------------------------------------------------------------------


class TestSegmentEndpoint:
    def test_returns_jpeg(self, client):
        resp = client.post(
            "/segment",
            files={"fashion_image": ("fashion.jpg", _make_jpeg_bytes(), "image/jpeg")},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/jpeg"

    def test_response_is_valid_image(self, client):
        resp = client.post(
            "/segment",
            files={"fashion_image": ("fashion.jpg", _make_jpeg_bytes(), "image/jpeg")},
        )
        img = Image.open(io.BytesIO(resp.content))
        assert img.mode == "RGB"
        assert img.width > 0
        assert img.height > 0

    def test_missing_file_returns_422(self, client):
        resp = client.post("/segment")
        assert resp.status_code == 422

    def test_invalid_file_returns_400(self, client):
        resp = client.post(
            "/segment",
            files={"fashion_image": ("bad.jpg", b"not-an-image", "image/jpeg")},
        )
        assert resp.status_code == 400

    def test_size_headers_present(self, client):
        resp = client.post(
            "/segment",
            files={"fashion_image": ("fashion.jpg", _make_jpeg_bytes(), "image/jpeg")},
        )
        assert "x-stylea-width" in resp.headers
        assert "x-stylea-height" in resp.headers


# ---------------------------------------------------------------------------
# /tryon
# ---------------------------------------------------------------------------


class TestTryOnEndpoint:
    def test_returns_jpeg(self, client):
        resp = client.post(
            "/tryon",
            files={
                "person_image": ("person.jpg", _make_jpeg_bytes(color=(200, 150, 100)), "image/jpeg"),
                "fashion_image": ("fashion.jpg", _make_jpeg_bytes(color=(50, 100, 200)), "image/jpeg"),
            },
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/jpeg"

    def test_response_is_valid_image(self, client):
        resp = client.post(
            "/tryon",
            files={
                "person_image": ("person.jpg", _make_jpeg_bytes(), "image/jpeg"),
                "fashion_image": ("fashion.jpg", _make_jpeg_bytes(), "image/jpeg"),
            },
        )
        img = Image.open(io.BytesIO(resp.content))
        assert img.mode == "RGB"

    def test_missing_person_returns_422(self, client):
        resp = client.post(
            "/tryon",
            files={
                "fashion_image": ("fashion.jpg", _make_jpeg_bytes(), "image/jpeg"),
            },
        )
        assert resp.status_code == 422

    def test_missing_fashion_returns_422(self, client):
        resp = client.post(
            "/tryon",
            files={
                "person_image": ("person.jpg", _make_jpeg_bytes(), "image/jpeg"),
            },
        )
        assert resp.status_code == 422

    def test_invalid_blend_alpha_returns_422(self, client):
        resp = client.post(
            "/tryon",
            files={
                "person_image": ("person.jpg", _make_jpeg_bytes(), "image/jpeg"),
                "fashion_image": ("fashion.jpg", _make_jpeg_bytes(), "image/jpeg"),
            },
            data={"blend_alpha": "1.5"},
        )
        assert resp.status_code == 422

    def test_custom_blend_alpha(self, client):
        resp = client.post(
            "/tryon",
            files={
                "person_image": ("person.jpg", _make_jpeg_bytes(), "image/jpeg"),
                "fashion_image": ("fashion.jpg", _make_jpeg_bytes(), "image/jpeg"),
            },
            data={"blend_alpha": "0.5"},
        )
        assert resp.status_code == 200

    def test_size_headers_present(self, client):
        resp = client.post(
            "/tryon",
            files={
                "person_image": ("person.jpg", _make_jpeg_bytes(), "image/jpeg"),
                "fashion_image": ("fashion.jpg", _make_jpeg_bytes(), "image/jpeg"),
            },
        )
        assert "x-stylea-width" in resp.headers
        assert "x-stylea-height" in resp.headers
