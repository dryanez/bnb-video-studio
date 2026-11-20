# 🎬 Boards & Beyond (B&B) Studio Player & V9 Gold Quiz Extractor (macOS & Windows)

Standalone, cross-platform medical study platform and automated PDF question-bank extraction engine for **Boards & Beyond USMLE Step 1 (Preclinical) & Step 2 (Clinical)**.

Runs natively on **macOS (Apple Silicon M1/M2/M3/M4 & Intel)** and **Windows**.

---

## ✨ Key Features

### 1. Studio Video Player & USMLE Question Bank UI (`http://localhost:4100`)
- **HTTP 206 Partial-Content Video Streaming:** Instant seeking across all 749 Step 1 & Step 2 MP4 lessons (`1x` to `2x` speed, keyboard shortcuts, automatic file-descriptor cleanup).
- **Interactive Chapter Quizzes (`Q1`–`QN` Navigator):**
  - Full clinical vignettes with **Pixel-Perfect Cropped Question Tables & Graphs** (`q_X_table_figure.png`).
  - **Peer Performance Distribution (`%`)** revealed per option choice upon answering.
  - **Smart Explanation Visuals:** Automatically displays either **`⚡ 4K UHD Master Slide`** (300 DPI vector render from the companion lecture deck) or **`📊 Clinical Reference Table / Medical Diagram`** (unclipped original table/chart/diagram).
  - **Color-Coded Pathophysiological Rationales:** Separate Emerald card for the correct answer rationale and Slate cards for each distractor (`A`–`F`).
- **AI Synchronized Transcripts & Companion Slide PDF Downloads.**

---

### 2. V9 Gold Extraction & Repair Engine (`scripts/`)
Solves every quirk of the rasterized Boards & Beyond Quiz PDFs:

1. **Full-Height Question & Option Capture (Zero 910px Viewport Cutoff):**
   - Many Question-page screenshots (even pages `0, 2, 4...`) were captured in a `1920×910` browser viewport that clipped options `(B)–(E)` whenever a table or graph appeared in the stem.
   - `scripts/repair_question_pages_fast.py` reads the question stem, cropped question table/graph, options `(A)–(G)`, and peer statistics `%` from the **top section of the full-height Explanation page** (odd pages `1, 3, 5...`), which is never truncated.
2. **Standalone Reference Tables & Diagrams vs. 16:9 Lecture Slides (In Answers):**
   - Some explanation sections contain a **standalone reference table** (e.g. `Anesthetic Agent | Oil:gas partition coefficient` or `Acid-Base Compensation Calculation`), a **medical chart/graph** (e.g. $F_A/F_I$ curves with external axis labels), or an **older vertical-stripe slide** (e.g. `Minimum Alveolar Concentration — Additive Properties`).
   - **Rule Enforced in Both `extract_all_quizzes_perfect.py` and `repair_question_pages_fast.py`:**
     - **Unclipped Full-Card Bounding Box:** Crops across the full explanation card width (`x = 220..1500`) from `cy + 65` (immediately below the blue breadcrumb line) to `vis_bot` (immediately above `Answer X (correct answer):`). Left-side text on vertical-stripe slides and outside axis labels (`FA/FI`, `Time (min)`) are **never cut off**.
     - **True Horizontal Slide Banner Filter (`>= 660px` wide):** Only upgrades to a 4K vector slide from `Slides_and_Notes/` when the explanation visual has an unbroken cyan-blue horizontal slide banner spanning $\ge 660\text{ px}$ (and total visual width $\ge 680\text{ px}$). Narrower blue-header tables (`~450–620px` wide) are strictly preserved as **`regular_medical_figure`** and never falsely replaced by a lecture slide.
3. **Question Stem Table & Graph Auto-Cropper:**
   - Detects white graph cards and centered table blocks above the options container, strips out the `65×65` circular pencil icon on the right margin, saves `q_X_table_figure.png`, and excludes the table cell coordinates from the question vignette text so table numbers never get mashed into the question sentence.

