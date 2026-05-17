console.log("🚀 [APP] Скрипт main_app.js начал загрузку!");

const VK_SEARCH_PARAMS = window.location.search || window.location.hash.replace('#', '?');
const API_SERVER_URL = "https://neuro-master.online";
const TEST_API_URL = "https://neuro-master.online/repetitor-api";

const urlParams = new URLSearchParams(VK_SEARCH_PARAMS);
let vkPlatform = urlParams.get('vk_platform');
const isMobileDevice = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
const isSmallScreen = window.innerWidth <= 800; 

// Бронебойная защита мобилок для оплат
if ((!vkPlatform && isMobileDevice) || isSmallScreen) {
    vkPlatform = 'mobile_app_forced';
} else if (!vkPlatform) {
    vkPlatform = 'desktop_web';
}
const canPay = vkPlatform === 'desktop_web' && !isMobileDevice && !isSmallScreen;

let USER_ID = urlParams.get('vk_user_id');
console.log("🚀 [APP] USER_ID получен:", USER_ID);

let currentExamType = null;
let currentTask = null;
let currentSubjectCode = null;
let questionNumber = 1;
let score = 0;
let mistakes = [];
let skipsLeft = 3; // <--- НОВАЯ ПЕРЕМЕННАЯ
let currentReviewIndex = 0;
let currentTestMode = "standard";
let isProcessing = false;
let analysisCache = {};

const OGE_SUBJECTS = { "oge_math": "Математика ОГЭ", "oge_russian": "Русский язык ОГЭ", "oge_informatics": "Информатика ОГЭ", "oge_history": "История ОГЭ", "oge_social": "Обществознание ОГЭ", "oge_geography": "География ОГЭ", "oge_physics": "Физика ОГЭ", "oge_chemistry": "Химия ОГЭ", "oge_biology": "Биология ОГЭ", "oge_english": "Английский ОГЭ" };
const EGE_SUBJECTS = { "math_ege": "Математика (профиль)", "russian_ege": "Русский язык ЕГЭ", "inf_ege": "Информатика ЕГЭ", "geo_ege": "География ЕГЭ", "phys_ege": "Физика ЕГЭ", "chem_ege": "Химия ЕГЭ", "ege_english": "Английский ЕГЭ", "ege_literature": "Литература ЕГЭ" };
const ALL_SUBJECTS = { ...OGE_SUBJECTS, ...EGE_SUBJECTS };
const TEST_LENGTH = 15;

function showScreen(screenElement) {
    document.querySelectorAll('.screen').forEach(s => { if(s) s.style.display = 'none'; });
    if(screenElement) {
        if (screenElement.id === 'screen-loading') {
            const loadText = screenElement.querySelector('p');
            if (loadText) loadText.innerText = "Подождите...";
        }
        screenElement.style.display = 'block';
        if (window.feather) feather.replace();
    }
}

window.showCustomAlert = function(message, title = "Внимание") {
    const modal = document.getElementById('custom-modal');
    if (!modal) return;
    document.body.style.overflow = 'hidden';
    
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-message').innerHTML = message;
    
    const tempBtns = document.getElementById('temp-confirm-btns');
    if (tempBtns) tempBtns.remove();
    const originalBtn = modal.querySelector('button');
    if (originalBtn) originalBtn.style.display = 'inline-block';

    modal.style.display = 'flex';
};

window.closeModal = function() {
    document.getElementById('custom-modal').style.display = 'none';
    document.body.style.overflow = '';
}

function renderMath(elementId) {
    const el = document.getElementById(elementId);
    if (el && window.renderMathInElement) {
        try { renderMathInElement(el, { delimiters: [{left: '$$', right: '$$', display: true}, {left: '$', right: '$', display: false}], throwOnError: false }); } catch(e){}
    }
}

window.toggleAccordion = function(element) {
    const body = element.nextElementSibling;
    const icon = element.querySelector('.feather-chevron-down') || element.querySelector('.feather-chevron-up');
    if (body.style.display === 'none' || body.style.display === '') {
        body.style.display = 'block';
        if(icon) icon.setAttribute('data-feather', 'chevron-up');
    } else {
        body.style.display = 'none';
        if(icon) icon.setAttribute('data-feather', 'chevron-down');
    }
    if (window.feather) feather.replace();
};

window.toggleMathHint = function() {
    const hintBox = document.getElementById('math-hint-box');
    if (hintBox) {
        hintBox.style.display = (hintBox.style.display === 'none' || hintBox.style.display === '') ? 'block' : 'none';
    }
};

