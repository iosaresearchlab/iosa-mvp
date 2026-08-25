import base64
import concurrent.futures
import re
import uuid
import asyncio
import urllib.parse
from pathlib import Path
from playwright.sync_api import sync_playwright


def format_count(val) -> str:
    """Helper for formatting raw numbers into human-readable compact notation (e.g., 32593211 -> 32.6M, 79976 -> 80.0K)."""
    if val is None:
        return "N/A"
    if isinstance(val, (int, float)):
        num = float(val)
    elif isinstance(val, str):
        cleaned = val.replace(',', '').strip()
        try:
            num = float(cleaned)
        except ValueError:
            return val
    else:
        return str(val)

    if num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}K"
    return str(int(num) if num.is_integer() else num)


def resolve_level_and_style(level_name: str, vpi_score: str):
    """Calculates level name and dynamic color styling for all 10 distinct levels."""
    vpi_num = 0.0
    try:
        cleaned_vpi = str(vpi_score).replace('+', '').replace('x', '').replace(',', '').strip()
        vpi_num = float(cleaned_vpi)
    except (ValueError, TypeError):
        vpi_num = 1.0

    # Determine computed level based on VPI thresholds
    if vpi_num >= 100:
        computed_level_num = 10
        computed_name = "LVL 10 — APEX OUTLIER"
    elif vpi_num >= 50:
        computed_level_num = 9
        computed_name = "LVL 9 — HYPER OUTLIER"
    elif vpi_num >= 25:
        computed_level_num = 8
        computed_name = "LVL 8 — SUPER OUTLIER"
    elif vpi_num >= 15:
        computed_level_num = 7
        computed_name = "LVL 7 — EXTREME OUTLIER"
    elif vpi_num >= 10:
        computed_level_num = 6
        computed_name = "LVL 6 — MAJOR OUTLIER"
    elif vpi_num >= 5:
        computed_level_num = 5
        computed_name = "LVL 5 — OUTLIER"
    elif vpi_num >= 3:
        computed_level_num = 4
        computed_name = "LVL 4 — HIGH PERFORMANCE"
    elif vpi_num >= 2:
        computed_level_num = 3
        computed_name = "LVL 3 — ABOVE AVERAGE"
    elif vpi_num >= 1.5:
        computed_level_num = 2
        computed_name = "LVL 2 — MODERATE"
    else:
        computed_level_num = 1
        computed_name = "LVL 1 — BASELINE"

    if not level_name or level_name in ["LVL 5 — OUTLIER", "LVL 5 - OUTLIER"]:
        final_level_name = computed_name
    else:
        final_level_name = level_name
        match = re.search(r'LVL\s*(\d+)', level_name, re.IGNORECASE)
        if match:
            computed_level_num = int(match.group(1))

    # Dynamic color styling for all 10 levels (High contrast palette)
    if computed_level_num >= 10:
        # Mythic Gold
        badge_style = "bg-amber-950/60 text-amber-300 border-4 border-amber-300 shadow-[0_0_40px_rgba(255,215,0,0.6)]"
    elif computed_level_num == 9:
        # Electric Cyan
        badge_style = "bg-cyan-950/50 text-cyan-300 border-4 border-cyan-400 shadow-[0_0_35px_rgba(6,182,212,0.5)]"
    elif computed_level_num == 8:
        # Deep Violet
        badge_style = "bg-purple-950/70 text-purple-400 border-4 border-purple-700 shadow-[0_0_35px_rgba(124,58,237,0.5)]"
    elif computed_level_num == 7:
        # Light Pink
        badge_style = "bg-pink-950/50 text-pink-300 border-4 border-pink-400 shadow-[0_0_35px_rgba(244,114,182,0.4)]"
    elif computed_level_num == 6:
        # Crimson Red
        badge_style = "bg-red-950/50 text-red-400 border-4 border-red-500 shadow-[0_0_30px_rgba(239,68,68,0.4)]"
    elif computed_level_num == 5:
        # Vibrant Orange
        badge_style = "bg-orange-950/50 text-orange-400 border-4 border-orange-500 shadow-[0_0_30px_rgba(249,115,22,0.4)]"
    elif computed_level_num == 4:
        # Canary Yellow
        badge_style = "bg-yellow-950/50 text-yellow-400 border-4 border-yellow-500 shadow-[0_0_30px_rgba(234,179,8,0.4)]"
    elif computed_level_num == 3:
        # Neon Lime
        badge_style = "bg-lime-950/50 text-lime-400 border-4 border-lime-500 shadow-[0_0_30px_rgba(132,204,22,0.4)]"
    elif computed_level_num == 2:
        # Forest Green
        badge_style = "bg-green-950/80 text-green-500 border-4 border-green-700 shadow-[0_0_25px_rgba(21,128,61,0.4)]"
    else:
        # Slate Gray
        badge_style = "bg-slate-950/50 text-slate-400 border-4 border-slate-600 shadow-[0_0_25px_rgba(100,116,139,0.3)]"

    return final_level_name, badge_style


