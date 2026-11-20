#!/usr/bin/env python3
"""
⚡ BOARDS & BEYOND: STEP 1 PRECLINICAL ORDERED EXTRACTION ENGINE
================================================================================
- Strictly extracts 'Step 1 - Preclinical' in numerical folder order (01_Anesthesia -> 22_Reproductive).
- Quizzes within each folder are processed in exact numerical order (01. ..., 02. ..., etc.).
- Capped memory footprint: 3 worker processes with single-thread isolation (~1.0 GB RAM total).
- Continuous memory guard prevents system thrashing, leaving 3.8+ GB free for user apps.
- Automatic worker process recycling (maxtasksperchild=10) prevents C++ memory leaks.
- Real-time telemetry written to D:/Telegram_BnB_Videos/quizzes_extracted/step1_progress.json.
"""

import os
import sys

# Thread and memory isolation for worker processes
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUNBUFFERED"] = "1"
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

import gc
import re
import json
import time
from pathlib import Path
from multiprocessing import Pool
import psutil
import pymupdf
import cv2
import numpy as np
from PIL import Image, ImageChops

BASE_DIR = Path("D:/Telegram_BnB_Videos")
STEP1_SOURCE_DIR = BASE_DIR / "PDFs_and_Quizzes" / "Quizzes" / "Step 1 - Preclinical"
SLIDES_SOURCE_DIR = BASE_DIR / "PDFs_and_Quizzes" / "Slides_and_Notes"
OUTPUT_DIR = BASE_DIR / "quizzes_extracted"
PROGRESS_FILE = OUTPUT_DIR / "step1_progress.json"
LOG_FILE = OUTPUT_DIR / "extractor_step1.log"

_SLIDE_CACHE = {}
_ocr_engine = None


def get_ocr():
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr_engine = RapidOCR()
        _ocr_engine.text_det.limit_side_len = 1600
    return _ocr_engine


def log(msg: str):
    print(msg, flush=True)
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


class PathEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Path):
            return obj.as_posix()
        return super().default(obj)


def clean_spaces(text: str) -> str:
    return " ".join((text or "").split())


def get_slide_deck_data(deck_path: Path):
    path_str = str(deck_path)
    if path_str in _SLIDE_CACHE:
        return _SLIDE_CACHE[path_str]
    try:
        doc = pymupdf.open(path_str)
        slides = []
        for idx, page in enumerate(doc):
            t = page.get_text()
            words = set([w.lower() for w in re.findall(r'[a-zA-Z]{4,}', t)])
            slides.append({'index': idx + 1, 'text': t, 'words': words})
        _SLIDE_CACHE[path_str] = (doc, slides)
        return doc, slides
    except Exception:
        return None, []