function saveSession(screenName = 'task-screen', extra = {}) {
    if (!currentTask) return;
    try {
        // СОХРАНЯЕМ КОЛИЧЕСТВО ЗАМЕН
        localStorage.setItem('active_test', JSON.stringify({
            currentTask, currentSubjectCode, questionNumber, score, mistakes, currentTestMode, screenName, extra, currentReviewIndex, skipsLeft
        }));
    } catch(e) {}
}

function initApp() {
    console.log("🚀 [APP] Инициализация интерфейса...");
    
    if (!canPay) {
        document.querySelectorAll('button').forEach(btn => {
            if (btn.innerText.toLowerCase().includes('пополнить')) {
                btn.style.display = 'none';
            }
        });
    }

    try {
        const saved = localStorage.getItem('active_test');
        if (saved) {
            const data = JSON.parse(saved);
            if (data && data.currentTask && data.currentTask.id) {
                currentTask = data.currentTask; currentSubjectCode = data.currentSubjectCode;
                questionNumber = data.questionNumber; score = data.score; mistakes = data.mistakes; currentTestMode = data.currentTestMode;
                if (data.currentReviewIndex !== undefined) currentReviewIndex = data.currentReviewIndex;
                if (data.skipsLeft !== undefined) skipsLeft = data.skipsLeft; else skipsLeft = 3;
                
                if (data.screenName === 'quick-result-screen') {
                    handleQuickResult(data.extra.isCorrect, data.extra.userAnswer, true);
                } else if (data.screenName === 'test-finish-screen') {
                    showFinishScreen(true);
                } else if (data.screenName === 'review-screen') {
                    loadReviewForCurrentMistake(true);
                } else {
                    showTask();
                }
                return;
            }
        }
    } catch(e) { try { localStorage.removeItem('active_test'); } catch(err){} }
    
    showScreen(document.getElementById('screen-main-menu'));
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}

document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden" && document.getElementById('task-screen').style.display === 'block') {
        saveSession('task-screen');
    }
});

window.openSubjects = function(examType) {
    currentExamType = examType;
    const subjects = (examType === 'ege') ? EGE_SUBJECTS : OGE_SUBJECTS;
    const subjectScreen = document.getElementById('screen-subjects');
    subjectScreen.innerHTML = `<h1>Выберите предмет</h1>`;
    for (const code in subjects) {
        const btn = document.createElement('button'); btn.className = 'button'; btn.innerText = subjects[code];
        btn.onclick = () => selectTariff(code, subjects[code]); subjectScreen.appendChild(btn);
    }
    const backBtn = document.createElement('button'); backBtn.className = 'button secondary'; backBtn.style.marginTop = '20px'; backBtn.innerText = '🔙 В главное меню';
    backBtn.onclick = () => showScreen(document.getElementById('screen-main-menu')); subjectScreen.appendChild(backBtn);
    showScreen(subjectScreen);
};

document.querySelectorAll('#screen-main-menu .button').forEach(button => {
    button.addEventListener('click', () => { if (button.dataset.examType) openSubjects(button.dataset.examType); });
});

window.selectTariff = function(subjectCode, subjectName) {
    const subjectScreen = document.getElementById('screen-subjects');
    subjectScreen.innerHTML = `
        <h2>${subjectName}</h2>
        <div style="margin-bottom: 15px;">
            <button class="button" style="background-color: #4a76a8; margin-bottom: 5px;" onclick="startTest('${subjectCode}', 'standard')"><i data-feather="play-circle" class="icon-sm"></i> Стандарт (3 кр.)</button>
            <div style="font-size: 12px; color: #666; line-height: 1.2;">Обычные разборы ошибок от ИИ.</div>
        </div>
        <div style="margin-bottom: 20px;">
            <button class="button" style="background-color: #2a5885; margin-bottom: 5px;" onclick="startTest('${subjectCode}', 'pro')"><i data-feather="zap" class="icon-sm"></i> Профи (4 кр.)</button>
            <div style="font-size: 12px; color: #666; line-height: 1.2;">Максимально подробные разборы ошибок «на пальцах».</div>
        </div>
        <button class="button secondary" onclick="openSubjects(currentExamType)"><i data-feather="arrow-left" class="icon-sm"></i> Назад к предметам</button>
    `;
    if (window.feather) feather.replace();
};

