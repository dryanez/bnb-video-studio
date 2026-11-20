import os
import sys
import json
import base64
from pathlib import Path
import pymupdf

BASE_DIR = Path("D:/Telegram_BnB_Videos")
QUIZ_DIR = BASE_DIR / "quizzes_extracted" / "Step 1 - Preclinical" / "21_Renal" / "01. Acid Base Principles-Quiz"
PDF_PATH = BASE_DIR / "PDFs_and_Quizzes" / "Quizzes" / "Step 1 - Preclinical" / "21_Renal" / "01. Acid Base Principles-Quiz.pdf"
ARTIFACT_PATH = Path(r"C:\Users\PC\.gemini\antigravity\brain\2e83789b-4111-4e63-b420-a2b371336846\quiz_web_preview.html")
LOCAL_PATH = Path(r"D:\Anti\Eunacom\quiz_web_preview.html")

# Load quiz.json
quiz_data = json.loads((QUIZ_DIR / "quiz.json").read_text(encoding="utf-8"))

# Load PDF for raw page comparisons
doc = pymupdf.open(str(PDF_PATH))

# Prepare question objects with base64 embedded images
processed_questions = []

for idx, q in enumerate(quiz_data["questions"]):
    q_num = q["question_number"]
    
    # 1. Cropped Table / Figure
    fig_b64 = None
    fig_file = QUIZ_DIR / "images" / f"q_{q_num}_table_figure.png"
    if fig_file.exists():
        fig_b64 = base64.b64encode(fig_file.read_bytes()).decode("ascii")
        
    # 2. Lecture Slide Mechanism
    slide_b64 = None
    slide_file = QUIZ_DIR / "images" / f"q_{q_num}_lecture_slide.png"
    if slide_file.exists():
        slide_b64 = base64.b64encode(slide_file.read_bytes()).decode("ascii")
        
    # 3. Raw PDF Question Page Image (for side-by-side verification)
    q_xref = doc[idx * 2].get_images()[0][0]
    raw_q_bytes = doc.extract_image(q_xref)["image"]
    raw_q_b64 = base64.b64encode(raw_q_bytes).decode("ascii")
    
    # 4. Raw PDF Explanation Page Image
    exp_xref = doc[idx * 2 + 1].get_images()[0][0]
    raw_exp_bytes = doc.extract_image(exp_xref)["image"]
    raw_exp_b64 = base64.b64encode(raw_exp_bytes).decode("ascii")
    v_meta = q.get("visual_metadata", {})
    processed_questions.append({
        "number": q_num,
        "question": q["question"],
        "options": q["options"],
        "correct": q["correct_answer"],
        "peer_stats": q.get("peer_statistics", {}),
        "explanation": q["explanation"],
        "figure_b64": fig_b64,
        "slide_b64": slide_b64,
        "v_type": v_meta.get("type", "none"),
        "v_deck": v_meta.get("matched_deck"),
        "v_slide": v_meta.get("matched_slide"),
        "v_score": v_meta.get("confidence_score"),
        "raw_q_b64": raw_q_b64,
        "raw_exp_b64": raw_exp_b64
    })

