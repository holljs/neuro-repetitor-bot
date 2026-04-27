// ЖЕЛЕЗОБЕТОННАЯ ФИКСАЦИЯ ПАРАМЕТРОВ ВК
const VK_SEARCH_PARAMS = window.location.search || window.location.hash.replace('#', '?'); 

const API_SERVER_URL = "https://neuro-master.online";
const TEST_API_URL = "https://neuro-master.online/repetitor-api"; 

// Экраны приложения
const loadingScreen = document.getElementById('screen-loading');
const mainMenuScreen = document.getElementById('screen-main-menu');
const subjectScreen = document.getElementById('screen-subjects');
const taskScreen = document.getElementById('task-screen');
const quickResultScreen = document.getElementById('quick-result-screen');
const testFinishScreen = document.getElementById('test-finish-screen');
const reviewScreen = document.getElementById('review-screen');
const helpScreen = document.getElementById('screen-help');

// --- ТОЧНОЕ ОПРЕДЕЛЕНИЕ ПЛАТФОРМЫ ВК ---
const urlParams = new URLSearchParams(VK_SEARCH_PARAMS);
const vkPlatform = urlParams.get('vk_platform') || 'desktop_web';
const allowedPaymentPlatforms = ['desktop_web', 'mobile_web'];
const canPay = allowedPaymentPlatforms.includes(vkPlatform);

let USER_ID = urlParams.get('vk_user_id');
let currentExamType = null; 

// --- СОБСТВЕННАЯ СИСТЕМА УВЕДОМЛЕНИЙ (БЕЗ ALERT) ---
window.showCustomAlert = function(message, title = "Внимание") {
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-message').textContent = message;
    document.getElementById('custom-modal').style.display = 'flex';
}

window.closeModal = function() {
    document.getElementById('custom-modal').style.display = 'none';
}

function renderMath(elementId) {
    const el = document.getElementById(elementId);
    if (el && window.renderMathInElement) {
        renderMathInElement(el, {
            delimiters: [
                {left: '$$', right: '$$', display: true}, 
                {left: '$', right: '$', display: false},  
                {left: '\\(', right: '\\)', display: false},
                {left: '\\[', right: '\\]', display: true}
            ],
            throwOnError: false 
        });
    }
}

const OGE_SUBJECTS = { 
    "oge_math": "Математика ОГЭ", "oge_russian": "Русский язык ОГЭ", 
    "oge_english": "Английский ОГЭ", "oge_chemistry": "Химия ОГЭ",
    "oge_physics": "Физика ОГЭ", "oge_geography": "География ОГЭ",
    "oge_biology": "Биология ОГЭ", "oge_informatics": "Информатика ОГЭ",
    "oge_history": "История ОГЭ", "oge_social": "Обществознание ОГЭ"
};

const EGE_SUBJECTS = { 
    "math_ege": "Математика (профиль)", "russian_ege": "Русский язык ЕГЭ",
    "inf_ege": "Информатика ЕГЭ", "geo_ege": "География ЕГЭ",
    "phys_ege": "Физика ЕГЭ", "ege_english": "Английский ЕГЭ",
    "chem_ege": "Химия ЕГЭ", "ege_literature": "Литература ЕГЭ"
};

const ALL_SUBJECTS = { ...OGE_SUBJECTS, ...EGE_SUBJECTS };

const TEST_LENGTH = 15;
let currentTask = null;
let currentSubjectCode = null;
let questionNumber = 1;
let score = 0;
let mistakes = []; 
let currentReviewIndex = 0;
let currentTestMode = "standard";

function showScreen(screenElement) {
    document.querySelectorAll('.screen').forEach(s => { if(s) s.style.display = 'none'; });
    if(screenElement) {
        screenElement.style.display = 'block';
        if (window.feather) feather.replace();
    }
}

function startApp() {
    showScreen(mainMenuScreen);
    vkBridge.send('VKWebAppInit');
    vkBridge.send('VKWebAppGetUserInfo')
        .then(userData => {
            if (!USER_ID) USER_ID = userData.id;
        })
        .catch(error => console.log("ВК не отдал профиль", error));
}