# ------------------------------------------------------------------------------
# DIGITAL PLAQUE / HORIZONTAL CERTIFICATE TEMPLATE (2700x1120)
# ------------------------------------------------------------------------------
TROPHY_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700;800&family=Inter:wght@400;600;900&family=Caveat:wght@600&display=swap" rel="stylesheet">
  <style>
    .font-mono-tech {{ font-family: 'JetBrains Mono', monospace; }}
    .font-sans-tech {{ font-family: 'Inter', sans-serif; }}
    .font-signature {{ font-family: 'Caveat', cursive; }}
    .bg-grid {{
      background-image: radial-gradient(rgba(0, 229, 255, 0.12) 1.5px, transparent 1.5px);
      background-size: 24px 24px;
    }}
    .line-clamp-3 {{
      display: -webkit-box;
      -webkit-line-clamp: 3;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }}
  </style>
</head>
<body class="bg-white text-gray-900 p-0 m-0 font-sans-tech w-[2700px] h-[1120px] flex items-center justify-center">

  <!-- Main Container -->
  <div class="w-[2700px] h-[1120px] bg-white overflow-hidden p-12 flex justify-between items-center relative gap-8">
    
    <!-- Left Panel -->
    <div class="w-[23%] bg-gray-50 text-gray-900 flex flex-col justify-between h-full py-10 px-8 relative z-10 border-2 border-gray-200 shadow-sm rounded-3xl">
      <div class="space-y-2 text-center">
        <div class="text-2xl font-mono-tech text-emerald-700 font-extrabold tracking-wider">METHODOLOGY</div>
        <div class="text-sm font-mono-tech text-gray-500 font-semibold">INSTITUTE FOR OPEN SOCIAL ANALYTICS</div>
      </div>

      <div class="space-y-6 font-mono-tech my-auto">
        <div class="bg-white p-5 rounded-2xl border border-gray-300 space-y-3 shadow-sm">
          <div class="text-emerald-800 font-extrabold text-sm tracking-wider">FORMULA</div>
          <div class="text-gray-900 font-mono text-lg bg-gray-50 px-4 py-3 rounded-xl border border-gray-200 text-center font-black">
            VPI = (E<sub>act</sub> / E<sub>base</sub>) &times; &gamma;
          </div>
        </div>

        <div class="bg-white p-5 rounded-2xl border border-gray-300 space-y-3 text-base">
          <div class="text-gray-700 text-sm font-black tracking-wider mb-2">BREAKDOWN DATA</div>
          <div class="flex justify-between font-semibold"><span class="text-gray-500">E<sub>act</sub>:</span> <span class="text-gray-900 font-bold">{e_act}</span></div>
          <div class="flex justify-between font-semibold"><span class="text-gray-500">E<sub>base</sub>:</span> <span class="text-gray-900 font-bold">{e_base}</span></div>
          <div class="flex justify-between font-semibold"><span class="text-gray-500">&gamma; (Gamma):</span> <span class="text-emerald-700 font-bold">{gamma}</span></div>
        </div>

        <p class="text-gray-600 text-sm leading-relaxed font-sans-tech bg-white p-4 rounded-2xl border border-gray-200 italic">
          Official accreditation for viral performance exceeding baseline standards.
        </p>

        <div class="pt-4 border-t border-gray-200 flex items-center justify-between">
          <div>
            <div class="text-gray-900 text-base font-mono-tech font-black">DR. M. A. PIERCE</div>
            <div class="text-gray-500 text-xs font-mono-tech uppercase font-bold">EXECUTIVE CHAIR</div>
          </div>
          <div class="font-signature text-emerald-700 text-4xl opacity-90 -rotate-3">M. A. Pierce</div>
        </div>
      </div>

      <div class="text-sm font-mono-tech text-gray-500 flex justify-between items-end border-t border-gray-200 pt-4">
        <div>HASH: <span class="text-gray-800 font-bold">{record_hash}</span></div>
        <span class="font-bold">IOSA-LAB</span>
      </div>
    </div>

    <!-- Center Panel -->
    <div class="w-[50%] bg-[#070A10] text-center flex flex-col justify-between h-full py-12 px-10 relative z-10 rounded-3xl border-4 border-emerald-500 shadow-2xl bg-grid">
      <div class="flex items-center justify-center gap-3">
        <div class="flex items-end gap-1">
          <svg class="h-16 w-12 text-[#00E5FF]" viewBox="0 0 18.5 32" fill="none">
            <path d="M1 26.5H6.5L14 8.5L17.5 14" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>
            <circle cx="14" cy="3" r="3" fill="#00E5FF"/>
          </svg>
          <span class="font-mono-tech font-black text-6xl tracking-tighter text-white leading-none">OSA</span>
        </div>
        <span class="text-lg font-mono-tech px-4 py-1.5 rounded bg-cyan-950 text-[#00E5FF] border border-cyan-500/30 font-extrabold tracking-wide">
          ACCREDITED
        </span>
      </div>

      <div class="space-y-4 my-auto">
        <div class="text-7xl font-mono-tech font-black text-[#00E5FF] tracking-wide uppercase drop-shadow-[0_0_30px_rgba(0,229,255,0.6)]">
          {user_handle}
        </div>
        <div class="text-9xl font-mono-tech font-black text-white tracking-tight leading-none drop-shadow-[0_0_40px_rgba(255,255,255,0.2)]">
          {vpi_score} <span class="text-[#00E5FF]">VPI</span>
        </div>
        
        <div class="pt-2 space-y-2">
          <div class="text-cyan-100/90 font-mono-tech text-2xl font-bold tracking-wider uppercase">
            Viral Performance Accreditation for
          </div>
          <div class="text-4xl text-white font-bold italic max-w-4xl mx-auto px-4 line-clamp-3 leading-tight">
            "{content_title}"
          </div>
        </div>
      </div>

      <div>
        <span class="inline-block text-3xl font-mono-tech px-12 py-4 rounded-2xl {level_badge_style} font-black tracking-widest">
          ACCREDITATION: {level_name}
        </span>
      </div>
    </div>

    <!-- Right Panel -->
    <div class="w-[23%] bg-gray-50 text-gray-900 flex flex-col justify-between items-center h-full py-10 px-8 relative z-10 border-2 border-gray-200 shadow-sm rounded-3xl text-center">
      <div class="space-y-2">
        <div class="text-2xl font-mono-tech text-emerald-700 font-extrabold tracking-wider">VERIFICATION</div>
        <div class="text-sm font-mono-tech text-gray-500 font-semibold">SCAN TO VERIFY</div>
      </div>

      <!-- Verification QR Code pointing directly to https://iosa-mvp-psi.vercel.app/claim/[record_id] -->
      <div class="bg-white p-6 rounded-2xl border-2 border-emerald-600 flex flex-col items-center gap-3 shadow-md my-auto">
        <img 
          src="https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={encoded_claim_url}&color=070A10&bgbw=0" 
          alt="Verification QR Code" 
          class="w-48 h-48"
        />
        <span class="text-sm font-mono-tech text-gray-800 font-black tracking-wider">{domain_display}</span>
      </div>

      <div class="text-sm font-mono-tech text-gray-500 font-bold border-t border-gray-200 pt-4 w-full">
        DATE: <span class="text-gray-800">{recorded_date}</span>
      </div>
    </div>

  </div>
