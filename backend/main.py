"""
Stylea Backend – AI Fashion Try-On API
--------------------------------------
Endpoints
  POST /segment  – Use SAM to segment clothing from a fashion image.
  POST /tryon    – Virtual try-on: overlay segmented clothing on a person photo.
  GET  /health   – Liveness probe.
"""

from __future__ import annotations

import io
import logging
import os
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import torch
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from PIL import Image
from segment_anything import SamPredictor, sam_model_registry

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SAM_CHECKPOINT_ENV = "SAM_CHECKPOINT"
DEFAULT_SAM_CHECKPOINT = str(
    Path(__file__).parent / "models" / "sam_vit_b_01ec64.pth"
)
SAM_MODEL_TYPE = "vit_b"

MAX_IMAGE_SIZE = (1024, 1024)   # Resize large images before processing
TRYON_BLEND_ALPHA = 0.92        # Opacity of the clothing layer

# ---------------------------------------------------------------------------
# App & CORS
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Stylea AI API",
    description="SAM-powered clothing segmentation and virtual try-on.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# SAM initialisation (lazy – loaded once on first use)
# ---------------------------------------------------------------------------
_sam_predictor: Optional[SamPredictor] = None


def _get_predictor() -> SamPredictor:
    global _sam_predictor
    if _sam_predictor is None:
        checkpoint = os.environ.get(SAM_CHECKPOINT_ENV, DEFAULT_SAM_CHECKPOINT)
        if not Path(checkpoint).exists():
            raise RuntimeError(
                f"SAM checkpoint not found at '{checkpoint}'. "
                "Set the SAM_CHECKPOINT environment variable or run "
                "'python download_models.py' to download it."
            )
        logger.info("Loading SAM model from %s …", checkpoint)
        device = "cuda" if torch.cuda.is_available() else "cpu"

        # Build the model architecture without loading weights so that we
        # control the torch.load call.  Passing checkpoint=None skips SAM's
        # internal torch.load, which would not set weights_only=True and is
        # therefore vulnerable to deserialization attacks (CVE / GHSA for
        # torch < 2.6.0).  We load the state dict ourselves with
        # weights_only=True, which restricts unpickling to tensors and basic
        # Python scalars only.
        sam = sam_model_registry[SAM_MODEL_TYPE](checkpoint=None)
        with open(checkpoint, "rb") as f:
            state_dict = torch.load(f, map_location=device, weights_only=True)
        sam.load_state_dict(state_dict)
        sam.to(device=device)
        _sam_predictor = SamPredictor(sam)
        logger.info("SAM model loaded on %s.", device)
    return _sam_predictor


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _read_image(upload: UploadFile) -> np.ndarray:
    """Read an uploaded file into an RGB numpy array."""
    raw = upload.file.read()
    pil = Image.open(io.BytesIO(raw)).convert("RGB")
    pil.thumbnail(MAX_IMAGE_SIZE, Image.LANCZOS)
    return np.array(pil)


