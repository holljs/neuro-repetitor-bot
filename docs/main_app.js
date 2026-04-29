const VK_SEARCH_PARAMS = window.location.search || window.location.hash.replace('#', '?'); 
const API_SERVER_URL = "https://neuro-master.online";
const TEST_API_URL = "https://neuro-master.online/repetitor-api"; 

// Переменные объявляем, но пока НЕ ИЩЕМ в HTML
let loadingScreen, mainMenuScreen, subjectScreen, taskScreen, quickResultScreen, testFinishScreen, reviewScreen, helpScreen;

const urlParams = new URLSearchParams(VK_SEARCH_PARAMS);
const vkPlatform = urlParams.get('vk_platform') || 'desktop_web';
const canPay = ['desktop_web', 'mobile_web'].includes(vkPlatform);

let USER_ID = urlParams.get('vk_user_id');
let currentExamType = null; 

window.showCustomAlert = function(message, title = "Внимание") {
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-message').innerHTML = message;
    document.getElementById('custom-modal').style.display = 'flex';
};

window.closeModal = function() { document.getElementById('custom-modal').style.display = 'none'; };

function renderMath(elementId) {
    const el = document.getElementById(elementId);
    if (el && window.renderMathInElement) {
        renderMathInElement(el, { delimiters: [{left: '$$', right: '$$', display: true}, {left: '$', right: '$', display: false}], throwOnError: false });
    }
}

const OGE_SUBJECTS = { "oge_math": "Математика ОГЭ", "oge_russian": "Русский язык ОГЭ", "oge_informatics": "Информатика ОГЭ", "oge_history": "История ОГЭ", "oge_social": "Обществознание ОГЭ", "oge_geography": "География ОГЭ", "oge_physics": "Физика ОГЭ", "oge_chemistry": "Химия ОГЭ", "oge_biology": "Биология ОГЭ", "oge_english": "Английский ОГЭ" };
const EGE_SUBJECTS = { "math_ege": "Математика (профиль)", "russian_ege": "Русский язык ЕГЭ", "inf_ege": "Информатика ЕГЭ", "geo_ege": "География ЕГЭ", "phys_ege": "Физика ЕГЭ", "chem_ege": "Химия ЕГЭ", "ege_english": "Английский ЕГЭ", "ege_literature": "Литература ЕГЭ" };
const ALL_SUBJECTS = { ...OGE_SUBJECTS, ...EGE_SUBJECTS };

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
    if(window.feather) feather.replace();
};

const TEST_LENGTH = 15;
let currentTask = null; let currentSubjectCode = null;
let questionNumber = 1; let score = 0; let mistakes = []; 
let currentReviewIndex = 0; let currentTestMode = "standard";

function saveSession() {
    if (!currentTask) return;
    try { 
        localStorage.setItem('active_test', JSON.stringify({ currentTask, currentSubjectCode, questionNumber, score, mistakes, currentTestMode }));
    } catch(e) {}
}

function restoreSession() {
    try {
        const saved = localStorage.getItem('active_test');
        if (saved) {
            const data = JSON.parse(saved);
            currentTask = data.currentTask; currentSubjectCode = data.currentSubjectCode;
            questionNumber = data.questionNumber; score = data.score; mistakes = data.mistakes; currentTestMode = data.currentTestMode;
            showTask(); return true;
        }
    } catch(e) { 
        try { localStorage.removeItem('active_test'); } catch(err){}
    }
    return false;
}

function showScreen(screenElement) {
    document.querySelectorAll('.screen').forEach(s => { if(s) s.style.display = 'none'; });
    if(screenElement) { screenElement.style.display = 'block'; if(window.feather) feather.replace(); }
}

let isAppInitialized = false;

function finalizeInit() {
    if (isAppInitialized) return;
    isAppInitialized = true;
    
    try {
        if (!restoreSession()) { showScreen(mainMenuScreen); }
    } catch(e) { showScreen(mainMenuScreen); }

    try {
        vkBridge.send('VKWebAppGetUserInfo')
            .then(userData => { if (userData && userData.id) USER_ID = userData.id; })
            .catch(error => console.log("ВК не отдал профиль", error));
    } catch(e) {}
}