</body>
</html>"""


# ------------------------------------------------------------------------------
# STATIC PHYSICAL ARTIFACT SAMPLE PREVIEW TEMPLATE (1600x900)
# ------------------------------------------------------------------------------
MUG_PREVIEW_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700;800&family=Inter:wght@400;600;900&display=swap" rel="stylesheet">
  <style>
    .font-mono-tech {{ font-family: 'JetBrains Mono', monospace; }}
    .font-sans-tech {{ font-family: 'Inter', sans-serif; }}
  </style>
</head>
<body class="bg-[#070A10] text-white p-0 m-0 font-sans-tech w-[1600px] h-[900px] flex items-center justify-center relative overflow-hidden">

  <!-- Inner container mirroring the exact dimensions of the image background -->
  <div class="relative w-[90%] h-[90%] flex flex-col items-center justify-center">
    
    {mug_sample_element}
    
    <!-- Modified Sample Banner overlay positioned inside the image bounds with a bottom gap -->
    <div class="absolute bottom-4 w-full bg-gray-500/[0.48] text-white font-sans-tech flex items-center justify-center py-5 z-20 text-center">
      <span class="text-4xl font-normal tracking-wide">
        This is a <span class="text-orange-600 font-bold uppercase">SAMPLE</span> and does not represent the customized product
      </span>
    </div>

  </div>

</body>
</html>"""


