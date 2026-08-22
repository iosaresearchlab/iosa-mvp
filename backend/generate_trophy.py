import base64
import concurrent.futures
import uuid
import asyncio
from pathlib import Path
from playwright.sync_api import sync_playwright

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
        <span class="inline-block text-3xl font-mono-tech px-12 py-4 rounded-2xl bg-amber-500/20 text-amber-300 border-4 border-amber-400 font-black tracking-widest shadow-[0_0_35px_rgba(245,158,11,0.4)]">
          ACCREDITATION: LVL 5 — OUTLIER
        </span>
      </div>
    </div>

    <!-- Right Panel -->
    <div class="w-[23%] bg-gray-50 text-gray-900 flex flex-col justify-between items-center h-full py-10 px-8 relative z-10 border-2 border-gray-200 shadow-sm rounded-3xl text-center">
      <div class="space-y-2">
        <div class="text-2xl font-mono-tech text-emerald-700 font-extrabold tracking-wider">VERIFICATION</div>
        <div class="text-sm font-mono-tech text-gray-500 font-semibold">SCAN TO VERIFY</div>
      </div>

      <div class="bg-white p-6 rounded-2xl border-2 border-emerald-600 flex flex-col items-center gap-3 shadow-md my-auto">
        <img 
          src="https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=https://iosa-lab.org/claim/{record_id}&color=070A10&bgbw=0" 
          alt="Verification QR Code" 
          class="w-48 h-48"
        />
        <span class="text-sm font-mono-tech text-gray-800 font-black tracking-wider">IOSA-LAB.ORG</span>
      </div>

      <div class="text-sm font-mono-tech text-gray-500 font-bold border-t border-gray-200 pt-4 w-full">
        DATE: <span class="text-gray-800">{recorded_date}</span>
      </div>
    </div>

  </div>
</body>
</html>"""


# ------------------------------------------------------------------------------
# STATIC PHYSICAL ARTIFACT SAMPLE PREVIEW TEMPLATE (1200x1200)
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
<body class="bg-[#070A10] text-white p-0 m-0 font-sans-tech w-[1200px] h-[1200px] flex items-center justify-center relative overflow-hidden">

  <div class="relative w-[1200px] h-[1200px] flex flex-col items-center justify-center p-8 bg-[#070A10]">
    
    <div class="relative w-full h-full flex items-center justify-center">
      {mug_sample_element}
      
      <div class="absolute top-8 bg-amber-500 text-black font-mono-tech font-black text-2xl px-8 py-3 rounded-2xl shadow-2xl tracking-widest uppercase border-4 border-black/20 z-20">
        SAMPLE ONLY
      </div>
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
    gamma: str,
    recorded_date: str,
    output_dir: str
) -> str:
    out_path = Path(__file__).resolve().parent / output_dir
    out_path.mkdir(parents=True, exist_ok=True)

    final_output_path = out_path / f"trophy_{record_id}.png"
    record_hash = f"0x{uuid.uuid4().hex[:8].upper()}"

    if content_title and len(content_title) > 130:
        content_title = content_title[:127] + "..."

    html_content = TROPHY_HTML_TEMPLATE.format(
        record_id=record_id,
        vpi_score=vpi_score,
        user_handle=user_handle,
        content_title=content_title,
        e_act=e_act,
        e_base=e_base,
        gamma=gamma,
        recorded_date=recorded_date,
        record_hash=record_hash
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
    output_dir: str = "renders"
) -> str:
    return await asyncio.to_thread(
        _render_png_sync,
        record_id,
        vpi_score,
        user_handle,
        content_title,
        e_act,
        e_base,
        gamma,
        recorded_date,
        output_dir
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
            return f'<img src="data:{mime_type};base64,{encoded_img}" class="max-h-[1050px] max-w-[1050px] w-auto h-auto object-contain rounded-2xl shadow-2xl relative z-10 mx-auto my-auto" alt="Physical Artifact Sample" />'

    return '<div class="text-amber-400 text-xl font-mono-tech border-2 border-amber-400 p-8 rounded-2xl">⚠️ mock_mug_sample.jpg not found in root directory!</div>'


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
            viewport={"width": 1200, "height": 1200},
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
# LEGACY HELPER FOR BACKWARD COMPATIBILITY
# ------------------------------------------------------------------------------
def create_trophy_image(
    author: str,
    vpi_ratio: str,
    level_name: str = "LVL 5 — OUTLIER",
    content_title: str = "",
    date_str: str = "2026-08-20",
    output_path: str = "renders/trophy.png"
) -> str:
    out_file = Path(output_path)
    out_dir = out_file.parent if out_file.parent else Path("renders")
    record_id = out_file.stem.replace("trophy_", "").replace("preview_", "")

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            _render_png_sync,
            record_id,
            vpi_ratio,
            author,
            content_title if content_title else "Viral Content Title",
            "87.2K",
            "10.0K",
            "1.0x",
            date_str,
            str(out_dir)
        )
        return future.result()