// ЭТУ ФУНКЦИЮ МЫ ВЫЗОВЕМ ТОЛЬКО КОГДА HTML ГОТОВ
function startApp() {
    // 1. Ищем экраны ТОЛЬКО сейчас, чтобы не было ошибки null
    loadingScreen = document.getElementById('screen-loading');
    mainMenuScreen = document.getElementById('screen-main-menu');
    subjectScreen = document.getElementById('screen-subjects');
    taskScreen = document.getElementById('task-screen');
    quickResultScreen = document.getElementById('quick-result-screen');
    testFinishScreen = document.getElementById('test-finish-screen');
    reviewScreen = document.getElementById('review-screen');
    helpScreen = document.getElementById('screen-help');

    // 2. Показываем меню
    showScreen(mainMenuScreen);

    // 3. Дергаем ВК
    vkBridge.send('VKWebAppInit')
        .then(() => finalizeInit())
        .catch(() => console.log("VK Bridge Promise не сработал"));

    vkBridge.subscribe((e) => {
        if (e.detail.type === 'VKWebAppUpdateConfig') finalizeInit();
    });

    setTimeout(() => { if (!isAppInitialized) finalizeInit(); }, 1500);
}

window.openSubjects = function(examType) {
    currentExamType = examType;
    const subjects = (examType === 'ege') ? EGE_SUBJECTS : OGE_SUBJECTS;
    subjectScreen.innerHTML = `<h1>Выберите предмет</h1>`;
    for (const code in subjects) {
        const btn = document.createElement('button'); btn.className = 'button'; btn.innerText = subjects[code];
        btn.onclick = () => selectTariff(code, subjects[code]); subjectScreen.appendChild(btn);
    }
    const backBtn = document.createElement('button'); backBtn.className = 'button secondary'; backBtn.style.marginTop = '20px';
    backBtn.innerText = '🔙 В главное меню'; backBtn.onclick = () => showScreen(mainMenuScreen);
    subjectScreen.appendChild(backBtn); showScreen(subjectScreen);
};

document.querySelectorAll('#screen-main-menu .button').forEach(button => {
    button.addEventListener('click', () => { if (button.dataset.examType) openSubjects(button.dataset.examType); });
});

window.selectTariff = function(subjectCode, subjectName) {
    subjectScreen.innerHTML = `
        <h2>${subjectName}</h2>
        <div style="margin-bottom: 10px;"><button class="button" style="background-color: #4a76a8;" onclick="startTest('${subjectCode}', 'standard')"><i data-feather="play-circle" class="icon-sm"></i> Стандарт (3 кредита)</button></div>
        <div style="margin-bottom: 20px;"><button class="button" style="background-color: #2a5885;" onclick="startTest('${subjectCode}', 'pro')"><i data-feather="zap" class="icon-sm"></i> Профи (4 кредита)</button></div>
        <button class="button secondary" onclick="openSubjects(currentExamType)"><i data-feather="arrow-left" class="icon-sm"></i> Назад к предметам</button>
    `;
    if (window.feather) feather.replace(); 
};

window.startTest = async function(subjectCode, mode) {
    currentTestMode = mode; showScreen(loadingScreen);
    try {
        const payResponse = await fetch(`${TEST_API_URL}/start_test_payment/`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ student_id: String(USER_ID || 'guest'), test_mode: currentTestMode, vk_params: VK_SEARCH_PARAMS })
        });
        const payResult = await payResponse.json();
        if (payResult.success) {
            currentSubjectCode = subjectCode; questionNumber = 1; score = 0; mistakes = []; getRandomTask();
        } else { showCustomAlert(payResult.error || "Недостаточно кредитов", "Ошибка"); showScreen(mainMenuScreen); }
    } catch (e) { showCustomAlert("Ошибка соединения с сервером.", "Ошибка"); showScreen(mainMenuScreen); }
};