# ------------------------------------------------------------------------------
# PLAQUE RENDERING (SYNC & ASYNC)
# ------------------------------------------------------------------------------
def _render_png_sync(
    record_id: str,
    vpi_score: str,
    user_handle: str,
    content_title: str,
    e_act: str,
    e_base: str,
    gamma: str = "1.0x",
    recorded_date: str = "2026-08-20",
    output_dir: str = "renders",
    level_name: str = None,
    claim_base_url: str = "https://iosa-mvp-psi.vercel.app"
) -> str:
    out_path = Path(__file__).resolve().parent / output_dir
    out_path.mkdir(parents=True, exist_ok=True)

    final_output_path = out_path / f"trophy_{record_id}.png"
    record_hash = f"0x{uuid.uuid4().hex[:8].upper()}"

    if content_title and len(content_title) > 130:
        content_title = content_title[:127] + "..."

    formatted_e_act = format_count(e_act)
    formatted_e_base = format_count(e_base)

    final_level_name, level_badge_style = resolve_level_and_style(level_name, vpi_score)

    clean_base_url = claim_base_url.rstrip("/")
    domain_display = clean_base_url.replace("https://", "").replace("http://", "").upper()
    
    # Construct exact claim URL and URL-encode it safely for the QR generator API
    claim_url = f"{clean_base_url}/claim/{record_id}"
    encoded_claim_url = urllib.parse.quote(claim_url, safe='')

    html_content = TROPHY_HTML_TEMPLATE.format(
        record_id=record_id,
        vpi_score=vpi_score,
        user_handle=user_handle,
        content_title=content_title,
        e_act=formatted_e_act,
        e_base=formatted_e_base,
        gamma=gamma,
        level_name=final_level_name,
        level_badge_style=level_badge_style,
        recorded_date=recorded_date,
        record_hash=record_hash,
        encoded_claim_url=encoded_claim_url,
        domain_display=domain_display
    )

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            viewport={"width": 2700, "height": 1120},
            device_scale_factor=1
        )
        page.set_content(html_content, wait_until="networkidle")
        page.screenshot(
            path=str(final_output_path),
            type="png",
            omit_background=False
        )
        browser.close()

    return str(final_output_path)


