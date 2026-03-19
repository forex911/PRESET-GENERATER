from fastapi import APIRouter, UploadFile, File
from fastapi.responses import FileResponse
import os
import uuid

from services.image_analysis import analyze_image
from services.feature_diff import compute_feature_difference
from services.llm_service import generate_lightroom_params
from services.preset_generator import generate_xmp_preset
from services.lab_color_transfer import lab_color_transfer
# ✅ NEW (safe post-processing layer)
from services.color_safety import apply_color_safety

router = APIRouter()

PRESET_DIR = "temp/presets"
os.makedirs(PRESET_DIR, exist_ok=True)


@router.post("/generate-preset")
async def generate_preset(
    input_image: UploadFile = File(...),
    reference_image: UploadFile = File(...)
):
    try:
        # Save uploads
        input_path = f"temp/{uuid.uuid4()}_{input_image.filename}"
        ref_path = f"temp/{uuid.uuid4()}_{reference_image.filename}"

        with open(input_path, "wb") as f:
            f.write(await input_image.read())

        with open(ref_path, "wb") as f:
            f.write(await reference_image.read())

        # ---- PIPELINE (UNCHANGED) ----
        input_feat = analyze_image(input_path)
        ref_feat = analyze_image(ref_path)

        lab_params = lab_color_transfer(input_path, ref_path)

        # AI generation (multimodal vision + math base)
        raw_params = generate_lightroom_params(lab_params, input_path, ref_path)

        # ✅ SAFETY & CINEMATIC CLAMP (NEW, NON-DESTRUCTIVE)
        params = apply_color_safety(raw_params)

        preset_path = generate_xmp_preset(params, PRESET_DIR)

        return {
            "success": True,
            "preset_name": os.path.basename(preset_path),
            "download_url": f"/download/{os.path.basename(preset_path)}"
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/download/{filename}")
def download_preset(filename: str):
    file_path = os.path.join(PRESET_DIR, filename)
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream"
    )

@router.get("/status")
def server_status():
    return {"status": "online"}