async function getRandomTask() {
    try {
        const response = await fetch(`${TEST_API_URL}/random_task/?exam_type=${currentSubjectCode}&student_id=${USER_ID || 'guest'}&vk_params=${encodeURIComponent(VK_SEARCH_PARAMS)}`);
        currentTask = await response.json();
        if (currentTask.done) { 
            try { localStorage.removeItem('active_test'); } catch(e){}
            showCustomAlert(currentTask.text, "Ура!"); showScreen(mainMenuScreen); return; 
        }
        showTask();
    } catch (e) { showCustomAlert("Ошибка при загрузке задачи.", "Ошибка"); showScreen(mainMenuScreen); }
}

function showTask() {
    saveSession();
    document.getElementById('test-progress').textContent = `Вопрос ${questionNumber} из ${TEST_LENGTH}`;
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
        imageContainer.innerHTML = `<img src="${encodeURI(fullImgUrl)}" class="question-image" style="width:100%; border-radius:8px;">`;
        imageContainer.style.display = 'block';
    } else { imageContainer.style.display = 'none'; }
    
    const answerBlock = document.querySelector('.answer-block');
    answerBlock.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
            <p class="hint" style="margin: 0; font-size:12px; color:#888;">* Формулы, слова. Цифры пишите по возрастанию.</p>
        </div>
        <input type="text" id="user-answer" placeholder="Введите ответ...">
    `;

    setTimeout(() => { renderMath('task-text'); }, 100); showScreen(taskScreen);
}

function normalizeText(str) {
    if (!str) return "";
    return str.toString().replace(/[\u2012\u2013\u2014\u2212]/g, '-').replace(',', '.').replace(/\s+/g, '').trim().toLowerCase();
}

window.submitAnswer = async function() {
    let rawInput = document.getElementById('user-answer').value;
    let userAnswer = normalizeText(rawInput);
    if (!userAnswer) { showCustomAlert("Пожалуйста, введите ответ!", "Внимание"); return; }
    showScreen(loadingScreen);
    try {
        const response = await fetch(`${TEST_API_URL}/check/`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_answer: userAnswer, task_id: currentTask.id, student_id: String(USER_ID || 'guest'), vk_params: VK_SEARCH_PARAMS })
        });
        const result = await response.json();
        if (result.correct_was) currentTask.answer = result.correct_was; 
        handleQuickResult(result.is_correct, rawInput); 
    } catch (error) { showCustomAlert("Ошибка при проверке ответа.", "Ошибка"); showScreen(taskScreen); }
};

function handleQuickResult(isCorrect, userAnswer) {
    const titleEl = document.getElementById('quick-result-title');
    if (isCorrect || normalizeText(userAnswer) === normalizeText(currentTask.answer)) {
        titleEl.innerHTML = '<div style="color:#4CAF50;"><i data-feather="check-circle"></i> Верно!</div>'; score++;
    } else {
        titleEl.innerHTML = `<div style="color:#ff5252;"><i data-feather="x-circle"></i> Неверно!</div><br><small style="color:#555;">Ожидалось: <b>${currentTask.answer || "---"}</b></small>`;
        mistakes.push({ task: currentTask, user_answer: userAnswer });
    }
    saveSession(); setTimeout(() => { if(window.feather) feather.replace(); renderMath('quick-result-screen'); }, 100); showScreen(quickResultScreen);
}

window.abortTest = function() {
    document.getElementById('modal-title').textContent = "Прервать тест?";
    document.getElementById('modal-message').innerHTML = "Вы уверены? <br><b style='color:#ff5252;'>Прогресс будет утерян, кредиты не возвращаются.</b>";
    const modal = document.getElementById('custom-modal');
    const originalBtn = modal.querySelector('button'); originalBtn.style.display = 'none';

    const btnGroup = document.createElement('div'); btnGroup.id = 'temp-confirm-btns';
    btnGroup.innerHTML = `<button class="button" style="background:#ff5252; margin-bottom:10px; width:100%" id="btn-yes">Да, прервать</button><button class="button secondary" style="width:100%" id="btn-no">Отмена</button>`;
    modal.querySelector('div').appendChild(btnGroup);

    document.getElementById('btn-yes').onclick = () => { try { localStorage.removeItem('active_test'); } catch(e){} document.getElementById('temp-confirm-btns').remove(); originalBtn.style.display = 'inline-block'; closeModal(); showScreen(mainMenuScreen); };
    document.getElementById('btn-no').onclick = () => { document.getElementById('temp-confirm-btns').remove(); originalBtn.style.display = 'inline-block'; closeModal(); };
    modal.style.display = 'flex';
};

window.nextTask = function() {
    questionNumber++;
    if (questionNumber <= TEST_LENGTH) getRandomTask(); else { try { localStorage.removeItem('active_test'); } catch(e){} showFinishScreen(); }
};

function showFinishScreen() {
    document.getElementById('final-score').textContent = score; document.getElementById('final-mistakes').textContent = mistakes.length;
    const reviewBtnBlock = document.getElementById('review-buttons');
    const oldStats = document.getElementById('topic-stats');
    if (oldStats) oldStats.remove();

    if (mistakes.length > 0) {
        reviewBtnBlock.style.display = 'block';
        reviewBtnBlock.insertAdjacentHTML('beforebegin', `
            <div id="topic-stats" style="margin-top:20px; text-align:left; background:#f0f8ff; padding:15px; border-radius:10px; border: 1px solid #bcdcff;">
                <h3 style="margin-top:0; color:#0056b3; display:flex; align-items:center;"><i data-feather="activity" class="icon-sm"></i> Умный анализ пробелов</h3>
                <p id="ai-analysis-text" style="font-size:14px; color:#333;">Хочешь узнать, какие конкретно темы и правила тебе нужно подтянуть на основе твоих ошибок?</p>
                <button id="ai-analysis-btn" class="button" style="background-color:#007bff; padding:10px; font-size:14px;" onclick="getAIAnalysis()"><i data-feather="cpu" class="icon-sm"></i> Сгенерировать ИИ-анализ</button>
            </div>
        `);
    } else { reviewBtnBlock.style.display = 'none'; }
    showScreen(testFinishScreen);
}

window.getAIAnalysis = async function() {
    const btn = document.getElementById('ai-analysis-btn'); const textBox = document.getElementById('ai-analysis-text');
    btn.style.display = 'none'; textBox.innerHTML = `<div style="display:flex; align-items:center; color:#555;"><div class="spinner" style="width:16px; height:16px; border-width:2px; margin: 0 10px 0 0;"></div> <i>ИИ анализирует ошибки...</i></div>`;
    const mData = mistakes.map(m => ({ task_text: String(m.task.task_text || m.task.text || ""), user_answer: String(m.user_answer || ""), correct_answer: String(m.task.answer || "") }));
    try {
        const res = await fetch(`${TEST_API_URL}/analyze_gaps/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mistakes: mData, student_id: String(USER_ID || 'guest'), vk_params: VK_SEARCH_PARAMS }) });
        const result = await res.json(); textBox.innerHTML = `<div style="line-height: 1.5;">${result.analysis}</div>`;
    } catch (e) { textBox.innerHTML = `<div style="color:#d32f2f;">Ошибка соединения с сервером.</div>`; btn.style.display = 'block'; }
};

