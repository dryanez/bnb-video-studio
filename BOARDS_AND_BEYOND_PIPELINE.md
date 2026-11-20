# 🎬 BOARDS & BEYOND: COMPLETE PIPELINE & RE-EXTRACTION HANDOFF SPECIFICATION

> **Target Audience:** Any AI Agent, Senior Data Engineer, or Developer taking over the Boards & Beyond curriculum processing, question bank extraction, and web player streaming pipeline.  
> **Repository Location:** `d:/Anti/Eunacom`  
> **Master Storage Directory:** `D:/Telegram_BnB_Videos`  
> **Date of Audit & Standard:** September 2026  

---

## 1. Executive Summary & Status

The project curates and hosts the complete **Boards & Beyond (B&B)** USMLE Step 1 (Preclinical) and Step 2 (Clinical) medical education library, paired with an interactive offline streaming player (`bnb-video-player`) and an interactive question bank with clinical vignettes, lab tables, answer options, and lecture slide explanations.

### Current Inventory & Metrics:
* **Total Video Files:** **749 videos** on disk (`510` Step 1 + `238` Step 2 + 1 test file).
* **Official Quiz PDFs:** **730 PDFs** in `D:/Telegram_BnB_Videos/PDFs_and_Quizzes/Quizzes`.
* **Total Extracted Questions:** **4,815 questions** across **717 folders**.
* **Current Matching Rate to Videos:** **725 out of 749 videos (96.8%)** have a mapped chapter quiz.
* **Extraction Health Status:**
  * **Critical Flaw in Existing Data:** An older legacy extractor (`V5 Fast Incremental`) ran on August 28 and corrupted **69.4% of question stems** with `"Clinical Board Review Question"`, cut off the first line of **16% of vignettes**, omitted **98.3% of question lab tables**, and left words glued together without spaces.
  * **The Solution:** A high-fidelity extraction standard was developed and verified on `01. Acid Base Principles-Quiz.pdf` that achieves **100% full stem preservation, 100% table/diagram auto-cropping, and 100% lecture slide explanation extraction**.

---

## 2. Directory Structure & Asset Topology

All master video and PDF assets reside on physical drive `D:` to preserve system drive space:

```text
D:/Telegram_BnB_Videos/
├── Step 1 - Preclinical/             # 510 MP4 video lessons organized by 22 subjects
│   ├── 01_Anesthesia/
│   ├── 02_Basic Pharmacology/
│   ├── 04_Biochemistry/
│   ├── 06_Cardiology/
│   ├── 09_Endocrinology/
│   ├── 21_Renal/
│   └── ...
├── Step 2 - Clinical/                # 238 MP4 video lessons organized by clinical specialties
│   ├── 01_Behavioral Science/
│   ├── 11_Obstetrics and Gynecology/
│   ├── 15_Renal and Genitourinary/
│   ├── 16_Surgery and Anesthesia/
│   └── ...
├── PDFs_and_Quizzes/
│   ├── Quizzes/                      # 730 Official Quiz PDFs (2 pages per question)
│   │   ├── General/                  # 12 quiz decks
│   │   ├── Step 1 - Preclinical/     # 586 quiz decks
│   │   └── Step 2 - Clinical/        # 134 quiz decks
│   └── Slides_and_Notes/             # Official lecture slide decks (1 PDF per video lesson)
├── quizzes_extracted/                # Master extracted JSON and cropped visual assets
│   ├── Step 1 - Preclinical/
│   │   └── [Subject]/[Lesson-Quiz]/
│   │       ├── quiz.json             # Modular quiz dataset for frontend
│   │       └── images/
│   │           ├── q_1_table_figure.png    # High-res cropped lab table / histology / ECG
│   │           ├── q_1_lecture_slide.png   # Cropped slide mechanism from explanation
│   │           └── exp_1.png               # Full-page high-res fallback
│   ├── Step 2 - Clinical/
│   └── extractor.log                 # Continuous progress log
├── transcripts/                      # Whisper JSON and TXT video transcripts
└── quizzes_bank.json                 # Monolithic 10 MB master question bank
```

---

## 3. Anatomy of Boards & Beyond Quiz PDFs

Understanding how the source PDFs are constructed is crucial for correct parsing:

1. **Pure Rasterized Screenshots (Lossless 1080p PNGs):**
   * B&B Quiz PDFs contain **zero selectable vector text** (`page.get_text()` returns empty strings).
   * Every page contains exactly **one embedded PNG image** (extracted via `doc.extract_image(xref)`).
   * **Question Pages:** Resolution is typically `1920 x 1300` to `1920 x 1620 px`.
   * **Explanation Pages:** Resolution is typically `1920 x 2300` to `1920 x 3300 px`.
2. **Page Alternation Scheme:**
   * A PDF with $N$ questions contains exactly $2N$ pages.
   * Odd pages ($0, 2, 4, 6, \dots$ in 0-indexed PyMuPDF): **Question Slides**.
   * Even pages ($1, 3, 5, 7, \dots$): **Explanation Slides**.