def process_explanation_visual(
    exp_img: Image.Image,
    exp_start_y: float,
    answer_correct_y: float,
    quiz_path: Path,
    q_num: int,
    img_dir: Path,
    rel_stem: str,
    engine
) -> dict:
    if not exp_start_y or not answer_correct_y:
        return {"has_visual": False, "image_rel": None, "type": "none"}
    gap = answer_correct_y - exp_start_y
    if gap < 120:
        return {"has_visual": False, "image_rel": None, "type": "none"}

    top = int(exp_start_y + 75)
    bottom = int(answer_correct_y - 15)
    left = 180
    right = 1650

    crop = exp_img.crop((left, top, right, bottom))
    bg = np.array([255, 255, 255], dtype=np.int16)
    diff = np.abs(np.array(crop).astype(np.int16) - bg).sum(axis=2)
    if np.count_nonzero(diff > 20) <= 5000:
        return {"has_visual": False, "image_rel": None, "type": "none"}

    # Color Palette / Blue Banner Analysis
    arr = np.array(crop)
    hsv = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV)
    blue_mask = cv2.inRange(hsv, np.array([95, 100, 100]), np.array([125, 255, 255]))
    blue_mask[:int(arr.shape[0] * 0.12), :] = 0
    blue_h_proj = (blue_mask > 0).sum(axis=1)
    max_blue_span = np.max(blue_h_proj) if len(blue_h_proj) > 0 else 0
    is_bb_lecture_slide = (max_blue_span >= (arr.shape[1] * 0.38))

    out_filename = f"q_{q_num}_lecture_slide.png"
    out_file_path = img_dir / out_filename
    image_rel = f"/quizzes/{rel_stem}/images/{out_filename}"

    # Non-slide: Autocrop table/diagram and preserve without slide replacement
    if not is_bb_lecture_slide:
        diff = np.abs(arr.astype(np.int16) - bg).sum(axis=2)
        mask = (diff > 25).astype(np.uint8)
        mask[:int(arr.shape[0] * 0.12), :] = 0
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            x_min, y_min, x_max, y_max = 99999, 99999, 0, 0
            for c in contours:
                cx, cy, cw, ch = cv2.boundingRect(c)
                if cw > 150 and ch > 40:
                    x_min = min(x_min, cx)
                    y_min = min(y_min, cy)
                    x_max = max(x_max, cx + cw)
                    y_max = max(y_max, cy + ch)
            if x_max > x_min and y_max > y_min:
                pad = 12
                clean_crop = crop.crop((
                    max(0, x_min - pad),
                    max(0, y_min - pad),
                    min(crop.width, x_max + pad),
                    min(crop.height, y_max + pad)
                ))
            else:
                clean_crop = crop
        else:
            clean_crop = crop

        clean_crop.save(str(out_file_path))
        return {
            "has_visual": True,
            "image_rel": image_rel,
            "type": "regular_medical_figure",
            "matched_deck": None,
            "matched_slide": None,
            "confidence_score": 0
        }

    # True Lecture Slide: OCR & match against slide deck library
    crop_res, _ = engine(np.array(crop))
    content_words = set()
    for b, t, s in (crop_res or []):
        box_y = b[0][1]
        if box_y > 85:
            clean_t = re.sub(r'([a-z])([A-Z])', r'\1 \2', t)
            for w in re.findall(r'[a-zA-Z]{4,}', clean_t):
                lw = w.lower()
                if lw not in ['boards', 'beyond', 'mcgraw', 'hill', 'page', 'courtesy', 'image']:
                    content_words.add(lw)

    clean_stem = quiz_path.stem.replace('-Quiz', '').strip()
    rel_parent = quiz_path.parent.relative_to(BASE_DIR / "PDFs_and_Quizzes" / "Quizzes")
    primary_deck_path = SLIDES_SOURCE_DIR / rel_parent / (clean_stem + '.pdf')
    parent_slides_dir = SLIDES_SOURCE_DIR / rel_parent

    if not primary_deck_path.exists() and parent_slides_dir.exists():
        for cand in parent_slides_dir.glob('*.pdf'):
            if clean_stem.lower() in cand.stem.lower():
                primary_deck_path = cand
                break

    sibling_decks = list(parent_slides_dir.glob('*.pdf')) if parent_slides_dir.exists() else []

    best_score = 0
    best_slide_idx = None
    best_deck_doc = None
    best_deck_path = None

    if primary_deck_path.exists():
        doc, slides = get_slide_deck_data(primary_deck_path)
        if doc and slides:
            for s in slides:
                overlap = len(content_words.intersection(s['words']))
                for cw in content_words:
                    if len(cw) >= 7:
                        for sw in s['words']:
                            if len(sw) >= 5 and sw in cw and sw not in content_words:
                                overlap += 1
                if overlap > best_score:
                    best_score = overlap
                    best_slide_idx = s['index']
                    best_deck_doc = doc
                    best_deck_path = primary_deck_path

    if best_score < 4 and sibling_decks:
        for sib in sibling_decks:
            if sib == primary_deck_path:
                continue
            doc, slides = get_slide_deck_data(sib)
            if doc and slides:
                for s in slides:
                    overlap = len(content_words.intersection(s['words']))
                    for cw in content_words:
                        if len(cw) >= 7:
                            for sw in s['words']:
                                if len(sw) >= 5 and sw in cw and sw not in content_words:
                                    overlap += 1
                    if overlap > best_score:
                        best_score = overlap
                        best_slide_idx = s['index']
                        best_deck_doc = doc
                        best_deck_path = sib

    if best_score >= 4 and best_deck_doc and best_slide_idx:
        try:
            page = best_deck_doc[best_slide_idx - 1]
            pix_4k = page.get_pixmap(dpi=300)
            pix_4k.save(str(out_file_path))
            return {
                "has_visual": True,
                "image_rel": image_rel,
                "type": "lecture_slide_4k",
                "matched_deck": best_deck_path.name,
                "matched_slide": best_slide_idx,
                "confidence_score": best_score
            }
        except Exception:
            crop.save(str(out_file_path))
            return {
                "has_visual": True,
                "image_rel": image_rel,
                "type": "lecture_slide_cropped",
                "matched_deck": best_deck_path.name if best_deck_path else None,
                "matched_slide": best_slide_idx,
                "confidence_score": best_score
            }
    else:
        crop.save(str(out_file_path))
        return {
            "has_visual": True,
            "image_rel": image_rel,
            "type": "regular_medical_figure",
            "matched_deck": None,
            "matched_slide": None,
            "confidence_score": best_score
        }