window.startReview = function() { currentReviewIndex = 0; loadReviewForCurrentMistake(); };

function loadReviewForCurrentMistake() {
    const mistake = mistakes[currentReviewIndex]; document.getElementById('review-progress').textContent = `Разбор ошибки ${currentReviewIndex + 1}`;
    document.getElementById('review-answers-block').innerHTML = `<p style="color:#d32f2f; font-weight:500;"><i data-feather="x-circle" class="icon-sm"></i> Твой: ${mistake.user_answer}</p><p style="color:#388e3c; font-weight:500;"><i data-feather="check-circle" class="icon-sm"></i> Правильный: ${mistake.task.answer}</p>`;
    const reviewImgContainer = document.getElementById('review-image-container');
    if (mistake.task.image && mistake.task.image.length > 5) {
        const fullImgUrl = mistake.task.image.startsWith('http') ? mistake.task.image : `https://neuro-master.online/${mistake.task.image}`;
        reviewImgContainer.innerHTML = `<img src="${encodeURI(fullImgUrl)}" class="question-image" style="max-width: 100%;">`;
    } else { reviewImgContainer.innerHTML = `<div style="padding:15px; background:#f9f9f9;">${mistake.task.task_text || mistake.task.text}</div>`; }
    document.getElementById('review-explanation').innerHTML = `<button class="submit-btn" onclick="runAIExplanation()"><i data-feather="cpu" class="icon-sm"></i> Разбор с ИИ</button>`;
    showScreen(reviewScreen);
}