window.startTest = async function(subjectCode, mode) {
    currentTestMode = mode; showScreen(document.getElementById('screen-loading'));
    try {
        const payResponse = await fetch(`${TEST_API_URL}/start_test_payment/`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ student_id: String(USER_ID || 'guest'), test_mode: currentTestMode, vk_params: VK_SEARCH_PARAMS })
        });
        const payResult = await payResponse.json();
        if (payResult.success) {
            currentSubjectCode = subjectCode; questionNumber = 1; score = 0; mistakes = []; skipsLeft = 3; getRandomTask();
        } else { showCustomAlert(payResult.error || "Недостаточно кредитов", "Ошибка"); showScreen(document.getElementById('screen-main-menu')); }
    } catch (e) { showCustomAlert("Ошибка соединения с сервером.", "Ошибка"); showScreen(document.getElementById('screen-main-menu')); }
};

async function getRandomTask() {
    try {
        const response = await fetch(`${TEST_API_URL}/random_task/?exam_type=${currentSubjectCode}&student_id=${USER_ID || 'guest'}&vk_params=${encodeURIComponent(VK_SEARCH_PARAMS)}`);
        currentTask = await response.json();
        if (currentTask.done) {
            try { localStorage.removeItem('active_test'); } catch(e){}
            showCustomAlert(currentTask.text, "Ура!"); showScreen(document.getElementById('screen-main-menu')); return;
        }
        showTask();
    } catch (e) { showCustomAlert("Ошибка при загрузке задачи.", "Ошибка"); showScreen(document.getElementById('screen-main-menu')); }
}

function showTask() {
    saveSession('task-screen');
    document.getElementById('test-progress').textContent = `Вопрос ${questionNumber} из ${TEST_LENGTH}`;
    
    // Обновляем кнопку замены вопроса
    const skipCountEl = document.getElementById('skips-count');
    if (skipCountEl) skipCountEl.textContent = skipsLeft;
    const skipBtn = document.getElementById('skip-task-btn');
    if (skipBtn) {
        if (skipsLeft <= 0) skipBtn.style.opacity = '0.5';
        else skipBtn.style.opacity = '1';
    }

    const taskTextElement = document.getElementById('task-text');
    const imageContainer = document.getElementById('task-image-container');

    let rawText = currentTask.task_text || currentTask.text || "";
    if (rawText) {
        let cleanText = rawText.replace(/Решите уравнения/gi, '').replace(/^\d+[\.\)]\s*/, '').trim();
        taskTextElement.innerHTML = `<div style="font-size: 1.1em; line-height: 1.5;">${cleanText}</div>`;
        taskTextElement.style.display = 'block';
    } else { taskTextElement.textContent = "Текст не найден"; }

    if (currentTask.image && currentTask.image.length > 5) {
        const fullImgUrl = currentTask.image.startsWith('http') ? currentTask.image : `https://neuro-master.online/${currentTask.image}`;
        imageContainer.innerHTML = `<img src="${encodeURI(fullImgUrl)}" class="question-image" style="width:100%; border-radius:8px; cursor:pointer;" onclick="openImageViewer('${encodeURI(fullImgUrl)}')">`;
        imageContainer.style.display = 'block';
    } else { imageContainer.style.display = 'none'; }
    
    document.getElementById('user-answer').value = '';
    setTimeout(() => { renderMath('task-text'); }, 100); showScreen(document.getElementById('task-screen'));
}

// --- НОВЫЙ ФУНКЦИОНАЛ ЗАМЕНЫ ВОПРОСА ---

window.confirmSkipTask = function() {
    if (skipsLeft <= 0) {
        showCustomAlert("У вас закончились замены в этом тесте.", "Лимит исчерпан");
        return;
    }
    
    const modal = document.getElementById('custom-modal');
    document.body.style.overflow = 'hidden';
    document.getElementById('modal-title').textContent = "Заменить вопрос?";
    document.getElementById('modal-message').innerHTML = `Вы можете пропустить этот вопрос, если в нём есть какая-то ошибка (например, отсутствует картинка).<br><br>Осталось замен на этот тест: <b style="color:#0077FF; font-size:18px;">${skipsLeft}</b>`;
    
    const originalBtn = modal.querySelector('button');
    if (originalBtn) originalBtn.style.display = 'none';

    let btnGroup = document.getElementById('temp-confirm-btns');
    if (!btnGroup) {
        btnGroup = document.createElement('div');
        btnGroup.id = 'temp-confirm-btns';
        btnGroup.innerHTML = `<button class="button" style="background:#0077FF; margin-bottom:10px; width:100%" id="btn-yes-skip">Да, заменить</button><button class="button secondary" style="width:100%" id="btn-no-skip">Отмена</button>`;
        modal.querySelector('div').appendChild(btnGroup);
    } else {
        btnGroup.innerHTML = `<button class="button" style="background:#0077FF; margin-bottom:10px; width:100%" id="btn-yes-skip">Да, заменить</button><button class="button secondary" style="width:100%" id="btn-no-skip">Отмена</button>`;
    }

    document.getElementById('btn-yes-skip').onclick = () => {
        btnGroup.remove();
        if (originalBtn) originalBtn.style.display = 'inline-block';
        closeModal();
        executeSkipTask();
    };
    
    document.getElementById('btn-no-skip').onclick = () => {
        btnGroup.remove();
        if (originalBtn) originalBtn.style.display = 'inline-block';
        closeModal();
    };
    
    modal.style.display = 'flex';
};