def _pil_to_jpeg_bytes(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def _segment_largest_object(
    predictor: SamPredictor,
    image_rgb: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Run SAM with a centre-point prompt and return:
      (mask [H,W bool], masked_image [H,W,3 uint8])
    The centre of the image is used as the foreground prompt, which works well
    for fashion photos where clothing is centred.
    """
    predictor.set_image(image_rgb)

    h, w = image_rgb.shape[:2]
    # Multiple seed points spread across the centre region for robustness
    cx, cy = w // 2, h // 2
    input_points = np.array([
        [cx, cy],
        [cx, int(cy * 0.7)],
        [cx, int(cy * 1.3)],
    ])
    input_labels = np.array([1, 1, 1])  # all foreground

    masks, scores, _ = predictor.predict(
        point_coords=input_points,
        point_labels=input_labels,
        multimask_output=True,
    )
    # Pick the mask with the highest score
    best_idx = int(np.argmax(scores))
    mask: np.ndarray = masks[best_idx]  # bool [H, W]

    # Apply mask to get the segmented clothing on a white background
    masked = image_rgb.copy()
    masked[~mask] = 255

    return mask, masked


def _resize_to_fit(src: np.ndarray, target_shape: tuple[int, int]) -> np.ndarray:
    """Resize *src* (H,W,C) to fit within *target_shape* (H, W), keep aspect."""
    th, tw = target_shape
    sh, sw = src.shape[:2]
    scale = min(tw / sw, th / sh)
    new_w, new_h = int(sw * scale), int(sh * scale)
    return cv2.resize(src, (new_w, new_h), interpolation=cv2.INTER_AREA)


def _overlay_clothing(
    person_rgb: np.ndarray,
    clothing_rgb: np.ndarray,
    clothing_mask: np.ndarray,
    alpha: float = TRYON_BLEND_ALPHA,
) -> np.ndarray:
    """
    Overlay the segmented clothing onto the person image.

    Strategy
    --------
    1. Resize clothing + mask to match the person image size.
    2. Place it centred on the torso area (upper 30–70 % of the image).
    3. Alpha-blend only in the clothing region.
    """
    ph, pw = person_rgb.shape[:2]

    # --- Place clothing in the torso area ---
    torso_top = int(ph * 0.20)
    torso_bot = int(ph * 0.75)
    torso_h = torso_bot - torso_top
    torso_w = pw

    clothing_resized = _resize_to_fit(clothing_rgb, (torso_h, torso_w))
    mask_uint8 = (clothing_mask.astype(np.uint8) * 255)
    mask_resized = cv2.resize(mask_uint8, (clothing_resized.shape[1], clothing_resized.shape[0]),
                              interpolation=cv2.INTER_NEAREST)
    mask_bool = mask_resized > 127

    ch, cw = clothing_resized.shape[:2]

    # Centre the clothing horizontally
    x_offset = (pw - cw) // 2
    y_offset = torso_top

    # Clip to image bounds
    x1, y1 = max(x_offset, 0), max(y_offset, 0)
    x2, y2 = min(x_offset + cw, pw), min(y_offset + ch, ph)
    cx1 = x1 - x_offset
    cy1 = y1 - y_offset
    cx2 = cx1 + (x2 - x1)
    cy2 = cy1 + (y2 - y1)

    result = person_rgb.copy()
    roi = result[y1:y2, x1:x2]
    cloth_roi = clothing_resized[cy1:cy2, cx1:cx2]
    mask_roi = mask_bool[cy1:cy2, cx1:cx2]

    # Blend
    roi[mask_roi] = (
        alpha * cloth_roi[mask_roi]
        + (1.0 - alpha) * roi[mask_roi]
    ).astype(np.uint8)

    return result


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", summary="Health check")
def health():
    return {"status": "ok"}


@app.post(
    "/segment",
    summary="Segment clothing from a fashion image",
    responses={200: {"content": {"image/jpeg": {}}}},
)
async def segment(
    fashion_image: UploadFile = File(..., description="Fashion / clothing photo"),
):
    """
    Accept a fashion image and return the **segmented clothing** on a white background.

    The SAM model is used with a centre-point prompt, which works well for
    product-style fashion photos where the garment is centred.
    """
    try:
        image_rgb = _read_image(fashion_image)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Cannot decode image: {exc}") from exc

    try:
        predictor = _get_predictor()
        _mask, masked_image = _segment_largest_object(predictor, image_rgb)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Segmentation failed")
        raise HTTPException(status_code=500, detail=f"Segmentation error: {exc}") from exc

    pil_result = Image.fromarray(masked_image)
    return StreamingResponse(
        io.BytesIO(_pil_to_jpeg_bytes(pil_result)),
        media_type="image/jpeg",
        headers={"X-Stylea-Width": str(pil_result.width),
                 "X-Stylea-Height": str(pil_result.height)},
    )


@app.post(
    "/tryon",
    summary="Virtual try-on: overlay clothing on a person photo",
    responses={200: {"content": {"image/jpeg": {}}}},
)
async def tryon(
    person_image: UploadFile = File(..., description="Photo of the person"),
    fashion_image: UploadFile = File(..., description="Fashion / clothing photo"),
    blend_alpha: float = Form(
        default=TRYON_BLEND_ALPHA,
        ge=0.0,
        le=1.0,
        description="Clothing opacity (0–1). Default 0.92.",
    ),
):
    """
    Accept a **person photo** and a **fashion image**, segment the clothing from
    the fashion image using SAM, and composite it onto the person photo.

    Returns the composited try-on image as JPEG.
    """
    try:
        person_rgb = _read_image(person_image)
        fashion_rgb = _read_image(fashion_image)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Cannot decode image: {exc}") from exc

    try:
        predictor = _get_predictor()
        clothing_mask, _masked = _segment_largest_object(predictor, fashion_rgb)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Segmentation failed during try-on")
        raise HTTPException(status_code=500, detail=f"Segmentation error: {exc}") from exc

    try:
        result_rgb = _overlay_clothing(
            person_rgb, fashion_rgb, clothing_mask, alpha=blend_alpha
        )
    except Exception as exc:
        logger.exception("Overlay failed")
        raise HTTPException(status_code=500, detail=f"Overlay error: {exc}") from exc

    pil_result = Image.fromarray(result_rgb)
    return StreamingResponse(
        io.BytesIO(_pil_to_jpeg_bytes(pil_result)),
        media_type="image/jpeg",
        headers={"X-Stylea-Width": str(pil_result.width),
                 "X-Stylea-Height": str(pil_result.height)},
    )


# ---------------------------------------------------------------------------
# Entry point (dev)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
