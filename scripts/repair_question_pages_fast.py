#!/usr/bin/env python3
"""
Fast Question-Page & Figure Repair Engine for Boards & Beyond Quizzes
=====================================================================
Repairs the Question Stem, Cropped Question Tables/Graphs (figure_image),
Options (A-G), and Peer Statistics (%) using the full-height top section
of the Explanation page (which is never truncated by the 910px viewport),
while 100% preserving existing 4K lecture slides (lecture_slide_image),
visual_metadata, and full verbatim explanation texts.
"""

import os
import sys
import re
import io
import json
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import pymupdf
import cv2
import numpy as np
from PIL import Image

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

def resolve_base_dir() -> Path:
    env_dir = os.environ.get("BNB_DATA_DIR")
    if env_dir and Path(env_dir).exists():
        return Path(env_dir)
    candidates = [
        Path("D:/Telegram_BnB_Videos"),
        Path.home() / "Telegram_BnB_Videos",
        Path.home() / "Desktop" / "Telegram_BnB_Videos",
        Path.cwd() / "Telegram_BnB_Videos",
    ]
    if sys.platform == "darwin" and Path("/Volumes").exists():
        for vol in Path("/Volumes").iterdir():
            if (vol / "Telegram_BnB_Videos").exists():
                return vol / "Telegram_BnB_Videos"
    for c in candidates:
        if c.exists():
            return c
    return Path(env_dir or "D:/Telegram_BnB_Videos")


BASE_DIR = resolve_base_dir()
QUIZZES_SOURCE_DIR = BASE_DIR / "PDFs_and_Quizzes" / "Quizzes"
OUTPUT_DIR = BASE_DIR / "quizzes_extracted"

_ocr_engine = None


def get_ocr():
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr_engine = RapidOCR()
    return _ocr_engine


def clean_spaces(text: str) -> str:
    if not text:
        return ""
    t = text.replace("（", "(").replace("）", ")").replace("【", "[").replace("】", "]")
    return re.sub(r"\s+", " ", t).strip()