window.executeSkipTask = async function() {
    skipsLeft--;
    showScreen(document.getElementById('screen-loading'));
    try {
        const response = await fetch(`${TEST_API_URL}/random_task/?exam_type=${currentSubjectCode}&student_id=${USER_ID || 'guest'}&vk_params=${encodeURIComponent(VK_SEARCH_PARAMS)}`);
        const newTask = await response.json();
        if (newTask.done) {
            showCustomAlert("Задачи в базе закончились!", "Упс");
            showScreen(document.getElementById('screen-main-menu'));
            return;
        }
        currentTask = newTask;
        showTask(); 
    } catch (e) { 
        showCustomAlert("Ошибка при загрузке новой задачи.", "Ошибка"); 
        showTask(); 
    }
};

// ----------------------------------------

function normalizeText(str) {
    if (!str) return "";
    let cleaned = str.toString()
        .replace(/[\u2012\u2013\u2014\u2212]/g, '-')
        .replace(',', '.')
        .replace(/[^\w\sа-яА-ЯёЁ\.,\-]/gi, '')
        .replace(/\s+/g, '')
        .trim().toLowerCase();
    return cleaned;
}

window.submitAnswer = async function() {
    let rawInput = document.getElementById('user-answer').value;
    let userAnswer = normalizeText(rawInput);
    if (!userAnswer) { showCustomAlert("Пожалуйста, введите корректный ответ (без эмодзи)!", "Внимание"); return; }
    showScreen(document.getElementById('screen-loading'));
    try {
        const response = await fetch(`${TEST_API_URL}/check/`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_answer: userAnswer, task_id: currentTask.id, student_id: String(USER_ID || 'guest'), vk_params: VK_SEARCH_PARAMS })
        });
        const result = await response.json();
        if (result.correct_was) currentTask.answer = result.correct_was;
        handleQuickResult(result.is_correct, rawInput);
    } catch (error) { showCustomAlert("Ошибка при проверке ответа.", "Ошибка"); showScreen(document.getElementById('task-screen')); }
};

function handleQuickResult(isCorrect, userAnswer, isRestored = false) {
    const titleEl = document.getElementById('quick-result-title');
    let actuallyCorrect = isCorrect || normalizeText(userAnswer) === normalizeText(currentTask.answer);

    if (!isRestored) {
        if (actuallyCorrect) {
            score++;
        } else {
            mistakes.push({ task: currentTask, user_answer: userAnswer });
        }
    }

    if (actuallyCorrect) {
        titleEl.innerHTML = '<div style="color:#4CAF50;"><i data-feather="check-circle"></i> Верно!</div>';
    } else {
        let expectedAns = currentTask.answer || "---";
        if (expectedAns.includes('\\') && !expectedAns.includes('$')) {
            expectedAns = `$${expectedAns}$`;
        }
        titleEl.innerHTML = `<div style="color:#ff5252;"><i data-feather="x-circle"></i> Неверно!</div><br><small style="color:#555;">Ожидалось: <b>${expectedAns}</b></small>`;
    }
    
    if (!isRestored) saveSession('quick-result-screen', { isCorrect: actuallyCorrect, userAnswer });
    setTimeout(() => { if(window.feather) feather.replace(); renderMath('quick-result-screen'); }, 100);
    showScreen(document.getElementById('quick-result-screen'));
}

window.abortTest = function() {
    const modal = document.getElementById('custom-modal');
    if (!modal) return;
    
    document.body.style.overflow = 'hidden';
    document.getElementById('modal-title').textContent = "Прервать тест?";
    document.getElementById('modal-message').innerHTML = "Вы уверены? <br><b style='color:#ff5252;'>Прогресс будет утерян, кредиты не возвращаются.</b>";
    
    const originalBtn = modal.querySelector('button');
    if (originalBtn) originalBtn.style.display = 'none';

    let btnGroup = document.getElementById('temp-confirm-btns');
    if (!btnGroup) {
        btnGroup = document.createElement('div');
        btnGroup.id = 'temp-confirm-btns';
        btnGroup.innerHTML = `<button class="button" style="background:#ff5252; margin-bottom:10px; width:100%" id="btn-yes">Да, прервать</button><button class="button secondary" style="width:100%" id="btn-no">Отмена</button>`;
        modal.querySelector('div').appendChild(btnGroup);
    }

    document.getElementById('btn-yes').onclick = () => {
        currentTask = null;
        try { localStorage.removeItem('active_test'); } catch(e){}
        btnGroup.remove();
        if (originalBtn) originalBtn.style.display = 'inline-block';
        closeModal();
        showScreen(document.getElementById('screen-main-menu'));
    };
    
    document.getElementById('btn-no').onclick = () => {
        btnGroup.remove();
        if (originalBtn) originalBtn.style.display = 'inline-block';
        closeModal();
    };
    
    modal.style.display = 'flex';
};