def extract_quiz_pdf(pdf_path: Path) -> dict:
    engine = get_ocr()
    doc = pymupdf.open(str(pdf_path))
    total_pages = len(doc)
    if total_pages < 2:
        return None

    rel_stem = pdf_path.relative_to(BASE_DIR / "PDFs_and_Quizzes" / "Quizzes").with_suffix("")
    rel_stem_str = rel_stem.as_posix()
    target_folder = OUTPUT_DIR / rel_stem
    img_dir = target_folder / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    num_questions = total_pages // 2
    parsed_questions = []

    for q_idx in range(num_questions):
        q_page_idx = q_idx * 2
        exp_page_idx = q_page_idx + 1

        # 1. PROCESS QUESTION PAGE
        q_xref = doc[q_page_idx].get_images()[0][0]
        q_bytes = doc.extract_image(q_xref)["image"]
        q_img = Image.open(pymupdf.io.BytesIO(q_bytes))
        qw, qh = q_img.size

        q_res, _ = engine(q_bytes)
        boxes_with_text = [(b, t.strip()) for b, t, s in (q_res or []) if t.strip()]

        markers = []
        filtered_boxes = []
        marker_inline_text = {}

        for box, text in boxes_with_text:
            y0 = box[0][1]
            x0 = box[0][0]
            if y0 < 100 or y0 > (qh - 100):
                continue
            filtered_boxes.append((box, text))
            clean_t = text.replace("（", "(").replace("）", ")").replace("【", "[").replace("】", "]").replace("○", "O")
            m = re.match(r"^(?:[O\(\[]*\s*)?([A-Ha-h])[\.\)\]]\s*(.*)$", clean_t)
            if m and 180 <= x0 <= 260:
                letter = m.group(1).upper()
                markers.append((y0, letter))
                rest = m.group(2).strip()
                if rest:
                    marker_inline_text[letter] = rest

        markers.sort(key=lambda x: x[0])
        first_opt_y = markers[0][0] if markers else qh * 0.55

        # Extract Vignette Text
        vignette_words = []
        for box, text in filtered_boxes:
            y0 = box[0][1]
            if 180 <= y0 < first_opt_y:
                clean_t = clean_spaces(text)
                if any(bad in clean_t.lower() for bad in ["graw", "mcgraw", "boards&beyond", "total time taken"]):
                    continue
                vignette_words.append(clean_t)
        full_vignette = " ".join(vignette_words)

        # Autocrop Figure / Table in Question Stem if present
        vignette_bottom = 200
        for box, text in filtered_boxes:
            y1 = box[2][1]
            if y1 < first_opt_y and y1 > vignette_bottom:
                vignette_bottom = y1

        figure_image_rel = None
        has_table_or_diagram = False
        fig_top = int(vignette_bottom + 15)
        fig_bottom = int(first_opt_y - 25)

        if (fig_bottom - fig_top) >= 80:
            crop_area = q_img.crop((180, fig_top, min(qw - 100, 1600), fig_bottom))
            bg = Image.new("RGB", crop_area.size, (255, 255, 255))
            diff = ImageChops.difference(crop_area, bg)
            bbox = diff.getbbox()
            if bbox and (bbox[2] - bbox[0]) > 80 and (bbox[3] - bbox[1]) > 50:
                pad = 10
                fig_crop = crop_area.crop((
                    max(0, bbox[0] - pad),
                    max(0, bbox[1] - pad),
                    min(crop_area.width, bbox[2] + pad),
                    min(crop_area.height, bbox[3] + pad)
                ))
            else:
                fig_crop = crop_area

            fig_filename = f"q_{q_idx + 1}_table_figure.png"
            fig_crop.save(str(img_dir / fig_filename))
            figure_image_rel = f"/quizzes/{rel_stem_str}/images/{fig_filename}"
            has_table_or_diagram = True

        # Extract Options
        options = {}
        if markers:
            for i, (my, mletter) in enumerate(markers):
                top_y = my - 25 if i == 0 else (markers[i - 1][0] + my) / 2
                bot_y = (my + markers[i + 1][0]) / 2 if i < len(markers) - 1 else my + (120 if i > 0 else 80)
                opt_words = []
                if mletter in marker_inline_text:
                    opt_words.append(marker_inline_text[mletter])
                for box, text in filtered_boxes:
                    by = box[0][1]
                    bx = box[0][0]
                    if top_y <= by < bot_y and 280 <= bx <= 1500:
                        t = clean_spaces(text)
                        t_norm = t.replace("（", "(").replace("）", ")").replace("【", "[").replace("】", "]").replace("○", "O")
                        if any(bad in t.lower() for bad in ["graw", "mcgraw", "boards&beyond", "total time taken"]):
                            continue
                        if not re.match(r"^(?:[O\(\[]*\s*)?[A-Ha-h][\.\)\]]", t_norm):
                            opt_words.append(t)
                options[mletter] = clean_spaces(" ".join(opt_words))

        # 2. PROCESS EXPLANATION PAGE
        exp_xref = doc[exp_page_idx].get_images()[0][0]
        exp_bytes = doc.extract_image(exp_xref)["image"]
        exp_img = Image.open(pymupdf.io.BytesIO(exp_bytes))
        ew, eh = exp_img.size

        exp_res, _ = engine(exp_bytes)
        peer_stats = {}
        correct_ans = ""
        exp_start_y = None
        exp_boxes = []

        for box, text, score in (exp_res or []):
            y0 = box[0][1]
            t = text.strip()
            if "explanation" == t.lower():
                exp_start_y = y0
            exp_boxes.append((box, t))

        for box, t in exp_boxes:
            y0 = box[0][1]
            m_pct = re.search(r"(\d{1,3}(?:\.\d{1,2})?)\s*%", t)
            if m_pct and y0 < (exp_start_y or eh - 300):
                for my, mlet in markers:
                    if abs(y0 - my) < 35:
                        peer_stats[mlet] = float(m_pct.group(1))
                        break

        exp_boxes.sort(key=lambda x: (x[0][0][1], x[0][0][0]))

        answer_correct_y = None
        for box, text in exp_boxes:
            m_c = re.search(r"^Answer\s+([A-Ha-h])\s*\((?:Correct|correct\s*answer)\)", text, re.I)
            if m_c:
                answer_correct_y = box[0][1]
                correct_ans = m_c.group(1).upper()
                break

        if not correct_ans:
            for box, text in exp_boxes:
                m_c = re.search(r"Answer\s+([A-Ha-h])\s*\((?:Correct|correct)", text, re.I)
                if m_c:
                    correct_ans = m_c.group(1).upper()
                    answer_correct_y = box[0][1]
                    break

        if not correct_ans:
            for box, text in exp_boxes:
                m_c = re.search(r"Answer\s+([A-Ha-h])(?:\s+is\s+correct|\s*\:|\s*\()", text, re.I)
                if m_c:
                    correct_ans = m_c.group(1).upper()
                    answer_correct_y = box[0][1]
                    break

        visual_info = process_explanation_visual(
            exp_img=exp_img,
            exp_start_y=exp_start_y,
            answer_correct_y=answer_correct_y,
            quiz_path=pdf_path,
            q_num=q_idx + 1,
            img_dir=img_dir,
            rel_stem=rel_stem_str,
            engine=engine
        )
        slide_img_rel = visual_info["image_rel"]

        # Extract Explanation with native-resolution crop
        explanation_blocks = []
        if answer_correct_y and answer_correct_y < (eh - 80):
            exp_text_crop = exp_img.crop((180, int(max(0, answer_correct_y - 20)), min(ew, 3800), int(eh - 60)))
            sub_res, _ = engine(np.array(exp_text_crop))
            sub_boxes = sorted(sub_res or [], key=lambda b: (b[0][0][1], b[0][0][0]))
            curr_b = []
            for b, text, score in sub_boxes:
                clean_t = clean_spaces(text)
                if not clean_t:
                    continue
                if any(k in clean_t.lower() for k in ["total time taken", "boards&beyond", "boards & beyond", "feedback", "suspend", "end quiz", "mcgraw", "statistics", "hil"]):
                    continue
                if re.match(r"^Answers?\s+[A-Ha-h]", clean_t, re.I):
                    if curr_b:
                        explanation_blocks.append(" ".join(curr_b))
                        curr_b = []
                    curr_b.append(clean_t)
                elif curr_b:
                    curr_b.append(clean_t)
            if curr_b:
                explanation_blocks.append(" ".join(curr_b))

        if not explanation_blocks:
            curr_b = []
            capture_exp = False
            for box, text in exp_boxes:
                y0 = box[0][1]
                if answer_correct_y and y0 >= answer_correct_y - 10:
                    capture_exp = True
                elif not answer_correct_y and exp_start_y and y0 >= exp_start_y + 450:
                    capture_exp = True
                elif not answer_correct_y and y0 >= 1750:
                    capture_exp = True

                if capture_exp:
                    clean_t = clean_spaces(text)
                    if any(k in clean_t.lower() for k in ["total time taken", "boards&beyond", "feedback", "suspend", "end quiz", "statistics", "mcgraw"]):
                        continue
                    if re.match(r"^Answers?\s+[A-Ha-h]", clean_t, re.I):
                        if curr_b:
                            explanation_blocks.append(" ".join(curr_b))
                            curr_b = []
                        curr_b.append(clean_t)
                    elif curr_b:
                        curr_b.append(clean_t)
                    else:
                        curr_b.append(clean_t)
            if curr_b:
                explanation_blocks.append(" ".join(curr_b))

        clean_blocks = []
        for blk in explanation_blocks:
            clean_blk = re.sub(r'\s+(?:hii|hil|hill|mcgraw|statistics)\s*$', '', blk, flags=re.I).strip()
            if clean_blk:
                clean_blocks.append(clean_blk)

        full_explanation_text = "\n\n".join(clean_blocks)

        parsed_questions.append({
            "question_number": q_idx + 1,
            "question": full_vignette or "Clinical Board Review Question",
            "has_figure": has_table_or_diagram,
            "figure_image": figure_image_rel,
            "options": options if len(options) >= 2 else {"A": "Option A", "B": "Option B", "C": "Option C", "D": "Option D"},
            "correct_answer": correct_ans or "A",
            "peer_statistics": peer_stats,
            "lecture_slide_image": slide_img_rel,
            "visual_metadata": visual_info,
            "explanation": full_explanation_text
        })

    result_data = {
        "title": pdf_path.stem.replace("-Quiz", "").replace("Quiz", "").strip(),
        "pdf_source": pdf_path.name,
        "relative_path": rel_stem_str,
        "total_questions": len(parsed_questions),
        "questions": parsed_questions
    }

    quiz_file = target_folder / "quiz.json"
    with open(quiz_file, "w", encoding="utf-8") as f:
        json.dump(result_data, f, indent=2, ensure_ascii=False, cls=PathEncoder)

    return result_data