### Visual Layout of a Question Slide (1920 px Width):
* `y = 0` to `120`: Dark blue top navigation bar (`Item X of Y`, `Mark`, `Question ID`, `Instructions`, `Lab Values`, `Calculator`).
* `y ≈ 140` to `y_question_end`: Clinical vignette in dark grey typography on a white card. Ends with a question mark `?`.
* `y_question_end` to `y_options_start`: **Lab Table / Clinical Diagram / Image Box** (if present).
  * Contains Chemistry panels, ABGs, pressure-volume loops, ECGs, or histology photos.
  * In table questions where the table *is* the question choices (e.g. Acid Base Q3), the table contains rows labelled `A`, `B`, `C`, `D`, `E`.
* `y_options_start` to `qh - 120`: The Option Box with light-blue outline. Radio buttons `(A)`, `(B)`, `(C)`, `(D)`, `(E)` on the left (`x ≈ 270`), text label to the right (`x ≈ 315`).
* `qh - 120` to `qh`: Bottom controls (`Submit`, `Boards&Beyond`, timer, stats).

### Visual Layout of an Explanation Slide:
* `y = 0` to `y ≈ 1350`: Recap of question and peer performance distribution (`%` per choice).
* `y ≈ 1380` to `1450`: Green card showing `Correct Answer` and `XX.XX% Answered Correctly`.
* Below green card: **The Lecture Slide Mechanism Box**.
  * Shows the exact lecture slide from Dr. Ryan's video course (e.g., MUDPILES mnemonic, Winter's formula calculation, coagulation cascade).
* Below slide box: Detailed textual explanation:
  * `Answer X (correct answer):` Detailed pathophysiology and math.
  * `Answer Y (incorrect answer):` Why distractors are wrong.

---

## 4. Root Causes of Previous V5 Parser Failure & Gold V9 Solutions

The previous `V5 Fast Incremental` script failed due to 5 specific architectural flaws, now resolved in `V9 Gold`:

1. **Blue Header Contrast & DBNet Downscale Issue (Missing First Lines):**
   * RapidOCR's DBNet by default has `limit_side_len = 736`. When processing a 1920×1620 image, it downscaled it by 2.2x, causing small 16px fonts to blur to 7px and miss the very first sentence.
   * Furthermore, artificial white header masks introduced harsh artificial contrast edges that blinded DBNet.
   * **V9 Gold Solution:** Configure `_ocr_engine.text_det.limit_side_len = 1600` for crystal-clear native resolution, and filter out header items purely through geometric box bounds (`y0 < 100`, `x0 < 180`, `y0 > qh - 100`).

2. **Loose Naive Crops vs. Pixel-Perfect Tables (The Pixel Feedback):**
   * Naive vertical band crops between the question mark and options box captured unwanted web UI clutter: the circular blue pencil edit button (`x ≈ 1150`), the top border line of Option A, and excess white margins.
   * **V9 Gold Solution:** OpenCV Morphological Line & Contour Grid Detection (`kernel_h = (60, 1)`, `kernel_v = (1, 30)`). Detects the precise table outer rectangle down to the exact pixel. If multiple tables are present (e.g. lab panel + options matrix), each table is cropped to its exact boundary and vertically stitched with uniform padding, rejecting pencil icons and UI borders.

3. **Clinical Diagrams, CT Scans & Histology:**
   * Non-table figures (CT scans, histology slides, ECGs, gross pathology) lack morphological grid lines.
   * **V9 Gold Solution:** Connected component analysis on non-background pixels (`diff from RGB(246, 246, 255) > 18`). Filters for large clinical images (`area > 12,000`, `w > 180`, `h > 100`), cleanly rejecting the circular pencil icon (`area ≈ 2,500`) and the options container. Pure text questions return `None` (zero false positives).

4. **Multi-line Option Baseline Offset & Chinese Bracket Markers:**
   * Radio buttons and option letters `(A)` are vertically centered next to two-line options. Sorting boxes purely by `(y, x)` severed the first line from Option A. Furthermore, web radio buttons were frequently OCR'd with East Asian brackets (e.g. `'A】'`).
   * **V9 Gold Solution:** Normalize unicode brackets (`【`, `】`, `（`, `）`, `○`) and identify all option markers `(A)-(H)` with their Y coordinates. Assign all text between `Marker[i]` and `Marker[i+1]` to Option `i`. This preserves 100% of multi-line option text.

5. **Peer Statistics Omission:**
   * Percentage statistics (`XX.XX%`) sit in their own column on the explanation page at `x ≈ 760`, separate from the option letter text box at `x ≈ 260`.
   * **V9 Gold Solution:** Map explanation page percentage boxes to option markers by Y-coordinate proximity (`abs(y_stat - y_marker) < 35`), populating `peer_statistics` with exact floats.

---

## 5. Standard Data Schema (`quiz.json`)

Each folder inside `quizzes_extracted/` must contain a `quiz.json` conforming to this schema:

