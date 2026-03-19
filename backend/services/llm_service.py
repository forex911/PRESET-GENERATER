import os
import json
import base64
import time
import mimetypes

from openai import OpenAI


# Get API key
CLARIFAI_API_KEY = os.getenv("CLARIFAI_API_KEY")

if not CLARIFAI_API_KEY:
    raise ValueError("❌ CLARIFAI_API_KEY not found in .env")

# --------------------------------------------------
# 🔹 Convert image → Base64 Data URI
# --------------------------------------------------
def encode_image_to_data_uri(image_path: str) -> str:
    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type:
        mime_type = "image/jpeg"

    with open(image_path, "rb") as img:
        b64 = base64.b64encode(img.read()).decode("utf-8")

    return f"data:{mime_type};base64,{b64}"


# --------------------------------------------------
# 🔹 Generate Lightroom Parameters
# --------------------------------------------------
def generate_lightroom_params(feature_diff, input_img, ref_img, retries=3):

    input_uri = encode_image_to_data_uri(input_img)
    ref_uri = encode_image_to_data_uri(ref_img)

    prompt = f"""
You are a professional cinematic colorist.

Analyze Image 1 (input) and Image 2 (reference).
Match the color grading style of the reference image.

Base adjustments already computed:
{json.dumps(feature_diff)}

Return ONLY JSON with Lightroom parameters:

Allowed keys:
- Highlights2012 (-100 to 100)
- Shadows2012 (-100 to 100)
- Whites2012 (-100 to 100)
- Blacks2012 (-100 to 100)
- Texture (-100 to 100)
- Clarity2012 (-100 to 100)
- Dehaze (-100 to 100)
- HueAdjustmentRed, HueAdjustmentYellow, HueAdjustmentGreen, HueAdjustmentBlue (-100 to 100)
- SaturationAdjustmentRed, SaturationAdjustmentYellow, SaturationAdjustmentGreen (-100 to 100)
- LuminanceAdjustmentRed, LuminanceAdjustmentYellow, LuminanceAdjustmentBlue (-100 to 100)
- SplitToningShadowHue (0 to 360)
- SplitToningShadowSaturation (0 to 100)
- SplitToningHighlightHue (0 to 360)
- SplitToningHighlightSaturation (0 to 100)
- PostCropVignetteAmount (-100 to 100)
- GrainAmount (0 to 100)

STRICT RULES:
- JSON ONLY
- No explanation
- No markdown
"""

    client = OpenAI(
        base_url="https://api.clarifai.com/v2/ext/openai/v1",
        api_key=CLARIFAI_API_KEY
    )

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": input_uri}},
                {"type": "image_url", "image_url": {"url": ref_uri}},
            ]
        }
    ]

    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model="https://clarifai.com/openai/chat-completion/models/gpt-4o",
                messages=messages,
                max_tokens=1000,
                temperature=0.3
            )

            text = response.choices[0].message.content.strip()

            # Clean response if wrapped
            if text.startswith("```"):
                text = text.replace("```json", "").replace("```", "").strip()

            ai_params = json.loads(text)
            return ai_params

        except Exception as e:
            if attempt == retries - 1:
                raise Exception(f"❌ API Error: {str(e)}")
            time.sleep(2)


# --------------------------------------------------
# 🔹 Convert Params → Lightroom XMP File
# --------------------------------------------------
def generate_xmp(params, output_file="preset.xmp"):

    xmp = f'''<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/">
'''

    for key, value in params.items():
        xmp += f'   <crs:{key}>{value}</crs:{key}>\n'

    xmp += '''
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
'''

    with open(output_file, "w") as f:
        f.write(xmp)

    print(f"✅ XMP preset saved: {output_file}")


# --------------------------------------------------
# 🔥 MAIN EXECUTION
# --------------------------------------------------
if __name__ == "__main__":

    # Example base adjustments (your computed physics)
    feature_diff = {
        "Exposure2012": 0.4,
        "Contrast2012": 20,
        "Temperature": 5500,
        "Tint": 10,
        "Saturation": 5
    }

    input_image = "input.jpg"
    reference_image = "reference.jpg"

    print("🚀 Generating LUT...")

    ai_params = generate_lightroom_params(
        feature_diff,
        input_image,
        reference_image
    )

    # Merge base + AI
    final_params = {**feature_diff, **ai_params}

    print("\n🎯 FINAL PARAMETERS:")
    print(json.dumps(final_params, indent=2))

    generate_xmp(final_params)