async def generate_trophy_png(
    record_id: str,
    vpi_score: str = "+8.7x",
    user_handle: str = "@TEARDOWNMAYHEM",
    content_title: str = "Viral Content Title",
    e_act: str = "87.2K",
    e_base: str = "10.0K",
    gamma: str = "1.0x",
    recorded_date: str = "2026-08-20",
    output_dir: str = "renders",
    level_name: str = None,
    claim_base_url: str = "https://iosa-mvp-psi.vercel.app"
) -> str:
    return await asyncio.to_thread(
        _render_png_sync,
        record_id=record_id,
        vpi_score=vpi_score,
        user_handle=user_handle,
        content_title=content_title,
        e_act=e_act,
        e_base=e_base,
        gamma=gamma,
        recorded_date=recorded_date,
        output_dir=output_dir,
        level_name=level_name,
        claim_base_url=claim_base_url
    )


# ------------------------------------------------------------------------------
# MUG SAMPLE PREVIEW RENDERING (SYNC & ASYNC)
# ------------------------------------------------------------------------------
def _get_mug_sample_element() -> str:
    possible_paths = [
        (Path(__file__).resolve().parent / "mock_mug_sample.jpg", "image/jpeg"),
        (Path(__file__).resolve().parent / "mock_mug_sample.png", "image/png"),
        (Path.cwd() / "mock_mug_sample.jpg", "image/jpeg"),
        (Path.cwd() / "mock_mug_sample.png", "image/png"),
    ]
    for p, mime_type in possible_paths:
        if p.exists():
            img_bytes = p.read_bytes()
            encoded_img = base64.b64encode(img_bytes).decode('utf-8')
            return f'<img src="data:{mime_type};base64,{encoded_img}" class="w-full h-full object-contain rounded-2xl relative z-10" alt="Physical Artifact Sample" />'

    return '<div class="text-amber-400 text-2xl font-mono-tech border-2 border-amber-400 p-8 rounded-2xl">⚠️ mock_mug_sample.jpg not found in root directory!</div>'


def _render_mug_preview_sync(
    record_id: str,
    vpi_score: str,
    user_handle: str,
    output_dir: str
) -> str:
    out_path = Path(__file__).resolve().parent / output_dir
    out_path.mkdir(parents=True, exist_ok=True)

    final_output_path = out_path / f"mug_preview_{record_id}.png"
    mug_sample_element = _get_mug_sample_element()

    html_content = MUG_PREVIEW_HTML_TEMPLATE.format(
        mug_sample_element=mug_sample_element
    )

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            viewport={"width": 1600, "height": 900},
            device_scale_factor=1
        )
        page.set_content(html_content, wait_until="networkidle")
        page.screenshot(
            path=str(final_output_path),
            type="png",
            omit_background=False
        )
        browser.close()

    return str(final_output_path)


async def generate_mug_preview_png(
    record_id: str = "preview",
    vpi_score: str = "+8.7x",
    user_handle: str = "@TEARDOWNMAYHEM",
    output_dir: str = "renders"
) -> str:
    return await asyncio.to_thread(
        _render_mug_preview_sync,
        record_id,
        vpi_score,
        user_handle,
        output_dir
    )


# ------------------------------------------------------------------------------
# HELPER FOR BACKWARD COMPATIBILITY & ROUTER CALLS
# ------------------------------------------------------------------------------
def create_trophy_image(
    author: str,
    vpi_ratio: str,
    level_name: str = None,
    content_title: str = "",
    date_str: str = "2026-08-20",
    output_path: str = "renders/trophy.png",
    e_act: str = "87.2K",
    e_base: str = "10.0K",
    gamma: str = "1.0x",
    record_id: str = None,
    claim_base_url: str = "https://iosa-mvp-psi.vercel.app"
) -> str:
    out_file = Path(output_path)
    out_dir = out_file.parent if out_file.parent else Path("renders")

    if not record_id:
        extracted = out_file.stem.replace("trophy_", "").replace("preview_", "")
        record_id = extracted if extracted != "trophy" else "preview"

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            _render_png_sync,
            record_id=record_id,
            vpi_score=vpi_ratio,
            user_handle=author,
            content_title=content_title if content_title else "Viral Content Title",
            e_act=e_act,
            e_base=e_base,
            gamma=gamma,
            recorded_date=date_str,
            output_dir=str(out_dir),
            level_name=level_name,
            claim_base_url=claim_base_url
        )
        return future.result()