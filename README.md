# Stylea
> **Try Any Outfit Instantly** – AI-powered virtual fashion try-on for Android

Stylea lets you upload any fashion photo, automatically segments the clothing
using **Meta's Segment Anything Model (SAM)**, and composites it onto your
own photo so you can see exactly how the outfit would look on you.

---

## Architecture

![SAM Model Architecture](https://raw.githubusercontent.com/facebookresearch/segment-anything/main/assets/model_diagram.png)

> **Figure:** SAM's three components — an image encoder (ViT-based), a prompt encoder (handling points, boxes, masks, and text), and a lightweight mask decoder that predicts the segmentation mask in real time.

---

## How It Works

1. **Pick a fashion image** – any product photo of a garment.
2. **Add your photo** – from the gallery or taken with the camera.
3. Tap **"Try It On!"** – the app sends both images to the backend.
4. The backend runs **SAM** to segment the clothing from the fashion photo.
5. The segmented garment is composited onto your photo using alpha-blending.
6. The result is displayed in-app with options to **save** or **share**.

```
Fashion Image ──► SAM Segmentation ──► Clothing Mask
                                             │
Your Photo ──────────────────────────► Alpha Composite ──► Try-On Result
```

---

## Backend Setup

### Prerequisites
- Python 3.10+
- (Recommended) NVIDIA GPU with CUDA 11.8+ for fast inference

### Quick start

```bash
cd backend

# 1. Install dependencies
pip install -r requirements.txt

# 2. Download the SAM ViT-B checkpoint (~375 MB)
python download_models.py

# 3. Start the server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API is now available at `http://localhost:8000`.
Interactive docs: `http://localhost:8000/docs`

### Docker

```bash
cd backend
docker build -t stylea-backend .
docker run -p 8000:8000 --gpus all stylea-backend
```

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `SAM_CHECKPOINT` | `models/sam_vit_b_01ec64.pth` | Path to SAM checkpoint file |

### Running tests

```bash
cd backend
pytest tests/ -v
```

---

## Android App Setup

### Prerequisites
- Android Studio Hedgehog (2023.1.1) or later
- Android SDK 34
- Java 8+

### Configuration

1. Open `app/` in Android Studio.
2. Edit `app/app/build.gradle` and update `BACKEND_URL` to your server's IP:

```groovy
buildConfigField "String", "BACKEND_URL", "\"http://YOUR_SERVER_IP:8000\""
```

> **Emulator shortcut:** The default `10.0.2.2` points to the host machine when
> running in the Android Emulator, so the default works out-of-the-box if the
> backend runs on the same machine.

3. Build and run on a device or emulator (API 26+):

```bash
cd app
./gradlew assembleDebug
```

### App Permissions
- `INTERNET` – backend API calls
- `CAMERA` – selfie capture
- `READ_MEDIA_IMAGES` / `READ_EXTERNAL_STORAGE` – gallery access

---

## API Reference

### `GET /health`
Returns `{"status": "ok"}` when the server is running.

### `POST /segment`
Segment clothing from a fashion image.

| Field | Type | Description |
|---|---|---|
| `fashion_image` | `file` | Fashion / clothing photo (JPEG/PNG) |

Returns: JPEG image of the segmented clothing on a white background.

Response headers: `X-Stylea-Width`, `X-Stylea-Height`.

### `POST /tryon`
Virtual try-on: overlay clothing onto a person photo.

| Field | Type | Default | Description |
|---|---|---|---|
| `person_image` | `file` | – | Photo of the person |
| `fashion_image` | `file` | – | Fashion / clothing photo |
| `blend_alpha` | `float` | `0.92` | Clothing opacity (0–1) |

Returns: JPEG composited try-on image.

---

## License

MIT – see [LICENSE](LICENSE).