window.runAIExplanation = async function(simplify = false) {
    const mistake = mistakes[currentReviewIndex]; const explanationBox = document.getElementById('review-explanation');
    explanationBox.innerHTML = `<div style="display:flex; align-items:center; color:#555;"><div class="spinner" style="width:16px; height:16px; border-width:2px; margin: 0 10px 0 0;"></div> <i>Генерирую...</i></div>`;
    try {
        const res = await fetch(`${TEST_API_URL}/review/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_answer: String(mistake.user_answer), image_url: mistake.task.image ? `https://neuro-master.online/${mistake.task.image}` : null, task_text: mistake.task.task_text || mistake.task.text, simplify: simplify, student_id: String(USER_ID || 'guest'), vk_params: VK_SEARCH_PARAMS }) });
        const result = await res.json(); explanationBox.innerHTML = `<div style="text-align:left;">${result.explanation}</div>`;
    } catch (e) { explanationBox.innerHTML = `<div style="color:#d32f2f;">Ошибка при генерации разбора.</div>`; }
};

window.nextReview = function() { currentReviewIndex++; if (currentReviewIndex < mistakes.length) loadReviewForCurrentMistake(); else showScreen(mainMenuScreen); };
window.finishSession = () => showScreen(mainMenuScreen);
window.allowVkMessages = function() { vkBridge.send("VKWebAppAllowMessagesFromGroup", {"group_id": 235924452}).then(() => showCustomAlert("Успешно!", "Отлично")).catch(() => showCustomAlert("Отменено", "Отмена")); };

window.buyPackage = async function(creditsAmount) {
    const priceMap = { 15: 150, 100: 700 }; const price = priceMap[creditsAmount]; showScreen(loadingScreen);
    try {
        const res = await fetch(`${TEST_API_URL}/create_payment/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ student_id: String(USER_ID || 'guest'), amount: creditsAmount, price: price, vk_params: VK_SEARCH_PARAMS }) });
        const result = await res.json();
        if (result.success && result.confirmation_url) {
            try { await vkBridge.send("VKWebAppOpenUrl", {"url": result.confirmation_url}); } catch (e) { window.open(result.confirmation_url, '_blank'); }
            showProfile();
        } else { showCustomAlert("Ошибка платежа", "Ошибка"); showProfile(); }
    } catch (e) { showCustomAlert("Ошибка сети", "Ошибка"); showProfile(); }
};

window.handleTopUpClick = function(amount) {
    if (vkPlatform.includes('iphone') || vkPlatform.includes('ipad') || vkPlatform.includes('android')) showCustomAlert("Пополнение временно доступно только с ПК!", "Ограничение");
    else buyPackage(amount);
};

window.showProfile = async function() {
    showScreen(loadingScreen);
    try {
        const res = await fetch(`${TEST_API_URL}/profile_base/?student_id=${USER_ID || 'guest'}&vk_params=${encodeURIComponent(VK_SEARCH_PARAMS)}`);
        if (!res.ok) { showCustomAlert("Ошибка безопасности VK.", "Доступ закрыт"); showScreen(mainMenuScreen); return; }
        const data = await res.json();
        
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
                        <button class="button" style="width:100%; background:#007bff; font-size:14px;" onclick="loadSubjectAnalytics('${subjCode}', '${subjName}')"><i data-feather="cpu" class="icon-sm"></i> Получить ИИ-анализ</button>
                    </div>
                </div>`;
            }
        } else { subjectsHtml = `<p style="color:#777; text-align:center;">Статистика появится после решения заданий!</p>`; }

        subjectScreen.innerHTML = `
            <h2 style="display:flex; align-items:center; justify-content:center; margin-bottom: 20px;"><i data-feather="user" style="margin-right:10px;"></i> Мой профиль</h2>
            <div style="background:white; padding:15px; border-radius:10px; margin-bottom:20px; display:flex; justify-content:space-around; text-align:center; border: 1px solid #e1e3e6;">
                <div><div style="font-size:24px; font-weight:bold; color:#ff9800;">${data.balance || 0}</div><div style="font-size:12px; color:#777; text-transform:uppercase;">кредитов</div></div>
                <div style="width:1px; background:#e1e3e6;"></div>
                <div><div style="font-size:24px; font-weight:bold; color:#4CAF50;">${data.total_solved || 0}</div><div style="font-size:12px; color:#777; text-transform:uppercase;">задач решено</div></div>
            </div>
            <h3 style="text-align:left; margin-bottom:10px; font-size: 16px;">Твои предметы:</h3>
            ${subjectsHtml}
            <div style="background:#fff; padding:15px; border-radius:10px; margin-top:20px; border: 1px solid #e1e3e6;">
                <h3 style="margin-top:0; text-align:center;">Пополнить баланс</h3>
                <button class="button" style="background:#4a76a8; margin-bottom:10px;" onclick="handleTopUpClick(15)">15 кр. — 150 руб.</button>
                <button class="button" style="background:#2a5885;" onclick="handleTopUpClick(100)">100 кр. — 700 руб.</button>
            </div>
            <button class="button secondary" style="margin-top:20px;" onclick="showScreen(mainMenuScreen)">В меню</button>
        `;
        showScreen(subjectScreen);
    } catch (e) { showCustomAlert("Не удалось загрузить профиль.", "Ошибка"); showScreen(mainMenuScreen); }
};