window.openSubjects = function(examType) {
    currentExamType = examType;
    const subjects = (examType === 'ege') ? EGE_SUBJECTS : OGE_SUBJECTS;
    subjectScreen.innerHTML = `<h1>Выберите предмет</h1>`;
    
    for (const code in subjects) {
        const btn = document.createElement('button');
        btn.className = 'button';
        btn.innerText = subjects[code];
        btn.onclick = () => selectTariff(code, subjects[code]); 
        subjectScreen.appendChild(btn);
    }
    
    const backBtn = document.createElement('button');
    backBtn.className = 'button secondary';
    backBtn.style.marginTop = '20px';
    backBtn.innerText = '🔙 В главное меню';
    backBtn.onclick = () => showScreen(mainMenuScreen);
    subjectScreen.appendChild(backBtn);
    showScreen(subjectScreen);
}

document.querySelectorAll('#screen-main-menu .button').forEach(button => {
    button.addEventListener('click', () => {
        if (button.dataset.examType) openSubjects(button.dataset.examType);
    });
});

window.selectTariff = function(subjectCode, subjectName) {
    subjectScreen.innerHTML = `
        <h2>${subjectName}</h2>
        <p style="text-align:center; color:#555; margin-bottom:20px;">Выберите формат тренировки:</p>

        <div style="margin-bottom: 10px;">
            <button class="button" style="background-color: #4a76a8; justify-content: space-between; padding-right: 15px;" onclick="startTest('${subjectCode}', 'standard')">
                <div style="display: flex; align-items: center;">
                    <i data-feather="play-circle" class="icon-sm"></i> Стандарт (3 кредита)
                </div>
                <div onclick="event.stopPropagation(); toggleHint('hint-standard')" style="padding: 5px; margin: -5px; cursor: pointer;">
                    <i data-feather="help-circle" class="icon-sm" style="margin: 0; opacity: 0.8;"></i>
                </div>
            </button>
            
            <div id="hint-standard" class="math-hint-box" style="margin-top: 8px;">
                <b>Стандарт:</b> Нейросеть даёт одно чёткое и понятное объяснение вашей ошибки. Идеально для быстрой тренировки.
            </div>
        </div>

        <div style="margin-bottom: 20px;">
            <button class="button" style="background-color: #2a5885; justify-content: space-between; padding-right: 15px;" onclick="startTest('${subjectCode}', 'pro')">
                <div style="display: flex; align-items: center;">
                    <i data-feather="zap" class="icon-sm"></i> Профи (4 кредита)
                </div>
                <div onclick="event.stopPropagation(); toggleHint('hint-pro')" style="padding: 5px; margin: -5px; cursor: pointer;">
                    <i data-feather="help-circle" class="icon-sm" style="margin: 0; opacity: 0.8;"></i>
                </div>
            </button>
            
            <div id="hint-pro" class="math-hint-box" style="margin-top: 8px;">
                <b>Профи:</b> Глубокий разбор. Если вы не поняли с первого раза, ИИ разжуёт ошибку повторно — ещё проще и детальнее.
            </div>
        </div>

        <button class="button secondary" onclick="openSubjects(currentExamType)">
            <i data-feather="arrow-left" class="icon-sm"></i> Назад к предметам
        </button>
    `;
    if (window.feather) feather.replace(); 
}

window.toggleHint = function(id) {
    const hint = document.getElementById(id);
    if (hint) {
        hint.style.display = hint.style.display === 'block' ? 'none' : 'block';
    }
}