```json
{
  "title": "01. Acid Base Principles",
  "pdf_source": "01. Acid Base Principles-Quiz.pdf",
  "relative_path": "Step 1 - Preclinical/21_Renal/01. Acid Base Principles-Quiz",
  "total_questions": 6,
  "questions": [
    {
      "question_number": 1,
      "question": "A 23-year-old woman with a history of poorly-controlled type I diabetes presents to the emergency department with abdominal pain, nausea, and vomiting. She has felt unwell for the past three days and has had persistent vomiting. She has not taken her regular insulin. Her temperature is 97.8°F, heart rate is 132/min, and blood pressure is 104/66. She appears fatigued and pale on examination. Laboratory studies are shown below. Which of the following best describes the patient's acid-base status?",
      "has_figure": true,
      "figure_image": "/quizzes/Step 1 - Preclinical/21_Renal/01. Acid Base Principles-Quiz/images/q_1_table_figure.png",
      "options": {
        "A": "Anion gap metabolic acidosis with respiratory compensation",
        "B": "Anion gap metabolic acidosis without respiratory compensation",
        "C": "Mixed anion gap metabolic acidosis with metabolic alkalosis",
        "D": "Mixed anion gap metabolic acidosis with non-anion gap acidosis",
        "E": "Mixed non-anion gap metabolic acidosis with respiratory acidosis",
        "F": "Non-anion gap metabolic acidosis without respiratory compensation"
      },
      "correct_answer": "A",
      "peer_statistics": {
        "A": 66.09,
        "B": 23.61,
        "C": 2.33,
        "D": 1.61,
        "E": 3.09
      },
      "lecture_slide_image": "/quizzes/Step 1 - Preclinical/21_Renal/01. Acid Base Principles-Quiz/images/q_1_lecture_slide.png",
      "explanation": "Answer A (correct answer): This woman has poorly controlled diabetes... Winter's Formula: (1.5 x HCO3) + 8 = PaCO2 +/- 2...\n\nAnswer B (incorrect answer): This patient has appropriate respiratory compensation..."
    }
  ]
}
```

---

## 6. Web Player Integration (`bnb-video-player`)

The local player runs at `http://localhost:4100` via Express.js (`bnb-video-player/server.js`):

* **Video Streaming:** `GET /api/stream?path=<relPath>` supports HTTP 206 Partial Content (range requests) for instant seeking across 4K/1080p MP4s.
* **Quiz Delivery:** `GET /api/quiz?path=<videoRelPath>`:
  1. Sanitizes video filename: strips leading numbers (`01_`, `1342_`), removes spaces and punctuation to create a canonical key.
  2. Traverses `quizzes_extracted/` to find a folder whose canonical key matches or is a substring.
  3. Returns `quiz.json` with `{ available: true, ...data }`.
* **Static Assets:** `app.use('/quizzes', express.static('D:/Telegram_BnB_Videos/quizzes_extracted'))`.
  * Paths like `/quizzes/Step 1 - Preclinical/21_Renal/01. Acid Base Principles-Quiz/images/q_1_table_figure.png` resolve automatically.
* **Frontend UI (`bnb-video-player/public/index.html`):**
  * Renders isolated `figure_image` directly above the option cards with a full-screen zoom link.
  * When a choice is clicked, reveals the explanation card, the correct/incorrect badge, the formatted explanation, and the lecture slide diagram.

---

## 7. How to Run the Full Batch Re-Extraction

The production extraction script is located at:  
[`scripts/extract_all_quizzes_perfect.py`](file:///d:/Anti/Eunacom/scripts/extract_all_quizzes_perfect.py)

### Execution Command:
```powershell
# From workspace root d:\Anti\Eunacom
python -u scripts/extract_all_quizzes_perfect.py
```

### Performance & Multi-Processing Specs:
* **Hardware Utilization:** Runs with `ProcessPoolExecutor` utilizing 4 to 8 CPU worker processes.
* **Throughput:** ~2.5 to 3.5 seconds per PDF on modern multi-core CPU.
* **Total Time for All 730 Quizzes:** ~35 to 45 minutes for the entire library.
* **Resume Capability:** Checks whether `quiz.json` has `has_figure: true` or verified stems. If already cleanly extracted, it skips automatically, allowing instant safe resumes.
* **Master Bank Sync:** Once all individual folders finish, it merges all records into `D:/Telegram_BnB_Videos/quizzes_bank.json`.

---

## 8. Verification & Quality Checklist for the Next Agent

Before concluding that a quiz or batch is valid, verify these 5 criteria:

1. [ ] **No Placeholder Text:** Ensure `grep "Clinical Board Review Question" quizzes_extracted/**/*.json` returns **0 results**.
2. [ ] **Table Integrity:** For any lesson in Renal, Cardiology, Endocrine, or Pharmacology, check that `images/q_*_table_figure.png` exists and is non-empty.
3. [ ] **Vignette Completeness:** Check that question strings start with a capital letter (e.g., `A 23-year-old...`, `A 55-year-old...`) rather than lowercase mid-sentence fragments.
4. [ ] **Option Completeness:** Check that `options` object has at least keys `A, B, C, D` and that values are non-empty strings.
5. [ ] **Server Availability:** Start `node server.js` in `bnb-video-player` and load `http://localhost:4100` to verify audio/video playback and quiz rendering.