window.loadSubjectAnalytics = async function(c, n) {
    subjectScreen.innerHTML = `<h2>Анализ: ${n}</h2><div id="an-cont"><div class="spinner"></div></div>`;
    try {
        const res = await fetch(`${TEST_API_URL}/analyze_subject/?student_id=${USER_ID || 'guest'}&subject_key=${c}&vk_params=${encodeURIComponent(VK_SEARCH_PARAMS)}`);
        const data = await res.json(); document.getElementById('an-cont').innerHTML = `<div style="text-align:left; line-height:1.6;">${data.analysis}</div><br><button class="button secondary" onclick="showProfile()">Назад</button>`;
    } catch(e) { document.getElementById('an-cont').innerHTML = `<div style="color:red">Ошибка</div><br><button class="button secondary" onclick="showProfile()">Назад</button>`; }
};

window.showHelp = function() {
    try {
        const hp = document.getElementById('help-payment-block'); if (hp) hp.style.display = canPay ? 'block' : 'none'; 
        const hS = document.getElementById('screen-help'); if (hS) showScreen(hS);
    } catch (e) {}
};

document.addEventListener('click', function(e) {
    if (e.target.tagName === 'A' && e.target.href) {
        e.preventDefault(); vkBridge.send("VKWebAppOpenUrl", {"url": e.target.href}).catch(() => { window.open(e.target.href, '_blank'); });
    }
});

// Запуск ТОЛЬКО когда браузер отрисовал HTML
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', startApp);
} else {
    startApp();
}
