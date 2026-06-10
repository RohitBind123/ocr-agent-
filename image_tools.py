"""Image manipulation tools the ReAct agent can call to decipher illegible handwriting."""
import io
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
from pdf2image import convert_from_path

# Form-layout regions as (left, top, right, bottom) fractions of the full page.
# Derived from the RGHS OPD form structure.
REGIONS = {
    'full':           (0.00, 0.00, 1.00, 1.00),
    'top_band':       (0.00, 0.18, 1.00, 0.42),   # free space above "Chief Complaints" (diagnosis often here)
    'complaint_zone': (0.00, 0.26, 0.62, 0.46),   # Chief Complaints handwriting (left, avoids vitals box)
    'diagnosis_zone': (0.00, 0.18, 1.00, 0.64),   # top band + Systemic Exam & Provisional Diagnosis
    'right_margin':   (0.55, 0.18, 1.00, 0.75),   # doctor's notes often continue on the right
}


def render_page(pdf_path: str, dpi: int = 300) -> Image.Image:
    pages = convert_from_path(pdf_path, dpi=dpi)
    return pages[0].convert('RGB')


def crop_region(img: Image.Image, region: str) -> Image.Image:
    l, t, r, b = REGIONS.get(region, REGIONS['full'])
    w, h = img.size
    return img.crop((int(l * w), int(t * h), int(r * w), int(b * h)))


def upscale(img: Image.Image, factor: float = 2.0) -> Image.Image:
    w, h = img.size
    return img.resize((int(w * factor), int(h * factor)), Image.LANCZOS)


def enhance(img: Image.Image, method: str) -> Image.Image:
    """method: contrast | sharpen | grayscale | threshold | denoise"""
    if method == 'contrast':
        g = ImageOps.grayscale(img)
        g = ImageOps.autocontrast(g, cutoff=2)
        return ImageEnhance.Contrast(g).enhance(1.8)
    if method == 'sharpen':
        return img.filter(ImageFilter.UnsharpMask(radius=2, percent=160, threshold=2))
    if method == 'grayscale':
        return ImageOps.grayscale(img)
    if method == 'threshold':
        g = ImageOps.grayscale(img)
        g = ImageOps.autocontrast(g, cutoff=1)
        # soft threshold to lift blue ink from white
        return g.point(lambda p: 0 if p < 130 else 255)
    if method == 'denoise':
        return img.filter(ImageFilter.MedianFilter(size=3))
    return img


def isolate_blue_ink(img: Image.Image) -> Image.Image:
    """Most handwriting is blue ballpoint — isolate it for clarity."""
    rgb = img.convert('RGB')
    px = rgb.load()
    w, h = rgb.size
    out = Image.new('L', (w, h), 255)
    op = out.load()
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            # blue ink: blue channel notably higher than red, and not too bright
            if b > r + 18 and b > 60 and r < 180:
                op[x, y] = 0
    return out


def to_jpeg_b64(img: Image.Image, quality: int = 92) -> str:
    import base64
    buf = io.BytesIO()
    img.convert('RGB').save(buf, format='JPEG', quality=quality)
    return base64.b64encode(buf.getvalue()).decode()


def apply_action(base_img: Image.Image, action: dict) -> tuple[Image.Image, str]:
    """Execute a ReAct action, return (new_image, observation_text)."""
    act = action.get('action')
    if act == 'zoom':
        region = action.get('region', 'full')
        img = upscale(crop_region(base_img, region), 2.0)
        return img, f"Zoomed into '{region}' at 2x."
    if act == 'enhance':
        method = action.get('method', 'contrast')
        region = action.get('region', 'diagnosis_zone')
        img = upscale(crop_region(base_img, region), 2.0)
        img = enhance(img, method)
        return img, f"Cropped '{region}', applied '{method}', upscaled 2x."
    if act == 'isolate_ink':
        region = action.get('region', 'diagnosis_zone')
        img = upscale(crop_region(base_img, region), 2.0)
        img = isolate_blue_ink(img)
        return img, f"Isolated blue ink in '{region}', upscaled 2x."
    return base_img, "No-op."