window.startTest = async function(subjectCode, mode) {
    currentTestMode = mode;
    showScreen(loadingScreen);
    try {
        const payResponse = await fetch(`${TEST_API_URL}/start_test_payment/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                student_id: String(USER_ID || 'guest'), 
                test_mode: currentTestMode,
                vk_params: VK_SEARCH_PARAMS
            })
        });
        const payResult = await payResponse.json();
        
        if (payResult.success) {
            currentSubjectCode = subjectCode;
            questionNumber = 1; score = 0; mistakes = [];
            getRandomTask();
        } else { 
            showCustomAlert(payResult.error || "Недостаточно кредитов", "Ошибка"); 
            showScreen(mainMenuScreen); 
        }
    } catch (e) { 
        showCustomAlert("Ошибка соединения с сервером.", "Ошибка");
        showScreen(mainMenuScreen); 
    }
}

async function getRandomTask() {
    try {
        const response = await fetch(`${TEST_API_URL}/random_task/?exam_type=${currentSubjectCode}&student_id=${USER_ID || 'guest'}&vk_params=${encodeURIComponent(VK_SEARCH_PARAMS)}`);
        currentTask = await response.json();
        if (currentTask.done) { 
            showCustomAlert(currentTask.text, "Ура!"); 
            showScreen(mainMenuScreen); 
            return; 
        }
        showTask();
    } catch (e) { 
        showCustomAlert("Ошибка при загрузке задачи.", "Ошибка");
        showScreen(mainMenuScreen); 
    }
}

function showTask() {
    document.getElementById('test-progress').textContent = `Вопрос ${questionNumber} из ${TEST_LENGTH}`;
    const taskTextElement = document.getElementById('task-text');
    const imageContainer = document.getElementById('task-image-container');

    let rawText = currentTask.task_text || currentTask.text || "";
    if (!rawText && currentTask.number) { rawText = "Задание №" + currentTask.number; }

    if (rawText) {
        let cleanText = rawText;
        if (currentSubjectCode === 'oge_math' || currentSubjectCode === 'math_ege') {
            cleanText = cleanText.replace(/Решите уравнения/gi, '').replace(/Решите уравнение/gi, '').replace(/^\d+[\.\)]\s*/, '').trim();
        }
        taskTextElement.innerHTML = `<div style="font-size: 1.1em; line-height: 1.5;">${cleanText}</div>`;
        taskTextElement.style.display = 'block';
    } else {
        taskTextElement.textContent = "Текст задачи не найден";
    }

    if (currentTask.image && currentTask.image.length > 5) {
        const fullImgUrl = currentTask.image.startsWith('http') ? currentTask.image : `https://neuro-master.online/${currentTask.image}`;
        imageContainer.innerHTML = `<img src="${encodeURI(fullImgUrl)}" class="question-image" style="width:100%; border-radius:8px;">`;
        imageContainer.style.display = 'block';
    } else {
        imageContainer.style.display = 'none';
    }
    
    document.getElementById('user-answer').value = '';
    setTimeout(() => { renderMath('task-text'); }, 100);
    showScreen(taskScreen);
}

function normalizeText(str) {
    if (!str) return "";
    return str.toString().replace(/[\u2012\u2013\u2014\u2212]/g, '-').replace(',', '.').replace(/\s+/g, '').trim().toLowerCase();
}

// --- ИЗМЕНЕНИЕ ДЛЯ ЗАЩИТЫ ОТ СЛИВА ОТВЕТОВ ---
window.submitAnswer = async function() {
    let rawInput = document.getElementById('user-answer').value;
    let userAnswer = normalizeText(rawInput);
    if (!userAnswer) {
        showCustomAlert("Пожалуйста, введите ответ!", "Внимание");
        return;
    }
    showScreen(loadingScreen);
    try {
        const response = await fetch(`${TEST_API_URL}/check/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                user_answer: userAnswer, 
                task_id: currentTask.id, 
                student_id: String(USER_ID || 'guest'),
                vk_params: VK_SEARCH_PARAMS
            })
        });
        const result = await response.json();
        
        // Сервер вернул правильный ответ после проверки
        if (result.correct_was) {
            currentTask.answer = result.correct_was; 
        }

        handleQuickResult(result.is_correct, rawInput); 
    } catch (error) { 
        showCustomAlert("Ошибка при проверке ответа.", "Ошибка");
        showScreen(taskScreen); 
    }
}

function handleQuickResult(isCorrect, userAnswer) {
    const titleEl = document.getElementById('quick-result-title');
    const normUser = normalizeText(userAnswer);
    const normCorrect = normalizeText(currentTask.answer);
    const finalCorrect = isCorrect || (normUser === normCorrect);
    
    if (finalCorrect) {
        titleEl.innerHTML = '<div style="color:#4CAF50; display:flex; justify-content:center; align-items:center;"><i data-feather="check-circle" style="margin-right:8px;"></i> Верно!</div>';
        score++;
    } else {
        titleEl.innerHTML = `<div style="color:#ff5252; display:flex; justify-content:center; align-items:center;"><i data-feather="x-circle" style="margin-right:8px;"></i> Неверно!</div><br><small style="color:#555;">Ожидалось: <b>${currentTask.answer || "---"}</b></small>`;
        mistakes.push({ task: currentTask, user_answer: userAnswer });
    }
    setTimeout(() => { feather.replace(); renderMath('quick-result-screen'); }, 100);
    showScreen(quickResultScreen);
}

// --- НОВАЯ ФУНКЦИЯ ПРЕРЫВАНИЯ ТЕСТА ---
window.abortTest = function() {
    if (confirm("Вы уверены, что хотите прервать тренировку? Прогресс этого теста не сохранится.")) {
        showScreen(mainMenuScreen);
    }
}

window.nextTask = function() {
    questionNumber++;
    if (questionNumber <= TEST_LENGTH) getRandomTask();
    else showFinishScreen();
}

function showFinishScreen() {
    document.getElementById('final-score').textContent = score;
    document.getElementById('final-mistakes').textContent = mistakes.length;
    
    const reviewBtnBlock = document.getElementById('review-buttons');
    const oldStats = document.getElementById('topic-stats');
    if (oldStats) oldStats.remove();

    if (mistakes.length > 0) {
        reviewBtnBlock.style.display = 'block';
        const aiAnalysisBlock = `
            <div id="topic-stats" style="margin-top:20px; text-align:left; background:#f0f8ff; padding:15px; border-radius:10px; border: 1px solid #bcdcff;">
                <h3 style="margin-top:0; color:#0056b3; display:flex; align-items:center;"><i data-feather="activity" class="icon-sm"></i> Умный анализ пробелов</h3>
                <p id="ai-analysis-text" style="font-size:14px; color:#333;">Хочешь узнать, какие конкретно темы и правила тебе нужно подтянуть на основе твоих ошибок?</p>
                <button id="ai-analysis-btn" class="button" style="background-color:#007bff; padding:10px; font-size:14px;" onclick="getAIAnalysis()">
                    <i data-feather="cpu" class="icon-sm"></i> Сгенерировать ИИ-анализ
                </button>
            </div>
        `;
        reviewBtnBlock.insertAdjacentHTML('beforebegin', aiAnalysisBlock);
    } else { 
        reviewBtnBlock.style.display = 'none'; 
    }
    showScreen(testFinishScreen);
}

window.getAIAnalysis = async function() {
    const btn = document.getElementById('ai-analysis-btn');
    const textBox = document.getElementById('ai-analysis-text');
    btn.style.display = 'none';
    
    textBox.innerHTML = `<div style="display:flex; align-items:center; color:#555;"><div class="spinner" style="width:16px; height:16px; border-width:2px; margin: 0 10px 0 0;"></div> <i>ИИ анализирует ошибки...</i></div>`;

    const mistakesData = mistakes.map(m => ({
        task_text: String(m.task.task_text || m.task.text || "Текст не найден"),
        user_answer: String(m.user_answer || ""),
        correct_answer: String(m.task.answer || "")
    }));

    try {
        const response = await fetch(`${TEST_API_URL}/analyze_gaps/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                mistakes: mistakesData,
                student_id: String(USER_ID || 'guest'),
                vk_params: VK_SEARCH_PARAMS
            })
        });
        const result = await response.json();
        textBox.innerHTML = `<div style="line-height: 1.5;">${result.analysis}</div>`;
    } catch (error) {
        textBox.innerHTML = `<div style="color:#d32f2f; display:flex; align-items:center;"><i data-feather="alert-triangle" class="icon-sm"></i> Ошибка соединения с сервером.</div>`;
        if (window.feather) feather.replace();
        btn.style.display = 'block';
    }
}

window.startReview = function() { currentReviewIndex = 0; loadReviewForCurrentMistake(); }

function loadReviewForCurrentMistake() {
    const mistake = mistakes[currentReviewIndex];
    document.getElementById('review-progress').textContent = `Разбор ошибки ${currentReviewIndex + 1}`;
    
    document.getElementById('review-answers-block').innerHTML = `
        <p style="display:flex; align-items:center; color:#d32f2f; font-weight:500;"><i data-feather="x-