window.nextTask = function() {
    if (isProcessing) return;
    isProcessing = true;
    
    questionNumber++;
    if (questionNumber <= TEST_LENGTH) {
        getRandomTask().finally(() => { isProcessing = false; });
    } else {
        showFinishScreen();
        isProcessing = false;
    }
};

function showFinishScreen(isRestored = false) {
    document.getElementById('final-score').textContent = score; 
    document.getElementById('final-mistakes').textContent = mistakes.length;
    
    // ОТПРАВЛЯЕМ ТЕБЕ УВЕДОМЛЕНИЕ О ЗАВЕРШЕНИИ (ТОЛЬКО ОДИН РАЗ)
    if (!isRestored) {
        fetch(`${TEST_API_URL}/notify_test_finish/`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({student_id: String(USER_ID || 'guest'), score: score, total: TEST_LENGTH, vk_params: VK_SEARCH_PARAMS})
        }).catch(()=>{});
        
        saveSession('test-finish-screen');
    }

    const reviewBtnBlock = document.getElementById('review-buttons');
    const oldStats = document.getElementById('topic-stats');
    if (oldStats) oldStats.remove();

    if (mistakes.length > 0) {
        reviewBtnBlock.style.display = 'block';
        reviewBtnBlock.insertAdjacentHTML('beforebegin', `
            <div id="topic-stats" style="margin-top:20px; text-align:left; background:#f0f8ff; padding:15px; border-radius:10px; border: 1px solid #bcdcff;">
                <h3 style="margin-top:0; color:#0056b3; display:flex; align-items:center;"><i data-feather="activity" class="icon-sm"></i> Умный анализ пробелов</h3>
                <p id="ai-analysis-text" style="font-size:14px; color:#333;">ИИ проанализирует твои ошибки.</p>
                <button id="ai-analysis-btn" class="button" style="background-color:#007bff; padding:10px; font-size:14px;" onclick="getAIAnalysis()"><i data-feather="cpu" class="icon-sm"></i> Сгенерировать ИИ-анализ</button>
            </div>
        `);
    } else { reviewBtnBlock.style.display = 'none'; }
    
    if (!isRestored) saveSession('test-finish-screen');
    showScreen(document.getElementById('test-finish-screen'));
}