def repair_single_quiz(pdf_path: Path, force: bool = False) -> tuple:
    rel_stem = pdf_path.relative_to(QUIZZES_SOURCE_DIR).with_suffix("")
    rel_stem_str = rel_stem.as_posix()
    target_folder = OUTPUT_DIR / rel_stem
    quiz_json_path = target_folder / "quiz.json"
    img_dir = target_folder / "images"

    if not quiz_json_path.exists():
        return str(rel_stem_str), "MISSING_JSON", 0

    try:
        data = json.loads(quiz_json_path.read_text(encoding="utf-8"))
    except Exception as e:
        return str(rel_stem_str), f"ERR_READ: {e}", 0

    questions = data.get("questions", [])
    if not questions:
        return str(rel_stem_str), "EMPTY", 0

    needs_repair = force or any(
        q.get("options", {}).get("A") in (None, "Option A")
        or q.get("question") in (None, "", "Clinical Board Review Question")
        or not q.get("peer_statistics")
        or not (q.get("explanation") or "").strip()
        or not re.match(r"^Answers?\s*[A-Na-n][^\n]{0,40}\(\s*correct", (q.get("explanation") or "").strip(), re.I)
        or "visual_metadata" not in q
        for q in questions
    )
    if not needs_repair:
        return str(rel_stem_str), "ALREADY_GOOD", len(questions)

    img_dir.mkdir(parents=True, exist_ok=True)
    engine = get_ocr()
    doc = pymupdf.open(str(pdf_path))
    num_q = min(len(questions), len(doc) // 2)

    for q_idx in range(num_q):
        q_obj = questions[q_idx]
        exp_page_idx = q_idx * 2 + 1
        exp_xref = doc[exp_page_idx].get_images()[0][0]
        im = Image.open(io.BytesIO(doc.extract_image(exp_xref)["image"]))
        arr = np.array(im)

        # 1. Locate all large white cards on the page (Options card + Score card + Explanation card)
        full_white = (
            (arr[:, :, 0] > 250)
            & (arr[:, :, 1] > 250)
            & (arr[:, :, 2] <= 255)
            & ((arr[:, :, 2].astype(int) - arr[:, :, 0].astype(int)) < 4)
        ).astype(np.uint8) * 255
        full_white[:120, :] = 0
        all_cnts, _ = cv2.findContours(full_white, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Explanation card is the bottom-most wide white card (w > 1000, h > 220)
        exp_cards = [
            cv2.boundingRect(c)
            for c in all_cnts
            if cv2.boundingRect(c)[2] > 1000 and cv2.boundingRect(c)[3] > 220 and cv2.boundingRect(c)[1] > 400
        ]
        exp_cards.sort(key=lambda r: r[1], reverse=True)
        exp_card = exp_cards[0] if exp_cards else None
        exp_card_top = exp_card[1] if exp_card else int(im.height * 0.55)

        # Options box segments live above exp_card_top (x around 214, w around 623)
        segs = [
            cv2.boundingRect(c)
            for c in all_cnts
            if 185 <= cv2.boundingRect(c)[0] <= 245
            and 540 <= cv2.boundingRect(c)[2] <= 720
            and cv2.boundingRect(c)[3] >= 30
            and cv2.boundingRect(c)[1] < exp_card_top - 40
        ]
        if segs:
            opt_top = max(140, min(s[1] for s in segs) - 120)
            opt_bot = min(exp_card_top - 10, max(s[1] + s[3] for s in segs) + 90)
        else:
            opt_top, opt_bot = 400, min(exp_card_top - 10, 1450)

        # 2. OCR the top question + options section at native 1:1 resolution
        top_crop = im.crop((180, 110, min(im.width, 1650), min(im.height, opt_bot + 30)))
        res, _ = engine(np.array(top_crop))
        boxes = []
        for b, t, s in (res or []):
            b_full = [[pt[0] + 180, pt[1] + 110] for pt in b]
            boxes.append((b_full, t.strip()))
        boxes.sort(key=lambda x: (x[0][0][1], x[0][0][0]))

        # Stop before 'Explanation' header or score banner if it appeared inside opt_bot
        exp_header_y = opt_bot + 50
        for b, t in boxes:
            tl = t.lower()
            if tl == "explanation" or "answered correctly" in tl or "time spent" in tl:
                exp_header_y = min(exp_header_y, b[0][1] - 10)

        # 3. Identify option markers (A)-(N) (supports up to 14 options like Cellular Adaptations Q1)
        markers = []
        marker_inline = {}
        for b, t in boxes:
            x0, y0 = b[0]
            if y0 >= exp_header_y:
                continue
            t_clean = (
                t.replace("（", "(")
                .replace("）", ")")
                .replace("【", "[")
                .replace("】", "]")
                .replace("○", "O")
            )
            if 200 <= x0 <= 335 and y0 >= opt_top - 35:
                m = re.match(r"^[O\(\)\[\]\s]*([A-Na-n])[\.\)\]\s]+(.*)$", t_clean)
                if not m:
                    m = re.match(r"^[O\(\)\[\]\s]*\(([A-Na-n])\)\s*(.*)$", t_clean)
                if m:
                    let = m.group(1).upper()
                    rem = m.group(2).strip()
                    if not any(let == x[1] for x in markers):
                        markers.append((y0, let, b[2][1]))
                        if rem:
                            marker_inline[let] = rem

        markers.sort(key=lambda x: x[0])
        real_opt_top = markers[0][0] - 25 if markers else opt_top

        # 4. Detect Question Figure / Table / Graph above real_opt_top
        # Unifies inner white plot cards AND outer axis labels/titles (e.g. Wiggers Diagram 'Pressure (mmHg)', '150..10', 'Time')
        fig_rect = None
        bg = np.array([246, 246, 255], dtype=np.int16)
        sub_h = max(140, int(real_opt_top - 8))
        sub_arr = arr[:sub_h, :]
        diff = np.abs(sub_arr.astype(np.int16) - bg).sum(axis=2)
        # diff > 12 captures both pure white plot cards ([255,255,255] -> diff=18) and dark ink/lines/axes
        tmask = (diff > 12).astype(np.uint8) * 255
        tmask[:125, :] = 0
        tmask[:, :315] = 0
        tmask[:, 1550:] = 0

        # Zero out full-width question text rows (which have dark text ink at x=205..310)
        left_text_ink = (diff[:, 205:310] > 35).sum(axis=1)
        for ry in range(len(left_text_ink)):
            if left_text_ink[ry] > 2:
                tmask[max(0, ry - 6) : min(tmask.shape[0], ry + 18), :] = 0

        # First check if there is a substantial figure core (width > 160, height > 75)
        kernel_core = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 18))
        closed_core = cv2.morphologyEx(tmask, cv2.MORPH_CLOSE, kernel_core)
        ccnts, _ = cv2.findContours(closed_core, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        core_blocks = [
            cv2.boundingRect(c)
            for c in ccnts
            if cv2.boundingRect(c)[2] > 160 and cv2.boundingRect(c)[3] > 70
        ]
        if core_blocks:
            cx0 = min(r[0] for r in core_blocks)
            cy0 = min(r[1] for r in core_blocks)
            cx1 = max(r[0] + r[2] for r in core_blocks)
            cy1 = max(r[1] + r[3] for r in core_blocks)
            # Expand to include any nearby outer axis labels/ticks/titles (within 95px horizontally, 55px vertically)
            # while excluding the 65x65 circular pencil button on the far right (x > cx1 + 25 and w < 85, h < 85)
            acnts, _ = cv2.findContours(tmask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            fx0, fy0, fx1, fy1 = cx0, cy0, cx1, cy1
            for c in acnts:
                rx, ry, rw, rh = cv2.boundingRect(c)
                if rw < 3 and rh < 3:
                    continue
                # Ignore isolated circular pencil button on the right of tables
                if rx > cx1 + 15 and rw < 90 and rh < 90:
                    continue
                if (
                    rx >= cx0 - 110
                    and (rx + rw) <= cx1 + 40
                    and ry >= cy0 - 45
                    and (ry + rh) <= min(sub_h, cy1 + 65)
                ):
                    fx0 = min(fx0, rx)
                    fy0 = min(fy0, ry)
                    fx1 = max(fx1, rx + rw)
                    fy1 = max(fy1, ry + rh)
            fig_rect = (fx0, fy0, fx1 - fx0, fy1 - fy0)

        if fig_rect:
            fx, fy, fw, fh = fig_rect
            pad = 12
            fcrop = im.crop(
                (
                    max(0, fx - pad),
                    max(0, fy - pad),
                    min(im.width, fx + fw + pad),
                    min(im.height, fy + fh + pad),
                )
            )
            fname = f"q_{q_idx + 1}_table_figure.png"
            fcrop.save(str(img_dir / fname))
            q_obj["has_figure"] = True
            q_obj["figure_image"] = f"/quizzes/{rel_stem_str}/images/{fname}"
        else:
            q_obj["has_figure"] = False
            q_obj["figure_image"] = None

        # 5. Stitch clinical vignette (excluding any OCR text inside fig_rect)
        vig_lines = []
        for b, t in boxes:
            bx0, by0 = b[0]
            bx1, by1 = b[2]
            if by0 >= real_opt_top:
                continue
            tl = t.lower()
            if any(
                k in tl
                for k in [
                    "boards&be",
                    "boards & be",
                    "item ",
                    "question id",
                    "mark",
                    "previous",
                    "next",
                    "calculator",
                    "lab values",
                    "total time taken",
                ]
            ):
                continue
            if fig_rect:
                fx, fy, fw, fh = fig_rect
                # Check if box center or bounds fall inside figure region
                bcx = (bx0 + bx1) / 2
                bcy = (by0 + by1) / 2
                if (
                    (fx - 30 <= bcx <= fx + fw + 45 and fy - 25 <= bcy <= fy + fh + 25)
                    or (bx0 >= fx - 30 and bx1 <= fx + fw + 45 and by0 >= fy - 25 and by1 <= fy + fh + 25)
                ):
                    continue
            vig_lines.append(clean_spaces(t))

        full_vig = clean_spaces(" ".join(vig_lines))
        if full_vig:
            q_obj["question"] = full_vig

        # 6. Extract Options and Peer Statistics
        opts = {}
        pstats = {}
        for i, (my, mlet, my1) in enumerate(markers):
            ty = my - 22 if i == 0 else (markers[i - 1][0] + my) / 2
            by = (
                (my + markers[i + 1][0]) / 2
                if i < len(markers) - 1
                else min(exp_header_y, my + 75)
            )
            words = []
            if mlet in marker_inline:
                words.append(marker_inline[mlet])
            for b, t in boxes:
                bx0, by0 = b[0]
                if ty <= by0 < by and by0 < exp_header_y:
                    m_pct = re.search(r"(\d{1,3}(?:\.\d{1,2})?)\s*%", t)
                    if m_pct and bx0 > 680:
                        pstats[mlet] = float(m_pct.group(1))
                    elif 285 <= bx0 <= 740:
                        t_clean = clean_spaces(t)
                        if not re.match(r"^[O\(\)\[\]\s]*[A-Na-n][\.\)\]]", t_clean):
                            words.append(t_clean)
            raw_opt = clean_spaces(" ".join(words)) or mlet
            m_tail_pct = re.search(r"\s+(\d{1,3}(?:\.\d{1,2})?)\s*%\s*$", raw_opt)
            if m_tail_pct:
                pstats[mlet] = float(m_tail_pct.group(1))
                raw_opt = raw_opt[: m_tail_pct.start()].strip() or mlet
            opts[mlet] = raw_opt

        if len(opts) >= 2:
            q_obj["options"] = opts
        if pstats:
            q_obj["peer_statistics"] = pstats

        # 7. Audit & Repair Explanation Visual AND Missing/Truncated Explanation Text via OpenCV Card Geometry
        if exp_card:
            cx, cy, cw, ch = exp_card
            vis_top = cy + 65
            scan_start = min(cy + 68, cy + ch - 25)
            card_sub = arr[scan_start : cy + ch - 15, :]
            is_dark_text = (
                (card_sub[:, 230:345, 0] < 165)
                & (card_sub[:, 230:345, 1] < 165)
                & ((card_sub[:, 230:345, 2].astype(int) - card_sub[:, 230:345, 0].astype(int)) < 35)
            )
            dark_left = is_dark_text.sum(axis=1)
            para_rows = np.where(dark_left > 4)[0]
            text_start_y = (
                scan_start + int(para_rows[0])
                if len(para_rows) > 0
                else cy + 75
            )
            vis_bot = text_start_y - 12

            # 7A. Extract/Repair Explanation Visual if a visual gap exists between vis_top and vis_bot
            if (vis_bot - vis_top) > 95:
                ecrop = im.crop((220, vis_top, cx + cw - 20, vis_bot))
                ecarr = np.array(ecrop)
                ediff = np.abs(ecarr.astype(np.int16) - 255).sum(axis=2)
                ys, xs = np.where(ediff > 18)
                if len(xs) > 150:
                    pad = 12
                    x0 = max(0, int(xs.min()) - pad)
                    y0 = max(0, int(ys.min()) - pad)
                    x1 = min(ecrop.width, int(xs.max()) + pad)
                    y1 = min(ecrop.height, int(ys.max()) + pad)
                    clean_ecrop = ecrop.crop((x0, y0, x1, y1))

                    hsv = cv2.cvtColor(np.array(clean_ecrop), cv2.COLOR_RGB2HSV)
                    bmask = cv2.inRange(hsv, np.array([95, 100, 100]), np.array([125, 255, 255]))
                    max_bspan = int(np.max((bmask > 0).sum(axis=1))) if bmask.size > 0 else 0
                    is_true_horiz_slide = (max_bspan >= 660 and clean_ecrop.width >= 680)

                    out_sname = f"q_{q_idx + 1}_lecture_slide.png"
                    out_spath = img_dir / out_sname
                    s_rel = f"/quizzes/{rel_stem_str}/images/{out_sname}"

                    if not is_true_horiz_slide or not q_obj.get("lecture_slide_image") or not out_spath.exists():
                        clean_ecrop.save(str(out_spath))
                        q_obj["lecture_slide_image"] = s_rel
                        q_obj["visual_metadata"] = {
                            "has_visual": True,
                            "image_rel": s_rel,
                            "type": "lecture_slide_cropped" if is_true_horiz_slide else "regular_medical_figure",
                            "matched_deck": None,
                            "matched_slide": None,
                            "confidence_score": 0,
                        }

            # 7B. Repair Missing / Empty / Top-Truncated Explanation Text
            # Every valid explanation begins with 'Answer X (correct answer)' in its first 70 chars
            cur_exp = (q_obj.get("explanation") or "").strip()
            starts_with_correct = bool(
                re.match(r"^Answers?\s*[A-Na-n][^\n]{0,40}\(\s*correct", cur_exp, re.I)
            )
            if not cur_exp or not starts_with_correct or "IncorrectAnswer" in cur_exp or len(cur_exp) < 50:
                exp_text_crop = im.crop(
                    (210, max(cy + 60, text_start_y - 15), cx + cw - 15, min(im.height - 60, cy + ch - 10))
                )
                eres, _ = engine(np.array(exp_text_crop))
                eboxes = sorted(eres or [], key=lambda b: (b[0][0][1], b[0][0][0]))
                blocks = []
                curr_b = []
                for b, txt, sc in eboxes:
                    ct = clean_spaces(txt)
                    if not ct:
                        continue
                    ctl = ct.lower()
                    if any(
                        k in ctl
                        for k in [
                            "total time taken",
                            "boards&beyond",
                            "boards & beyond",
                            "feedback",
                            "suspend",
                            "end quiz",
                            "mcgraw",
                            "statistics",
                        ]
                    ):
                        continue
                    m_ans = re.match(
                        r"^Answers?\s*([A-Na-n])\b[^\n]*?\((correct|incorrect)",
                        ct,
                        re.I,
                    )
                    if m_ans:
                        if m_ans.group(2).lower().startswith("correct"):
                            q_obj["correct_answer"] = m_ans.group(1).upper()
                        if curr_b:
                            blocks.append(" ".join(curr_b))
                            curr_b = []
                        curr_b.append(ct)
                    elif re.match(r"^Answers?\s*[A-Na-n](?:\s*(?:,|and|&)\s*[A-Na-n])*\s*\(", ct, re.I):
                        if curr_b:
                            blocks.append(" ".join(curr_b))
                            curr_b = []
                        curr_b.append(ct)
                    else:
                        curr_b.append(ct)
                if curr_b:
                    blocks.append(" ".join(curr_b))
                if blocks:
                    q_obj["explanation"] = "\n\n".join(blocks)
            else:
                m_corr = re.search(r"Answer\s*([A-Na-n])\s*\(\s*correct", cur_exp, re.I)
                if m_corr:
                    q_obj["correct_answer"] = m_corr.group(1).upper()

    quiz_json_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return str(rel_stem_str), "REPAIRED", num_q


def _worker_task(args):
    pdf_path, force_flag = args
    t0 = time.time()
    try:
        rel, status, nq = repair_single_quiz(pdf_path, force=force_flag)
        return rel, status, nq, time.time() - t0
    except Exception as e:
        return str(pdf_path.name), f"ERROR: {e}", 0, time.time() - t0


if __name__ == "__main__":
    force_flag = "--force" in sys.argv
    workers = 3
    targets = []
    for a in sys.argv[1:]:
        if a.startswith("--workers="):
            workers = int(a.split("=")[1])
        elif not a.startswith("--") and Path(a).exists():
            p = Path(a)
            if p.is_dir():
                targets.extend(sorted(list(p.rglob("*.pdf"))))
            else:
                targets.append(p)

    if targets:
        for t in targets:
            t0 = time.time()
            rel, status, nq = repair_single_quiz(t, force=True)
            print(f"[{status}] {rel} ({nq} Qs) in {time.time() - t0:.1f}s", flush=True)
    else:
        all_pdfs = sorted(list(QUIZZES_SOURCE_DIR.rglob("*.pdf")))
        print(f"Scanning {len(all_pdfs)} quiz PDFs for Question-Page repair (workers={workers})...", flush=True)
        done = 0
        repaired = 0
        already = 0
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(_worker_task, (pdf, force_flag)): pdf for pdf in all_pdfs}
            for fut in as_completed(futs):
                done += 1
                rel, status, nq, dt = fut.result()
                if status == "REPAIRED":
                    repaired += 1
                    print(f"[{done}/{len(all_pdfs)}] ✅ REPAIRED: {rel} ({nq} Qs) in {dt:.1f}s (repaired={repaired}, good={already})", flush=True)
                elif status == "ALREADY_GOOD":
                    already += 1
        print(f"Complete! Repaired {repaired} quizzes (Already good: {already}).", flush=True)

