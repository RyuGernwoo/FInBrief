"""compose_card 렌더러 (Pillow, dict 입력). 프로덕션은 HTML/CSS+Playwright 로 교체 예정.
   폰트: FINBRIEF_FONT 우선, 없으면 OS별 한글 폰트 자동탐색, 최후엔 기본폰트."""
from __future__ import annotations

import os
from PIL import Image, ImageDraw, ImageFont

CANVAS = 1080
BG, INK, GRAY, MUTED, EDGE = (238, 241, 245), (26, 26, 26), (70, 78, 90), (150, 158, 168), (200, 205, 212)
THEMES = {"MARKET": (31, 111, 235), "GLOBAL": (74, 109, 167), "DOMESTIC": (31, 157, 85),
          "CRYPTO": (217, 138, 0), "FX": (14, 155, 142)}
DEFAULT_ACCENT = (74, 109, 167)
_FONT_CANDIDATES = [
    os.environ.get("FINBRIEF_FONT"),
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "C:/Windows/Fonts/malgun.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
]
_fc: dict[int, ImageFont.FreeTypeFont] = {}


def _f(sz: int):
    if sz in _fc:
        return _fc[sz]
    for c in _FONT_CANDIDATES:
        if c and os.path.exists(c):
            try:
                _fc[sz] = ImageFont.truetype(c, sz)
                return _fc[sz]
            except Exception:
                continue
    _fc[sz] = ImageFont.load_default()
    return _fc[sz]


def _wrap(d, text, font, maxw):
    lines, cur = [], ""
    for w in str(text).split(" "):
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font) <= maxw:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def render_card(content: dict, out_path: str) -> str:
    accent = THEMES.get(str(content.get("category", "")).upper(), DEFAULT_ACCENT)
    img = Image.new("RGB", (CANVAS, CANVAS), BG)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([16, 16, CANVAS - 16, CANVAS - 16], radius=10, outline=accent, width=3)
    padx = 60
    bx, by, bs = padx, 52, 96
    d.rounded_rectangle([bx, by, bx + bs, by + bs], radius=6, outline=INK, width=3)
    d.text((bx + bs / 2, by + 22), str(content.get("category", "")).upper()[:8], font=_f(20), fill=accent, anchor="mm")
    d.line([bx + 14, by + 40, bx + bs - 14, by + 40], fill=(210, 214, 220), width=1)
    d.text((bx + bs / 2, by + 68), str(content.get("index_no", "00")), font=_f(52), fill=INK, anchor="mm")
    tx = bx + bs + 26
    d.text((tx, by + 8), content.get("subtitle", ""), font=_f(30), fill=GRAY, anchor="lm")
    d.text((tx, by + 66), content.get("headline", ""), font=_f(60), fill=INK, anchor="lm", stroke_width=2, stroke_fill=INK)
    ix0, iy0, ix1, iy1 = padx, 200, CANVAS - padx, 640
    ip = content.get("image_url")
    if ip and os.path.exists(ip):
        ill = Image.open(ip).convert("RGB")
        s = max((ix1 - ix0) / ill.width, (iy1 - iy0) / ill.height)
        ill = ill.resize((int(ill.width * s), int(ill.height * s)))
        l, t = (ill.width - (ix1 - ix0)) // 2, (ill.height - (iy1 - iy0)) // 2
        img.paste(ill.crop((l, t, l + ix1 - ix0, t + iy1 - iy0)), (ix0, iy0))
    else:
        panel = Image.new("RGB", (ix1 - ix0, iy1 - iy0))
        pd = ImageDraw.Draw(panel)
        for y in range(iy1 - iy0):
            k = y / (iy1 - iy0)
            pd.line([(0, y), (ix1 - ix0, y)], fill=(int(216 - 38 * k), int(228 - 30 * k), int(244 - 12 * k)))
        img.paste(panel, (ix0, iy0))
        d.text(((ix0 + ix1) / 2, (iy0 + iy1) / 2), "AI 일러스트 자리 (Nano Banana)", font=_f(20), fill=(120, 130, 145), anchor="mm")
    d.rounded_rectangle([ix0, iy0, ix1, iy1], radius=8, outline=EDGE, width=2)
    maxw = CANVAS - 2 * padx
    y = 686
    for ln in _wrap(d, content.get("lead", ""), _f(33), maxw):
        d.text((CANVAS / 2, y), ln, font=_f(33), fill=INK, anchor="mm", stroke_width=1, stroke_fill=INK)
        y += 46
    y += 14
    for ln in _wrap(d, content.get("body", ""), _f(30), maxw):
        d.text((CANVAS / 2, y), ln, font=_f(30), fill=GRAY, anchor="mm")
        y += 44
    d.text((CANVAS / 2, CANVAS - 92), content.get("source", ""), font=_f(20), fill=MUTED, anchor="mm")
    d.text((CANVAS / 2, CANVAS - 58), content.get("disclaimer", ""), font=_f(19), fill=MUTED, anchor="mm")
    img.save(out_path)
    return out_path
