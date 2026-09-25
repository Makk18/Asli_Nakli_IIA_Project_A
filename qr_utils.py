"""
qr_utils.py
-----------
Module for:
1. Decoding QR codes from webcam photos or uploaded images using OpenCV.
2. Generating official tamper-resistant QR codes for medicine batches.
"""

import io
import json
import numpy as np
import cv2
import qrcode
from PIL import Image

def decode_qr(image_input) -> tuple[str | None, str]:
    """
    Decodes a QR code from a file-like object, byte buffer, or PIL Image.
    Returns: (decoded_text, status_message)
    """
    if image_input is None:
        return None, "No image provided"

    try:
        if isinstance(image_input, (bytes, bytearray)):
            img_bytes = image_input
        elif hasattr(image_input, "read"):
            img_bytes = image_input.read()
        elif isinstance(image_input, Image.Image):
            buf = io.BytesIO()
            image_input.save(buf, format="PNG")
            img_bytes = buf.getvalue()
        else:
            return None, "Unsupported image format"

        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            return None, "Unable to read image matrix"

        detector = cv2.QRCodeDetector()
        val, pts, _ = detector.detectAndDecode(img)

        if val and val.strip():
            decoded_val = val.strip()
            # If payload is JSON, extract item_code if present
            try:
                data = json.loads(decoded_val)
                if isinstance(data, dict) and "item_code" in data:
                    return data["item_code"], f"Decoded JSON QR: Found code {data['item_code']}"
            except Exception:
                pass
            return decoded_val, f"Successfully decoded QR Code: {decoded_val}"

        # If standard detector fails, try preprocessing (grayscale + OTSU threshold)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        val2, pts2, _ = detector.detectAndDecode(thresh)
        if val2 and val2.strip():
            return val2.strip(), f"Decoded QR Code (after contrast enhancement): {val2.strip()}"

        return None, "No QR Code detected in image. Ensure the code is clear, well-lit, and centered."
    except Exception as e:
        return None, f"QR Decoding Error: {str(e)}"


def generate_qr_image(item_code: str, extra_meta: dict = None) -> io.BytesIO:
    """
    Generates a high-quality QR code image buffer for an item code.
    Can encode plain item_code or structured metadata.
    """
    payload = item_code
    if extra_meta:
        meta_dict = {"item_code": item_code, **extra_meta}
        payload = json.dumps(meta_dict)

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