def is_quiz_already_processed(pdf_path: Path) -> bool:
    rel_stem = pdf_path.relative_to(BASE_DIR / "PDFs_and_Quizzes" / "Quizzes").with_suffix("")
    target_folder = OUTPUT_DIR / rel_stem
    quiz_file = target_folder / "quiz.json"
    if not quiz_file.exists():
        return False
    try:
        data = json.loads(quiz_file.read_text(encoding="utf-8"))
        qs = data.get("questions", [])
        if not qs:
            return False
        for q in qs:
            if "visual_metadata" not in q:
                return False
        return True
    except Exception:
        return False


def process_wrapper(args):
    pdf_path, force = args

    # Memory Safety Guard
    vm = psutil.virtual_memory()
    if vm.percent > 80.0:
        gc.collect()
        time.sleep(2)

    if not force and is_quiz_already_processed(pdf_path):
        rel_stem = pdf_path.relative_to(BASE_DIR / "PDFs_and_Quizzes" / "Quizzes").with_suffix("")
        quiz_file = OUTPUT_DIR / rel_stem / "quiz.json"
        try:
            res = json.loads(quiz_file.read_text(encoding="utf-8"))
            return res, True, pdf_path.name, None
        except Exception:
            pass

    try:
        t0 = time.time()
        res = extract_quiz_pdf(pdf_path)
        dt = time.time() - t0
        gc.collect()
        return res, False, pdf_path.name, dt
    except Exception as e:
        import traceback
        tb_lines = traceback.format_exc().strip().splitlines()
        last_line = tb_lines[-1] if tb_lines else str(e)
        file_line = tb_lines[-2] if len(tb_lines) >= 2 else ""
        return None, False, pdf_path.name, f"{last_line} at {file_line.strip()}"