window.getAIAnalysis = async function() {
    const btn = document.getElementById('ai-analysis-btn'); const textBox = document.getElementById('ai-analysis-text');
    btn.style.display = 'none'; textBox.innerHTML = `<div style="display:flex; align-items:center; color:#555;"><div class="spinner" style="width:16px; height:16px; border-width:2px; margin: 0 10px 0 0;"></div> <i>ИИ анализирует...</i></div>`;
    const mData = mistakes.map(m => ({ task_text: String(m.task.task_text || m.task.text || ""), user_answer: String(m.user_answer || ""), correct_answer: String(m.task.answer || "") }));
    try {
        const response = await fetch(`${TEST_API_URL}/analyze_gaps/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mistakes: mData, student_id: String(USER_ID || 'guest'), vk_params: VK_SEARCH_PARAMS }) });
        const result = await response.json(); textBox.innerHTML = `<div style="line-height: 1.5;">${result.analysis}</div>`;
    } catch (error) { textBox.innerHTML = `<div style="color:#d32f2f;">Ошибка соединения с сервером.</div>`; btn.style.display = 'block'; }
};

window.startReview = function() { currentReviewIndex = 0; loadReviewForCurrentMistake(); };

window.prevReview = function() {
    if (currentReviewIndex > 0) {
        currentReviewIndex--;
        loadReviewForCurrentMistake();
    }
};

function loadReviewForCurrentMistake(isRestored = false) {
    const mistake = mistakes[currentReviewIndex]; document.getElementById('review-progress').textContent = `Разбор ошибки ${currentReviewIndex + 1}`;
    
    document.getElementById('review-answers-block').innerHTML = `
        <div style="display:flex; align-items:flex-start; color:#d32f2f; font-weight:500; word-break: break-word; margin-bottom: 5px;">
            <i data-feather="x-circle" class="icon-sm" style="margin-right:5px; flex-shrink:0;"></i> <span>Твой: ${mistake.user_answer}</span>
        </div>
        <div style="display:flex; align-items:flex-start; color:#388e3c; font-weight:500; word-break: break-word;">
            <i data-feather="check-circle" class="icon-sm" style="margin-right:5px; flex-shrink:0;"></i> <span>Правильный: ${mistake.task.answer}</span>
        </div>`;
        
    const reviewImgContainer = document.getElementById('review-image-container');
    if (mistake.task.image && mistake.task.image.length > 5) {
        const fullImgUrl = mistake.task.image.startsWith('http') ? mistake.task.image : `https://neuro-master.online/${mistake.task.image}`;
        reviewImgContainer.innerHTML = `<img src="${encodeURI(fullImgUrl)}" class="question-image" style="max-width: 100%; cursor:pointer;" onclick="openImageViewer('${encodeURI(fullImgUrl)}')">`;
    } else { reviewImgContainer.innerHTML = `<div style="padding:15px; background:#f9f9f9;">${mistake.task.task_text || mistake.task.text}</div>`; }
    
    let navButtons = `<button class="submit-btn" style="margin-bottom:10px;" onclick="runAIExplanation()"><i data-feather="cpu" class="icon-sm"></i> Разбор с ИИ</button><br>`;
    
    navButtons += `<div style="display:flex; justify-content:space-between; gap:10px;">`;
    if (currentReviewIndex > 0) {
        navButtons += `<button class="button secondary" style="flex:1;" onclick="prevReview()">⬅️ Назад</button>`;
    } else {
        navButtons += `<div style="flex:1;"></div>`;
    }
    
    if (currentReviewIndex < mistakes.length - 1) {
        navButtons += `<button class="button" style="flex:1;" onclick="nextReview()">Далее ➡️</button>`;
    } else {
        navButtons += `<button class="button" style="flex:1;" onclick="finishSession()">Завершить 🎉</button>`;
    }
    navButtons += `</div>`;
    
    document.getElementById('review-explanation').innerHTML = navButtons;
    
    if (!isRestored) saveSession('review-screen');
    showScreen(document.getElementById('review-screen'));
}

window.runAIExplanation = async function(simplify = false) {
    const mistake = mistakes[currentReviewIndex]; const explanationBox = document.getElementById('review-explanation');
    
    let navButtons = `<div style="display:flex; justify-content:space-between; gap:10px; margin-top:15px;">`;
    if (currentReviewIndex > 0) navButtons += `<button class="button secondary" style="flex:1;" onclick="prevReview()">⬅️ Назад</button>`;
    else navButtons += `<div style="flex:1;"></div>`;
    if (currentReviewIndex < mistakes.length - 1) navButtons += `<button class="button" style="flex:1;" onclick="nextReview()">Далее ➡️</button>`;
    else navButtons += `<button class="button" style="flex:1;" onclick="finishSession()">Завершить 🎉</button>`;
    navButtons += `</div>`;

    explanationBox.innerHTML = `<div style="display:flex; align-items:center; color:#555; margin-bottom:10px;"><div class="spinner" style="width:16px; height:16px; border-width:2px; margin: 0 10px 0 0;"></div> <i>Генерирую...</i></div>` + navButtons;
    
    let imageUrl = mistake.task.image ? `https://neuro-master.online/${mistake.task.image}` : null;
    try {
        const response = await fetch(`${TEST_API_URL}/review/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_answer: String(mistake.user_answer), image_url: imageUrl, task_text: mistake.task.task_text || mistake.task.text || "Текст", simplify: simplify, student_id: String(USER_ID || 'guest'), vk_params: VK_SEARCH_PARAMS }) });
        const result = await response.json();
        
        let finalHtml = result.explanation;
        if (window.marked) { finalHtml = marked.parse(finalHtml); }
        
        explanationBox.innerHTML = `<div style="text-align:left;">${finalHtml}</div>` + navButtons;
        setTimeout(() => { renderMath('review-explanation'); }, 100);
    } catch (error) { explanationBox.innerHTML = `<div style="color:#d32f2f;">Ошибка при генерации разбора.</div>` + navButtons; }
};

window.nextReview = function() { currentReviewIndex++; if (currentReviewIndex < mistakes.length) loadReviewForCurrentMistake(); else { window.finishSession(); } };

window.finishSession = () => {
    currentTask = null;
    try { localStorage.removeItem('active_test'); } catch(e){}
    showScreen(document.getElementById('screen-main-menu'));
};

window.allowVkMessages = function(btnElement) {
    vkBridge.send("VKWebAppAllowMessagesFromGroup", {"group_id": 235924452})
        .then(async () => {
            try {
                const res = await fetch(`${TEST_API_URL}/reward_subscription/`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({student_id: String(USER_ID || 'guest'), vk_params: VK_SEARCH_PARAMS})
                });
                const data = await res.json();
                
                // БРОНЕБОЙНОЕ СКРЫТИЕ КНОПКИ (даже если юзер нажал 2 раза)
                if (btnElement) {
                    btnElement.style.display = 'none';
                } else {
                    // Резервный вариант: ищем все кнопки с бонусом на экране и убиваем их
                    document.querySelectorAll('button').forEach(b => { 
                        if(b.innerText.includes('кредита') || b.innerText.includes('уведомления')) b.style.display = 'none'; 
                    });
                }

                if(data.success) {
                    showCustomAlert("Вы подписались на уведомления и получили +3 кредита! 🎉", "Отлично!");
                    setTimeout(() => showProfile(), 1500); // Обновляем баланс
                } else {
                    // Пишем честно, если он уже забирал бонус
                    showCustomAlert(data.message || "Вы уже получали бонус за подписку!", "Внимание");
                }
            } catch(e) {
                 showCustomAlert("Вы подписались на уведомления!", "Отлично");
            }
        })
        .catch(() => {});
};

window.buyPackage = function(creditsAmount) {
    if (!USER_ID) { 
        showCustomAlert("Не удалось определить ваш ID ВКонтакте.", "Ошибка"); 
        return; 
    }
    
    // Магия: отправляем пользователя на нашу новую безопасную страницу оплаты на GitHub Pages
    const payUrl = `https://holljs.github.io/vk-image-bot-frontend/pay_repetitor.html?user_id=${USER_ID}`;
    
    window.openVKUrl(payUrl);
};

window.showProfile = async function() {
    showScreen(document.getElementById('screen-loading'));
    try {
        const response = await fetch(`${TEST_API_URL}/profile_base/?student_id=${USER_ID || 'guest'}&vk_params=${encodeURIComponent(VK_SEARCH_PARAMS)}`);
        if (!response.ok) { showCustomAlert("Ошибка VK.", "Доступ закрыт"); showScreen(document.getElementById('screen-main-menu')); return; }
        const data = await response.json();
        
        let subjectsHtml = '';
        if (data.subject_counts && Object.keys(data.subject_counts).length > 0) {
            for (const [subjCode, count] of Object.entries(data.subject_counts)) {
                const subjName = ALL_SUBJECTS[subjCode] || subjCode;
                subjectsHtml += `
                <div style="margin-bottom:10px; border: 1px solid #e1e3e6; border-radius:8px; background: #fff; overflow:hidden;">
                    <div onclick="toggleAccordion(this)" style="padding:15px; display:flex; justify-content:space-between; align-items:center; cursor:pointer; background:#f9f9f9; font-weight:600; color:#333;">
                        <div style="display:flex; align-items:center;"><i data-feather="book" class="icon-sm" style="margin-right:8px; color:#4a76a8;"></i> ${subjName}</div>
                        <div style="display:flex; align-items:center; font-size:14px; color:#666;">Решено: ${count} <i data-feather="chevron-down" class="icon-sm" style="margin-left:5px;"></i></div>
                    </div>
                    <div style="display:none; padding:15px; border-top:1px solid #e1e3e6;">
                        <button class="button" style="width:100%; background:#4a76a8; font-size:14px;" onclick="loadSubjectAnalytics('${subjCode}', '${subjName}')"><i data-feather="cpu" class="icon-sm"></i> Получить ИИ-анализ</button>
                    </div>
                </div>`;
            }
        } else { subjectsHtml = `<p style="color:#777; text-align:center;">Статистика появится после решения заданий!</p>`; }

        let topUpBlock = '';
        if (canPay) {
            topUpBlock = `
            <div style="background:#fff; padding:15px; border-radius:10px; margin-bottom:20px; border: 1px solid #e1e3e6; box-shadow: 0 2px 8px rgba(0,0,0,0.02);">
                <h3 style="margin-top:0; text-align:center; color:#4a76a8; font-size:16px;"><i data-feather="credit-card" class="icon-sm"></i> Пополнить баланс кредитов</h3>
                <button class="button" style="background:#4a76a8; margin-bottom:10px;" onclick="buyPackage(15)">15 кр. — 150 руб.</button>
                <button class="button" style="background:#2a5885;" onclick="buyPackage(100)">100 кр. — 700 руб.</button>
            </div>`;
        }

        // --- УМНАЯ КНОПКА ПОДПИСКИ ---
        let rewardBtnHtml = '';
        if (data.got_reward !== 1) { // Если еще не получал бонус, рисуем кнопку
            rewardBtnHtml = `
            <button class="button" style="background: linear-gradient(135deg, #4a76a8 0%, #2a5885 100%); margin-bottom:20px; font-size:14px; padding:12px; border: none; box-shrink: 0; box-shadow: 0 4px 10px rgba(74, 118, 168, 0.15);" onclick="allowVkMessages(this)">
                <i data-feather="gift" class="icon-sm" style="margin-right:8px;"></i> Получить +3 кредита за подписку
            </button>`;
        }

        const subjectScreen = document.getElementById('screen-profile');
        subjectScreen.innerHTML = `
            <h2 style="display:flex; align-items:center; justify-content:center; margin-bottom: 20px;"><i data-feather="user" style="margin-right:10px;"></i> Мой профиль</h2>
            
            ${rewardBtnHtml}

            <div style="background:white; padding:15px; border-radius:10px; margin-bottom:20px; display:flex; justify-content:space-around; text-align:center; border: 1px solid #e1e3e6;">
                <div><div style="font-size:24px; font-weight:bold; color:#4a76a8;">${data.balance || 0}</div><div style="font-size:12px; color:#777; text-transform:uppercase;">кредитов</div></div>
                <div style="width:1px; background:#e1e3e6;"></div>
                <div><div style="font-size:24px; font-weight:bold; color:#4CAF50;">${data.total_solved || 0}</div><div style="font-size:12px; color:#777; text-transform:uppercase;">задач решено</div></div>
            </div>

            ${topUpBlock}

            <h3 style="text-align:left; margin-bottom:10px; font-size: 16px; color:#333;">Твои предметы:</h3>
            ${subjectsHtml}
            
            <div style="margin-top: 25px; text-align:center; padding-top: 15px; border-top: 1px dashed #ccc; font-size: 11px; color: #888; line-height: 1.4;">
                Самозанятая Селяхова Наталья Викторовна<br>
                ИНН: 502209781184 | Email: holljs@mail.ru
            </div>
            <button class="button secondary" style="margin-top:20px;" onclick="showScreen(document.getElementById('screen-main-menu'))">В меню</button>
        `;
        showScreen(subjectScreen);
    } catch (e) { showCustomAlert("Не удалось загрузить профиль.", "Ошибка сервера"); showScreen(document.getElementById('screen-main-menu')); }
};

window.loadSubjectAnalytics = async function(c, n) {
    const subjectScreen = document.getElementById('screen-profile');
    subjectScreen.innerHTML = `<h2>Анализ: ${n}</h2><div id="an-cont"><div class="spinner"></div></div>`;
    
    if (analysisCache[c]) {
        document.getElementById('an-cont').innerHTML = `<div style="text-align:left; line-height:1.6;">${analysisCache[c]}</div><br><button class="button secondary" onclick="showProfile()">Назад</button>`;
        if (window.feather) feather.replace();
        return;
    }
    
    try {
        const res = await fetch(`${TEST_API_URL}/analyze_subject/?student_id=${USER_ID || 'guest'}&subject_key=${c}&vk_params=${encodeURIComponent(VK_SEARCH_PARAMS)}`);
        const data = await res.json();
        analysisCache[c] = data.analysis;
        document.getElementById('an-cont').innerHTML = `<div style="text-align:left; line-height:1.6;">${data.analysis}</div><br><button class="button secondary" onclick="showProfile()">Назад</button>`;
        if (window.feather) feather.replace();
    } catch(e) { document.getElementById('an-cont').innerHTML = `<div style="color:red">Ошибка</div><br><button class="button secondary" onclick="showProfile()">Назад</button>`; }
};

window.showHelp = function() {
    const helpScreen = document.getElementById('screen-help');
    const payBlock = document.getElementById('help-payment-block');
    if (payBlock) payBlock.style.display = canPay ? 'block' : 'none';
    showScreen(helpScreen);
};

window.openVKUrl = function(url) {
    try {
        vkBridge.send("VKWebAppOpenUrl", {"url": url}).catch(() => { window.open(url, '_blank'); });
    } catch(e) { window.open(url, '_blank'); }
};

// --- ФУНКЦИЯ ДЛЯ УВЕЛИЧЕНИЯ КАРТИНОК ---
window.openImageViewer = function(url) {
    try {
        vkBridge.send("VKWebAppShowImages", { images: [url] })
        .catch(() => { window.open(url, '_blank'); });
    } catch(e) { window.open(url, '_blank'); }
};