---

## 🍎 Quick Start on macOS (MacBook / iMac / Mac Studio)

### 1. Clone This Repository
```bash
git clone https://github.com/dryanez/bnb-video-studio.git
cd bnb-video-studio
```

### 2. Point to Your `Telegram_BnB_Videos` Folder
The server and Python scripts automatically look for `Telegram_BnB_Videos` in:
- `~/Telegram_BnB_Videos`
- `~/Desktop/Telegram_BnB_Videos`
- `/Volumes/<AnyExternalDrive>/Telegram_BnB_Videos`
- `./Telegram_BnB_Videos`

Or you can explicitly set `BNB_DATA_DIR` to any path on your Mac or external SSD/HDD:
```bash
export BNB_DATA_DIR="/Volumes/MySSD/Telegram_BnB_Videos"
```

Expected folder structure inside `Telegram_BnB_Videos`:
```text
Telegram_BnB_Videos/
├── Step 1 - Preclinical/             # MP4 video lessons by subject
├── Step 2 - Clinical/                # MP4 video lessons by specialty
├── PDFs_and_Quizzes/
│   ├── Quizzes/                      # 730 Official Quiz PDFs
│   └── Slides_and_Notes/             # Official Lecture Slide PDFs
├── quizzes_extracted/                # Extracted quiz.json + images/
└── transcripts/                      # Video transcripts (.json / .txt)
```

### 3. Start the Web Player on Mac
```bash
chmod +x start_mac.sh
./start_mac.sh
```
Or manually:
```bash
npm install
node server.js
```
Then open **[http://localhost:4100](http://localhost:4100)** in Safari or Chrome.

---

## 🧠 Running Quiz Extraction & Repair on macOS

### 1. Install Python Dependencies on Mac
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Fast Repair / Re-Extraction of Question Stems, Tables, Options & Standalone Answer Visuals
Use **`scripts/repair_question_pages_fast.py`** when `quiz.json` files already exist and you want to fix or audit question stems, question tables/graphs, options `A`–`E`, peer `%` stats, and standalone explanation tables/figures without re-rendering existing 4K slides:

```bash
# Run across all 730 quizzes with 3 parallel workers (skips already-good quizzes automatically)
python3 scripts/repair_question_pages_fast.py --workers=3

# Force re-process a specific quiz PDF
python3 scripts/repair_question_pages_fast.py --force "/path/to/01. Inhaled Anesthetics-Quiz.pdf"

# Force re-process an entire subject folder
python3 scripts/repair_question_pages_fast.py --force "/path/to/PDFs_and_Quizzes/Quizzes/Step 1 - Preclinical/06_Cardiology"
```

### 3. Full From-Scratch Extraction (Question + 4K Slide Matching + Full Explanation OCR)
Use **`scripts/extract_all_quizzes_perfect.py`** to extract brand-new Quiz PDFs from scratch:

```bash
# Run full batch extraction across all 730 PDFs (resumable via checkpoint)
python3 scripts/extract_all_quizzes_perfect.py --workers=4

# Extract a single Quiz PDF from scratch with --force
python3 scripts/extract_all_quizzes_perfect.py --force "/path/to/01. Acid Base Principles-Quiz.pdf"
```

### 4. Generate Standalone Side-by-Side PDF Audit HTML
```bash
python3 scripts/generate_html_preview.py
```
Opens a standalone HTML runner (`public/quiz_web_preview.html`) with a **Side-by-Side Raw PDF Audit** toggle comparing extracted questions/slides against the original ground-truth PDF pages.

---

## 🪟 Quick Start on Windows

```powershell
start_windows.bat
# Or manually:
npm install
node server.js
```
And for Python extraction on Windows:
```powershell
pip install -r requirements.txt
python scripts/repair_question_pages_fast.py --workers=3
```
