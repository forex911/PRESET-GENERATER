from fastapi import APIRouter, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
import os
import uuid
import json
import asyncio

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
    # Save uploads
    input_path = f"temp/{uuid.uuid4()}_{input_image.filename}"
    ref_path = f"temp/{uuid.uuid4()}_{reference_image.filename}"

    with open(input_path, "wb") as f:
        f.write(await input_image.read())

    with open(ref_path, "wb") as f:
        f.write(await reference_image.read())

    async def event_generator():
        try:
            # Step 0: Analyzing
            yield f"data: {json.dumps({'step': 0, 'status': 'analyzing'})}\n\n"
            await asyncio.sleep(0.1)
            # ---- PIPELINE (UNCHANGED) ----
            input_feat = analyze_image(input_path)
            ref_feat = analyze_image(ref_path)

            # Step 1: Grading
            yield f"data: {json.dumps({'step': 1, 'status': 'grading'})}\n\n"
            await asyncio.sleep(0.1)
            lab_params = lab_color_transfer(input_path, ref_path)

            # AI generation (multimodal vision + math base)
            raw_params = generate_lightroom_params(lab_params, input_path, ref_path)

            # Step 2: Calibrating
            yield f"data: {json.dumps({'step': 2, 'status': 'calibrating'})}\n\n"
            await asyncio.sleep(0.1)
            # ✅ SAFETY & CINEMATIC CLAMP (NEW, NON-DESTRUCTIVE)
            params = apply_color_safety(raw_params)

            # Step 3: Exporting
            yield f"data: {json.dumps({'step': 3, 'status': 'exporting'})}\n\n"
            await asyncio.sleep(0.1)
            preset_path = generate_xmp_preset(params, PRESET_DIR)

            yield f"data: {json.dumps({'success': True, 'preset_name': os.path.basename(preset_path), 'download_url': f'/download/{os.path.basename(preset_path)}'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'success': False, 'error': str(e)})}\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")


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