html_content = f"""<!DOCTYPE html>
<html lang="en" class="h-full">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Boards & Beyond - {quiz_data['title']} (Web Runner Preview)</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap" rel="stylesheet">
  <style>
    body {{ font-family: 'Inter', system-ui, -apple-system, sans-serif; }}
    .vignette-font {{ font-family: 'Source Serif 4', Georgia, serif; }}
    ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
    ::-webkit-scrollbar-track {{ background: #f1f5f9; }}
    ::-webkit-scrollbar-thumb {{ background: #cbd5e1; border-radius: 3px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: #94a3b8; }}
  </style>
</head>
<body class="bg-slate-50 text-slate-900 h-full flex flex-col antialiased">

  <!-- Top Blue Navigation Bar (Boards & Beyond Masterclass Theme) -->
  <header class="bg-[#1e3a8a] text-white shadow-md select-none shrink-0">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex items-center justify-between h-14">
        <div class="flex items-center space-x-3">
          <div class="bg-white/10 p-1.5 rounded-lg">
            <svg class="w-5 h-5 text-amber-400" fill="currentColor" viewBox="0 0 20 20">
              <path d="M9 4.804A7.968 7.968 0 005.5 4c-1.255 0-2.443.29-3.5.804v10A7.969 7.969 0 015.5 14c1.669 0 3.218.51 4.5 1.385A7.962 7.962 0 0114.5 14c1.255 0 2.443.29 3.5.804v-10A7.968 7.968 0 0014.5 4c-1.255 0-2.443.29-3.5.804V12a1 1 0 11-2 0V4.804z"/>
            </svg>
          </div>
          <div>
            <span class="text-xs font-medium uppercase tracking-wider text-blue-200">Boards &amp; Beyond Clinical Bank</span>
            <h1 class="text-sm font-bold text-white tracking-tight">{quiz_data['title']}</h1>
          </div>
        </div>

        <!-- Center: Question Navigator -->
        <div class="flex items-center space-x-1" id="tab-container">
          <!-- Populated by JS -->
        </div>

        <!-- Right: Status / Side-by-Side Toggle -->
        <div class="flex items-center space-x-3">
          <button id="toggle-pdf-btn" onclick="togglePdfComparison()" class="text-xs px-3 py-1.5 bg-blue-700/80 hover:bg-blue-600 border border-blue-400/40 rounded-md font-medium transition flex items-center space-x-1.5 shadow-sm">
            <svg class="w-3.5 h-3.5 text-blue-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2"/>
            </svg>
            <span id="pdf-toggle-text">Side-by-Side PDF Audit</span>
          </button>
          <div class="text-xs bg-black/20 px-2.5 py-1 rounded text-blue-100 font-mono" id="score-badge">Score: 0 / 6</div>
        </div>
      </div>
    </div>
  </header>

  <!-- Subheader Breadcrumb & Controls -->
  <div class="bg-white border-b border-slate-200 px-6 py-2.5 flex items-center justify-between text-xs text-slate-500 shadow-sm shrink-0">
    <div class="flex items-center space-x-2">
      <span class="font-medium text-slate-700">Renal &amp; Genitourinary</span>
      <span>&rsaquo;</span>
      <span class="font-medium text-slate-700">Acid-Base Physiology</span>
      <span>&rsaquo;</span>
      <span class="text-blue-600 font-semibold" id="current-q-label">Question 1 of 6</span>
    </div>
    <div class="flex items-center space-x-4">
      <button onclick="prevQuestion()" class="hover:text-slate-900 font-medium flex items-center space-x-1">
        <span>&larr; Previous</span>
      </button>
      <button onclick="nextQuestion()" class="hover:text-slate-900 font-medium flex items-center space-x-1">
        <span>Next &rarr;</span>
      </button>
    </div>
  </div>

  <!-- Main Content Workspace -->
  <main class="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
    <div class="max-w-7xl mx-auto grid grid-cols-1 gap-6 transition-all duration-300" id="main-layout">
      
      <!-- Primary Question / Extracted Content Column -->
      <div class="space-y-6" id="extracted-view-col">
        
        <!-- Question Card -->
        <div class="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          
          <!-- Card Header -->
          <div class="bg-slate-50/80 px-6 py-4 border-b border-slate-200 flex items-center justify-between">
            <div class="flex items-center space-x-3">
              <span class="px-2.5 py-1 bg-blue-100 text-blue-800 text-xs font-bold rounded-md uppercase tracking-wider" id="q-badge">Question 1</span>
              <span class="text-xs text-slate-400">|</span>
              <span class="text-xs text-slate-500 font-medium">USMLE Step 1 / EUNACOM Clinical Vignette</span>
            </div>
            <div class="flex items-center space-x-2 text-xs text-emerald-600 font-medium" id="status-pill">
              <span class="w-2 h-2 rounded-full bg-slate-300" id="status-dot"></span>
              <span id="status-text">Unanswered</span>
            </div>
          </div>

          <!-- Question Body -->
          <div class="p-6 sm:p-8 space-y-6">
            
            <!-- Clinical Vignette Text -->
            <div class="vignette-font text-slate-800 text-base sm:text-lg leading-relaxed font-normal" id="vignette-text">
              <!-- Inserted by JS -->
            </div>

            <!-- Pixel-Perfect Table / Figure Container -->
            <div id="figure-container" class="hidden my-6">
              <div class="bg-slate-50 rounded-xl border border-slate-200 p-4 shadow-sm inline-block max-w-full">
                <div class="flex items-center justify-between pb-2 mb-3 border-b border-slate-200">
                  <div class="flex items-center space-x-2 text-xs font-semibold text-slate-600">
                    <svg class="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                    </svg>
                    <span>CLINICAL LAB DATA / FIGURE</span>
                  </div>
                  <span class="text-[10px] bg-blue-50 text-blue-600 font-mono px-2 py-0.5 rounded border border-blue-200 font-medium">OpenCV 100% Pixel-Perfect Crop</span>
                </div>
                <!-- The image -->
                <div class="overflow-x-auto flex justify-center bg-white p-2 rounded-lg border border-slate-100">
                  <img id="figure-img" src="" alt="Clinical Table" class="max-h-[380px] object-contain rounded shadow-sm">
                </div>
              </div>
            </div>

            <!-- Options Box -->
            <div class="space-y-3 pt-2" id="options-container">
              <!-- Options populated by JS -->
            </div>

            <!-- Action Bar -->
            <div class="pt-4 flex items-center justify-between border-t border-slate-100">
              <button id="submit-btn" onclick="submitCurrentAnswer()" class="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-semibold text-sm rounded-lg shadow-sm hover:shadow transition flex items-center space-x-2">
                <span>Submit Answer</span>
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/>
                </svg>
              </button>
              <button id="toggle-exp-btn" onclick="toggleExplanation()" class="text-xs text-slate-500 hover:text-slate-800 font-medium underline">
                Reveal Explanation
              </button>
            </div>

          </div>
        </div>

        <!-- Explanation & Lecture Slide Section (Revealed on Submit) -->
        <div id="explanation-card" class="hidden bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden transition-all duration-300">
          
          <!-- Explanation Header with Result Banner -->
          <div id="result-banner" class="px-6 py-4 border-b flex items-center justify-between">
            <div class="flex items-center space-x-3">
              <div id="result-icon-box" class="w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm"></div>
              <div>
                <h3 id="result-title" class="text-sm font-bold tracking-tight"></h3>
                <p id="result-subtitle" class="text-xs text-slate-500"></p>
              </div>
            </div>
            <!-- Peer Stats Breakdown Summary -->
            <div class="text-right text-xs text-slate-500">
              <span class="font-bold text-slate-700" id="correct-pct-summary"></span> of peers answered correctly
            </div>
          </div>

          <div class="p-6 sm:p-8 space-y-8">
            
            <!-- Peer Statistics Distribution Bar Charts -->
            <div>
              <div class="flex items-center justify-between mb-3">
                <h4 class="text-xs font-bold uppercase tracking-wider text-slate-500">Peer Performance Distribution</h4>
                <span class="text-[11px] text-slate-400">Total verified respondents</span>
              </div>
              <div class="space-y-2 bg-slate-50 p-4 rounded-xl border border-slate-200" id="peer-bars-container">
                <!-- Populated by JS -->
              </div>
            </div>

            <!-- Embedded Lecture Mechanism Slide (High-Yield mechanism) -->
            <div id="slide-container" class="hidden">
              <div class="flex items-center justify-between mb-3">
                <div class="flex items-center space-x-2">
                  <span class="w-2 h-2 rounded-full bg-amber-500"></span>
                  <h4 class="text-xs font-bold uppercase tracking-wider text-slate-700">Dr. Ryan Lecture Slide Mechanism</h4>
                </div>
                <span id="slide-badge" class="text-[10px] font-mono px-2 py-0.5 rounded font-semibold"></span>
              </div>
              <div class="bg-slate-900/5 p-3 rounded-xl border border-slate-200 overflow-hidden flex justify-center">
                <img id="slide-img" src="" alt="Lecture Slide Mechanism" class="max-h-[420px] object-contain rounded-lg shadow">
              </div>
            </div>

            <!-- Pathophysiology Rationale & Distractor Breakdown -->
            <div>
              <h4 class="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">Pathophysiological Rationale</h4>
              <div class="prose prose-slate max-w-none text-sm text-slate-700 space-y-4 leading-relaxed" id="rationale-text">
                <!-- Populated by JS -->
              </div>
            </div>

          </div>
        </div>

      </div>

      <!-- Secondary Column: Real Raw PDF Page Comparison (Side-by-Side) -->
      <div id="pdf-compare-col" class="hidden space-y-6">
        <div class="bg-white rounded-xl border border-blue-200 shadow-sm overflow-hidden sticky top-4">
          <div class="bg-blue-900 text-white px-5 py-3.5 flex items-center justify-between">
            <div class="flex items-center space-x-2">
              <svg class="w-4 h-4 text-amber-400" fill="currentColor" viewBox="0 0 20 20">
                <path d="M4 3a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V5a2 2 0 00-2-2H4zm12 12H4l4-8 3 6 2-4 3 6z"/>
              </svg>
              <h3 class="text-xs font-bold uppercase tracking-wider">Original Raw PDF Source (Ground Truth)</h3>
            </div>
            <div class="flex items-center space-x-1">
              <button onclick="setPdfTab('question')" id="btn-pdf-q" class="text-[11px] px-2.5 py-1 bg-blue-700 rounded font-semibold text-white">Question Page</button>
              <button onclick="setPdfTab('explanation')" id="btn-pdf-exp" class="text-[11px] px-2.5 py-1 bg-blue-950 text-blue-200 rounded hover:text-white font-medium">Explanation Page</button>
            </div>
          </div>
          <div class="p-3 bg-slate-100 max-h-[calc(100vh-140px)] overflow-y-auto flex justify-center">
            <img id="raw-pdf-img" src="" alt="Raw PDF Page" class="w-full h-auto rounded shadow border border-slate-300">
          </div>
        </div>
      </div>

    </div>
  </main>

  <script>
    const questionsData = {json.dumps(processed_questions)};
    let currentIndex = 0;
    let userAnswers = Array(questionsData.length).fill(null);
    let submittedState = Array(questionsData.length).fill(false);
    let pdfComparisonOpen = false;
    let activePdfTab = 'question';

    function init() {{
      buildTabs();
      renderQuestion(0);
    }}

    function buildTabs() {{
      const c = document.getElementById('tab-container');
      c.innerHTML = '';
      questionsData.forEach((q, idx) => {{
        const btn = document.createElement('button');
        btn.id = `tab-btn-${{idx}}`;
        btn.className = `w-8 h-8 rounded-full text-xs font-bold transition flex items-center justify-center ${{
          idx === currentIndex 
            ? 'bg-white text-blue-900 shadow-md font-extrabold scale-105' 
            : 'text-blue-200 hover:bg-blue-800/80 hover:text-white'
        }}`;
        btn.innerText = q.number;
        btn.onclick = () => switchQuestion(idx);
        c.appendChild(btn);
      }});
    }}

    function updateTabStyles() {{
      questionsData.forEach((q, idx) => {{
        const btn = document.getElementById(`tab-btn-${{idx}}`);
        const isCurrent = idx === currentIndex;
        const isSubmitted = submittedState[idx];
        const isCorrect = userAnswers[idx] === q.correct;
        
        btn.className = `w-8 h-8 rounded-full text-xs font-bold transition flex items-center justify-center ${{
          isCurrent 
            ? 'ring-2 ring-white bg-white text-blue-900 shadow-md scale-105' 
            : isSubmitted 
              ? (isCorrect ? 'bg-emerald-600 text-white' : 'bg-rose-600 text-white')
              : 'text-blue-200 hover:bg-blue-800/80 hover:text-white'
        }}`;
      }});
      updateScoreBadge();
    }}

    function updateScoreBadge() {{
      let score = 0;
      let totalSubmitted = 0;
      questionsData.forEach((q, idx) => {{
        if (submittedState[idx]) {{
          totalSubmitted++;
          if (userAnswers[idx] === q.correct) score++;
        }}
      }});
      document.getElementById('score-badge').innerText = `Score: ${{score}} / ${{questionsData.length}} (${{totalSubmitted}} answered)`;
    }}

    function switchQuestion(idx) {{
      currentIndex = idx;
      renderQuestion(idx);
      updateTabStyles();
    }}

    function prevQuestion() {{
      if (currentIndex > 0) switchQuestion(currentIndex - 1);
    }}

    function nextQuestion() {{
      if (currentIndex < questionsData.length - 1) switchQuestion(currentIndex + 1);
    }}

    function renderQuestion(idx) {{
      const q = questionsData[idx];
      document.getElementById('q-badge').innerText = `Question ${{q.number}} of ${{questionsData.length}}`;
      document.getElementById('current-q-label').innerText = `Question ${{q.number}} of ${{questionsData.length}}`;
      
      // Vignette
      document.getElementById('vignette-text').innerText = q.question;

      // Figure
      const figContainer = document.getElementById('figure-container');
      const figImg = document.getElementById('figure-img');
      if (q.figure_b64) {{
        figImg.src = `data:image/png;base64,${{q.figure_b64}}`;
        figContainer.classList.remove('hidden');
      }} else {{
        figContainer.classList.add('hidden');
      }}

      // Options
      const optContainer = document.getElementById('options-container');
      optContainer.innerHTML = '';
      const letters = Object.keys(q.options).sort();
      
      letters.forEach(letter => {{
        const text = q.options[letter];
        const isSelected = userAnswers[idx] === letter;
        const isSubmitted = submittedState[idx];
        const isCorrect = letter === q.correct;
        
        let borderBgStyle = 'border-slate-200 hover:border-blue-400 hover:bg-blue-50/30 bg-white';
        let radioStyle = 'border-slate-300 text-transparent';
        
        if (isSelected && !isSubmitted) {{
          borderBgStyle = 'border-blue-600 bg-blue-50/50 ring-1 ring-blue-500';
          radioStyle = 'border-blue-600 bg-blue-600 text-white';
        }} else if (isSubmitted) {{
          if (isCorrect) {{
            borderBgStyle = 'border-emerald-500 bg-emerald-50/60 ring-1 ring-emerald-400';
            radioStyle = 'border-emerald-600 bg-emerald-600 text-white';
          }} else if (isSelected && !isCorrect) {{
            borderBgStyle = 'border-rose-400 bg-rose-50/50 ring-1 ring-rose-400';
            radioStyle = 'border-rose-500 bg-rose-500 text-white';
          }} else {{
            borderBgStyle = 'border-slate-200 bg-slate-50/50 opacity-70';
          }}
        }}

        const row = document.createElement('div');
        row.className = `border rounded-xl p-3.5 sm:p-4 cursor-pointer transition flex items-start space-x-3.5 ${{borderBgStyle}}`;
        row.onclick = () => {{
          if (!submittedState[idx]) {{
            userAnswers[idx] = letter;
            renderQuestion(idx);
          }}
        }};

        row.innerHTML = `
          <div class="w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 mt-0.5 transition ${{radioStyle}}">
            <span class="w-2 h-2 rounded-full bg-current"></span>
          </div>
          <div class="flex-1 text-sm font-medium text-slate-800 leading-snug">
            <span class="font-bold text-slate-900 mr-1.5">(${{letter}})</span>
            <span>${{text}}</span>
          </div>
        `;
        optContainer.appendChild(row);
      }});

      // Status pill & button state
      const statusPill = document.getElementById('status-pill');
      const statusDot = document.getElementById('status-dot');
      const statusText = document.getElementById('status-text');
      const submitBtn = document.getElementById('submit-btn');

      if (submittedState[idx]) {{
        submitBtn.classList.add('hidden');
        if (userAnswers[idx] === q.correct) {{
          statusDot.className = 'w-2 h-2 rounded-full bg-emerald-500';
          statusText.innerText = 'Answered Correctly';
          statusText.className = 'text-emerald-700 font-semibold';
        }} else {{
          statusDot.className = 'w-2 h-2 rounded-full bg-rose-500';
          statusText.innerText = 'Answered Incorrectly';
          statusText.className = 'text-rose-700 font-semibold';
        }}
        renderExplanation(q, userAnswers[idx] === q.correct);
      }} else {{
        submitBtn.classList.remove('hidden');
        statusDot.className = userAnswers[idx] ? 'w-2 h-2 rounded-full bg-amber-500' : 'w-2 h-2 rounded-full bg-slate-300';
        statusText.innerText = userAnswers[idx] ? 'Option Selected (Ready)' : 'Unanswered';
        statusText.className = 'text-slate-500 font-medium';
        document.getElementById('explanation-card').classList.add('hidden');
      }}

      // Update Raw PDF Preview
      updateRawPdfView(q);
    }}

    function submitCurrentAnswer() {{
      const q = questionsData[currentIndex];
      if (!userAnswers[currentIndex]) {{
        alert('Please select an option before submitting.');
        return;
      }}
      submittedState[currentIndex] = true;
      renderQuestion(currentIndex);
      updateTabStyles();
    }}

    function toggleExplanation() {{
      const expCard = document.getElementById('explanation-card');
      if (expCard.classList.contains('hidden')) {{
        renderExplanation(questionsData[currentIndex], userAnswers[currentIndex] === questionsData[currentIndex].correct);
      }} else {{
        expCard.classList.add('hidden');
      }}
    }}

    function renderExplanation(q, isCorrect) {{
      const card = document.getElementById('explanation-card');
      card.classList.remove('hidden');

      const banner = document.getElementById('result-banner');
      const iconBox = document.getElementById('result-icon-box');
      const title = document.getElementById('result-title');
      const subtitle = document.getElementById('result-subtitle');

      if (isCorrect) {{
        banner.className = 'px-6 py-4 border-b border-emerald-200 bg-emerald-50/80 flex items-center justify-between';
        iconBox.className = 'w-8 h-8 rounded-full bg-emerald-600 text-white flex items-center justify-center font-bold text-sm';
        iconBox.innerHTML = '&check;';
        title.className = 'text-sm font-bold tracking-tight text-emerald-900';
        title.innerText = 'Correct Answer!';
        subtitle.innerText = `You correctly selected (${{q.correct}}).`;
      }} else {{
        banner.className = 'px-6 py-4 border-b border-rose-200 bg-rose-50/80 flex items-center justify-between';
        iconBox.className = 'w-8 h-8 rounded-full bg-rose-600 text-white flex items-center justify-center font-bold text-sm';
        iconBox.innerHTML = '&times;';
        title.className = 'text-sm font-bold tracking-tight text-rose-900';
        title.innerText = 'Incorrect';
        subtitle.innerText = `You chose (${{userAnswers[currentIndex] || 'None'}}). Correct answer is (${{q.correct}}).`;
      }}

      // Peer summary
      const correctPct = q.peer_stats[q.correct] || 0;
      document.getElementById('correct-pct-summary').innerText = `${{correctPct}}%`;

      // Peer bars
      const peerContainer = document.getElementById('peer-bars-container');
      peerContainer.innerHTML = '';
      const letters = Object.keys(q.options).sort();
      letters.forEach(let => {{
        const pct = q.peer_stats[let] || 0;
        const isThisCorrect = let === q.correct;
        const isUserChoice = userAnswers[currentIndex] === let;
        
        let barColor = isThisCorrect ? 'bg-emerald-500' : 'bg-slate-300';
        if (isUserChoice && !isThisCorrect) barColor = 'bg-rose-400';

        const row = document.createElement('div');
        row.className = 'flex items-center space-x-3 text-xs';
        row.innerHTML = `
          <span class="w-6 font-bold ${{isThisCorrect ? 'text-emerald-700' : 'text-slate-600'}}">(${{let}})</span>
          <div class="flex-1 bg-slate-200/80 rounded-full h-2.5 overflow-hidden">
            <div class="h-full rounded-full transition-all duration-500 ${{barColor}}" style="width: ${{pct}}%"></div>
          </div>
          <span class="w-14 text-right font-mono font-medium ${{isThisCorrect ? 'text-emerald-700 font-bold' : 'text-slate-500'}}">${{pct}}%</span>
        `;
        peerContainer.appendChild(row);
      }});

      // Slide image
      const slideContainer = document.getElementById('slide-container');
      const slideImg = document.getElementById('slide-img');
      const slideBadge = document.getElementById('slide-badge');
      if (q.slide_b64) {{
        slideImg.src = `data:image/png;base64,${{q.slide_b64}}`;
        slideContainer.classList.remove('hidden');
        if (q.v_type === 'lecture_slide_4k') {{
          slideBadge.className = 'text-[10px] bg-indigo-50 text-indigo-700 border border-indigo-200 font-mono px-2 py-0.5 rounded font-semibold flex items-center gap-1';
          slideBadge.innerHTML = '⚡ 4K UHD Master Slide • ' + (q.v_deck || '') + ' (Slide ' + (q.v_slide || '') + ')';
        }} else if (q.v_type === 'regular_medical_figure' || q.v_type === 'regular_medical_image') {{
          slideBadge.className = 'text-[10px] bg-amber-50 text-amber-800 border border-amber-300 font-mono px-2 py-0.5 rounded font-semibold flex items-center gap-1';
          slideBadge.innerHTML = '📊 Clinical Reference Table / Standalone Medical Diagram (Original Source)';
        }} else {{
          slideBadge.className = 'text-[10px] bg-slate-100 text-slate-600 border border-slate-200 font-mono px-2 py-0.5 rounded';
          slideBadge.innerText = 'Lecture Visual';
        }}
      }} else {{
        slideContainer.classList.add('hidden');
      }}

      // Rationale text (format blocks)
      const ratEl = document.getElementById('rationale-text');
      const paragraphs = (q.explanation || '').split('\\n\\n').filter(Boolean);
      ratEl.innerHTML = paragraphs.map(p => {{
        const clean = p.trim();
        if (clean.startsWith('Answer ' + q.correct) || clean.startsWith('Answer (' + q.correct)) {{
          return `<div class="p-4 bg-emerald-50/70 border border-emerald-200 rounded-lg text-slate-800 font-medium">${{clean}}</div>`;
        }} else if (clean.startsWith('Answer')) {{
          return `<div class="p-3.5 bg-slate-50 border border-slate-200 rounded-lg text-slate-700">${{clean}}</div>`;
        }} else {{
          return `<p class="leading-relaxed">${{clean}}</p>`;
        }}
      }}).join('');

      card.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
    }}

    function togglePdfComparison() {{
      pdfComparisonOpen = !pdfComparisonOpen;
      const layout = document.getElementById('main-layout');
      const pdfCol = document.getElementById('pdf-compare-col');
      const btnText = document.getElementById('pdf-toggle-text');

      if (pdfComparisonOpen) {{
        layout.className = 'max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-6 transition-all duration-300';
        pdfCol.classList.remove('hidden');
        btnText.innerText = 'Close PDF Audit';
      }} else {{
        layout.className = 'max-w-7xl mx-auto grid grid-cols-1 gap-6 transition-all duration-300';
        pdfCol.classList.add('hidden');
        btnText.innerText = 'Side-by-Side PDF Audit';
      }}
    }}

    function setPdfTab(tab) {{
      activePdfTab = tab;
      const btnQ = document.getElementById('btn-pdf-q');
      const btnExp = document.getElementById('btn-pdf-exp');
      if (tab === 'question') {{
        btnQ.className = 'text-[11px] px-2.5 py-1 bg-blue-700 rounded font-semibold text-white';
        btnExp.className = 'text-[11px] px-2.5 py-1 bg-blue-950 text-blue-200 rounded hover:text-white font-medium';
      }} else {{
        btnQ.className = 'text-[11px] px-2.5 py-1 bg-blue-950 text-blue-200 rounded hover:text-white font-medium';
        btnExp.className = 'text-[11px] px-2.5 py-1 bg-blue-700 rounded font-semibold text-white';
      }}
      updateRawPdfView(questionsData[currentIndex]);
    }}

    function updateRawPdfView(q) {{
      const img = document.getElementById('raw-pdf-img');
      img.src = activePdfTab === 'question' 
        ? `data:image/png;base64,${{q.raw_q_b64}}` 
        : `data:image/png;base64,${{q.raw_exp_b64}}`;
    }}

    window.onload = init;
  </script>
</body>
</html>
"""

# Write to artifact directory and local project
ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
ARTIFACT_PATH.write_text(html_content, encoding="utf-8")
LOCAL_PATH.write_text(html_content, encoding="utf-8")

print(f"Generated standalone web runner HTML preview at:")
print(f"  Artifact: {ARTIFACT_PATH} ({ARTIFACT_PATH.stat().st_size / 1024:.1f} KB)")
print(f"  Local:    {LOCAL_PATH} ({LOCAL_PATH.stat().st_size / 1024:.1f} KB)")