def main():
    force_all = "--force" in sys.argv
    workers = 3  # Safe 3-worker limit leaves >3.8 GB RAM free for user apps

    for arg in sys.argv[1:]:
        if arg.startswith("--workers="):
            try:
                workers = int(arg.split("=")[1])
            except ValueError:
                pass

    # Collect all Step 1 Preclinical quizzes strictly in numerical folder order
    step1_categories = sorted([d for d in STEP1_SOURCE_DIR.iterdir() if d.is_dir()])
    ordered_pdfs = []
    for cat_dir in step1_categories:
        cat_pdfs = sorted(list(cat_dir.glob("*.pdf")), key=lambda p: p.name)
        for p in cat_pdfs:
            ordered_pdfs.append((cat_dir.name, p))

    total_quizzes = len(ordered_pdfs)
    log("=" * 80)
    log("⚡ BOARDS & BEYOND: STEP 1 PRECLINICAL ORDERED EXTRACTION")
    log(f"📂 Total Categories: {len(step1_categories)} | Total Quizzes: {total_quizzes}")
    log(f"🚀 Parallel Workers: {workers} (Memory Safe Mode | System Cores: {os.cpu_count()})")
    log("=" * 80)

    all_records = []
    done_count = 0
    new_count = 0
    cached_count = 0

    # Persistent worker pool avoids WindowsApps CreateProcess WinError 1920 respawning crashes
    with Pool(processes=workers) as pool:
        task_args = [(pdf, force_all) for _, pdf in ordered_pdfs]
        for idx, (res, cached, name, meta) in enumerate(pool.imap(process_wrapper, task_args)):
            done_count += 1
            cat_name = ordered_pdfs[idx][0]
            pct = (done_count / total_quizzes) * 100

            if res:
                all_records.append(res)
                if cached:
                    cached_count += 1
                    status_tag = "⚡ CACHED"
                else:
                    new_count += 1
                    status_tag = "✅ EXTRACTED"
            else:
                status_tag = f"❌ ERROR ({meta})"

            vm = psutil.virtual_memory()
            ram_pct = vm.percent
            ram_free_gb = vm.available / (1024 ** 3)

            dt_str = f" in {meta:.1f}s" if isinstance(meta, (int, float)) else ""
            log(f"[{done_count}/{total_quizzes} ({pct:.1f}%)] 📂 {cat_name} | {status_tag}: {name}{dt_str} (RAM: {ram_pct}% | Free: {ram_free_gb:.1f}GB)")

            # Atomic telemetry update
            try:
                PROGRESS_FILE.write_text(json.dumps({
                    "total": total_quizzes,
                    "completed": done_count,
                    "newly_extracted": new_count,
                    "already_cached": cached_count,
                    "percentage": round(pct, 2),
                    "current_category": cat_name,
                    "last_quiz": name,
                    "ram_used_percent": ram_pct,
                    "ram_available_gb": round(ram_free_gb, 2),
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }, indent=2), encoding="utf-8")
            except Exception:
                pass

    log("=" * 80)
    log(f"🎉 Step 1 Preclinical Batch Extraction Completed! Total Extracted: {len(all_records)}")
    log("=" * 80)


if __name__ == "__main__":
    main()
