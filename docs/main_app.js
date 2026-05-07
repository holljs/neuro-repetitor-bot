console.log("🚀 [APP] Скрипт запущен!");

const VK_SEARCH_PARAMS = window.location.search || window.location.hash.replace('#', '?'); 
const API_SERVER_URL = "https://neuro-master.online";
const TEST_API_URL = "https://neuro-master.online/repetitor-api"; 

const urlParams = new URLSearchParams(VK_SEARCH_PARAMS);
let vkPlatform = urlParams.get('vk_platform');
const isMobileDevice = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);

// Бронебойная проверка платформы для Apple/Google
if (!vkPlatform && isMobileDevice) {
    vkPlatform = 'mobile_app_forced'; 
} else if (!vkPlatform) {
    vkPlatform = 'desktop_web';
}

const canPay = ['desktop_web', 'mobile_web'].includes(vkPlatform);
let USER_ID = urlParams.get('vk_user_id');

let currentExamType, currentTask, currentSubjectCode, questionNumber = 1, score = 0, mistakes = [], currentReviewIndex = 0, currentTestMode = "standard", isProcessing = false, analysisCache = {};

const OGE_SUBJECTS = { "oge_math": "Математика ОГЭ", "oge_russian": "Русский язык ОГЭ", "oge_informatics": "Информатика ОГЭ", "oge_history": "История ОГЭ", "oge_social": "Обществознание ОГЭ", "oge_geography": "География ОГЭ", "oge_physics": "Физика ОГЭ", "oge_chemistry": "Химия ОГЭ", "oge_biology": "Биология ОГЭ", "oge_english": "Английский ОГЭ" };
const EGE_SUBJECTS = { "math_ege": "Математика (профиль)", "russian_ege": "Русский язык ЕГЭ", "inf_ege": "Информатика ЕГЭ", "geo_ege": "География ЕГЭ", "phys_ege": "Физика ЕГЭ", "chem_ege": "Химия ЕГЭ", "ege_english": "Английский ЕГЭ", "ege_literature": "Литература ЕГЭ" };
const ALL_SUBJECTS = { ...OGE_SUBJECTS, ...EGE_SUBJECTS };
const TEST_LENGTH = 15;

// === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
function showScreen(el) {
    document.querySelectorAll('.screen').forEach(s => s.style.display = 'none');
    if(el) { el.style.display = 'block'; if (window.feather) feather.replace(); }
}

window.showCustomAlert = function(msg, title = "Внимание") {
    const modal = document.getElementById('custom-modal');
    document.body.style.overflow = 'hidden'; 
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-message').innerHTML = msg;
    modal.style.display = 'flex';
};

window.closeModal = function() { 
    document.getElementById('custom-modal').style.display = 'none'; 
    document.body.style.overflow = ''; 
};

function renderMath(elementId) {
    const el = document.getElementById(elementId);
    if (el && window.renderMathInElement) {
        try { renderMathInElement(el, { delimiters: [{left: '$$', right: '$$', display: true}, {left: '$', right: '$', display: false}], throwOnError: false }); } catch(e){}
    }
}

window.toggleAccordion = function(element) {
    const body = element.nextElementSibling;
    body.style.display = (body.style.display === 'none' || body.style.display === '') ? 'block' : 'none';
    if (window.feather) feather.replace();
};

function saveSession(screenName = 'task-screen', extra = {}) {
    if (!currentTask) return;
    try { localStorage.setItem('active_test', JSON.stringify({ currentTask, currentSubjectCode, questionNumber, score, mistakes, currentTestMode, screenName, extra, currentReviewIndex })); } catch(e) {}
}

// === ИНИЦИАЛИЗАЦИЯ ===
function initApp() {
    if (!canPay) {
        document.querySelectorAll('button').forEach(btn => {
            if (btn.innerText.toLowerCase().includes('пополнить')) btn.style.display = 'none';
        });
    }
    try {
        const saved = localStorage.getItem('active_test');
        if (saved) {
            const data = JSON.parse(saved);
            if (data && data.currentTask) {
                currentTask = data.currentTask; currentSubjectCode = data.currentSubjectCode;
                questionNumber = data.questionNumber; score = data.score; mistakes = data.mistakes;
                currentReviewIndex = data.currentReviewIndex || 0;
                if (data.screenName === 'quick-result-screen') handleQuickResult(data.extra.isCorrect, data.extra.userAnswer, true);
                else if (data.screenName === 'test-finish-screen') showFinishScreen(true);
                else if (data.screenName === 'review-screen') loadReviewForCurrentMistake(true);
                else showTask();
                return;
            }
        }
    } catch(e) {}
    showScreen(document.getElementById('screen-main-menu'));
}
initApp();

// === ЛОГИКА ТЕСТОВ ===
window.openSubjects = function(examType) {
    currentExamType = examType;
    const subjects = (examType === 'ege') ? EGE_SUBJECTS : OGE_SUBJECTS;
    const screen = document.getElementById('screen-subjects');
    screen.innerHTML = `<h1>Выберите предмет</h1>`;
    for (const code in subjects) {
        const btn = document.createElement('button'); btn.className = 'button'; btn.innerText = subjects[code];
        btn.onclick = () => selectTariff(code, subjects[code]); screen.appendChild(btn);
    }
    const back = document.createElement('button'); back.className = 'button secondary'; back.style.marginTop = '20px'; back.innerText = '🔙 В меню';
    back.onclick = () => showScreen(document.getElementById('screen-main-menu')); screen.appendChild(back);
    showScreen(screen);
};

document.querySelectorAll('#screen-main-menu .button').forEach(btn => {
    btn.addEventListener('click', () => { if (btn.dataset.examType) openSubjects(btn.dataset.examType); });
});

window.selectTariff = function(code, name) {
    const screen = document.getElementById('screen-subjects');
    screen.innerHTML = `
        <h2>${name}</h2>
        <div style="margin-bottom: 10px;"><button class="button" style="background:#4a76a8;" onclick="startTest('${code}', 'standard')">Стандарт (3 кр.)</button></div>
        <div style="font-size:12px; color:#666; margin-bottom:15px;">Обычные разборы ошибок от ИИ.</div>
        <div style="margin-bottom: 10px;"><button class="button" style="background:#2a5885;" onclick="startTest('${code}', 'pro')">Профи (4 кр.)</button></div>
        <div style="font-size:12px; color:#666; margin-bottom:20px;">Максимально подробные разборы «на пальцах».</div>
        <button class="button secondary" onclick="openSubjects(currentExamType)">⬅️ Назад</button>
    `;
};

window.startTest = async function(code, mode) {
    currentTestMode = mode; showScreen(document.getElementById('screen-loading'));
    try {
        const resp = await fetch(`${TEST_API_URL}/start_test_payment/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ student_id: String(USER_ID || 'guest'), test_mode: mode, vk_params: VK_SEARCH_PARAMS }) });
        const res = await resp.json();
        if (res.success) { currentSubjectCode = code; questionNumber = 1; score = 0; mistakes = []; getRandomTask(); }
        else { showCustomAlert(res.error || "Нет кредитов"); showScreen(document.getElementById('screen-main-menu')); }
    } catch (e) { showScreen(document.getElementById('screen-main-menu')); }
};

async function getRandomTask() {
    try {
        const resp = await fetch(`${TEST_API_URL}/random_task/?exam_type=${currentSubjectCode}&student_id=${USER_ID || 'guest'}&vk_params=${encodeURIComponent(VK_SEARCH_PARAMS)}`);
        currentTask = await resp.json();
        if (currentTask.done) { localStorage.removeItem('active_test'); showCustomAlert(currentTask.text, "Ура!"); showScreen(document.getElementById('screen-main-menu')); return; }
        showTask();
    } catch (e) { showScreen(document.getElementById('screen-main-menu')); }
}

function showTask() {
    saveSession('task-screen');
    document.getElementById('test-progress').textContent = `Вопрос ${questionNumber} из ${TEST_LENGTH}`;
    const txt = currentTask.task_text || currentTask.text || "";
    document.getElementById('task-text').innerHTML = txt.replace(/Решите уравнения/gi, '').replace(/^\d+[\.\)]\s*/, '');
    const img = document.getElementById('task-image-container');
    if (currentTask.image) { img.innerHTML = `<img src="https://neuro-master.online/${currentTask.image}" style="width:100%; border-radius:8px;">`; img.style.display = 'block'; }
    else { img.style.display = 'none'; }
    setTimeout(() => renderMath('task-text'), 100);
    showScreen(document.getElementById('task-screen'));
}

function normalizeText(s) { return s ? s.toString().replace(/[^\w\sа-яА-ЯёЁ\.,\-]/gi, '').replace(/\s+/g, '').trim().toLowerCase() : ""; }

window.submitAnswer = async function() {
    const raw = document.getElementById('user-answer').value;
    const ans = normalizeText(raw);
    if (!ans) { showCustomAlert("Введите ответ!"); return; }
    showScreen(document.getElementById('screen-loading'));
    try {
        const resp = await fetch(`${TEST_API_URL}/check/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_answer: ans, task_id: currentTask.id, student_id: String(USER_ID || 'guest'), vk_params: VK_SEARCH_PARAMS }) });
        const res = await resp.json();
        if (res.correct_was) currentTask.answer = res.correct_was;
        handleQuickResult(res.is_correct, raw);
    } catch (e) { showScreen(document.getElementById('task-screen')); }
};

function handleQuickResult(isCorrect, ans, restored = false) {
    const title = document.getElementById('quick-result-title');
    const correct = isCorrect || normalizeText(ans) === normalizeText(currentTask.answer);
    if (!restored) { if (correct) score++; else mistakes.push({ task: currentTask, user_answer: ans }); }
    title.innerHTML = correct ? '<div style="color:#4CAF50;">Верно!</div>' : `<div style="color:#ff5252;">Неверно!</div><br><small>Ожидалось: ${currentTask.answer || "---"}</small>`;
    if (!restored) saveSession('quick-result-screen', { isCorrect: correct, userAnswer: ans });
    showScreen(document.getElementById('quick-result-screen'));
}

window.nextTask = function() {
    if (isProcessing) return;
    isProcessing = true;
    questionNumber++;
    if (questionNumber <= TEST_LENGTH) getRandomTask().finally(() => isProcessing = false);
    else { showFinishScreen(); isProcessing = false; }
};

function showFinishScreen(restored = false) {
    document.getElementById('final-score').textContent = score;
    const btn = document.getElementById('review-buttons');
    btn.style.display = mistakes.length > 0 ? 'block' : 'none';
    if (!restored) saveSession('test-finish-screen');
    showScreen(document.getElementById('test-finish-screen'));
}

// === РАЗБОР ОШИБОК ===
window.startReview = function() { currentReviewIndex = 0; loadReviewForCurrentMistake(); };
window.prevReview = function() { if (currentReviewIndex > 0) { currentReviewIndex--; loadReviewForCurrentMistake(); } };
window.nextReview = function() { currentReviewIndex++; if (currentReviewIndex < mistakes.length) loadReviewForCurrentMistake(); else finishSession(); };

function loadReviewForCurrentMistake(restored = false) {
    const m = mistakes[currentReviewIndex];
    document.getElementById('review-progress').textContent = `Ошибка ${currentReviewIndex + 1}`;
    document.getElementById('review-answers-block').innerHTML = `<div style="color:#d32f2f;">Твой: ${m.user_answer}</div><div style="color:#388e3c;">Правильный: ${m.task.answer}</div>`;
    const img = document.getElementById('review-image-container');
    img.innerHTML = m.task.image ? `<img src="https://neuro-master.online/${m.task.image}" style="width:100%;">` : `<div style="padding:10px; background:#f5f5f5;">${m.task.task_text || m.task.text}</div>`;
    
    let nav = `<button class="submit-btn" style="margin-bottom:10px;" onclick="runAIExplanation()">Разбор с ИИ</button><div style="display:flex; gap:10px;">`;
    if (currentReviewIndex > 0) nav += `<button class="button secondary" style="flex:1" onclick="prevReview()">⬅️ Назад</button>`;
    nav += `<button class="button" style="flex:1" onclick="nextReview()">${currentReviewIndex < mistakes.length - 1 ? 'Далее' : 'Завершить'}</button></div>`;
    document.getElementById('review-explanation').innerHTML = nav;
    if (!restored) saveSession('review-screen');
    showScreen(document.getElementById('review-screen'));
}

window.runAIExplanation = async function() {
    const m = mistakes[currentReviewIndex];
    const box = document.getElementById('review-explanation');
    const oldHtml = box.innerHTML;
    box.innerHTML = `<div class="spinner" style="width:20px; height:20px;"></div>` + oldHtml;
    try {
        const resp = await fetch(`${TEST_API_URL}/review/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_answer: String(m.user_answer), task_text: m.task.task_text || m.task.text, simplify: (currentTestMode === 'pro'), student_id: String(USER_ID || 'guest'), vk_params: VK_SEARCH_PARAMS }) });
        const res = await resp.json();
        box.innerHTML = `<div style="text-align:left; margin-bottom:15px; font-size:14px; line-height:1.4;">${res.explanation}</div>` + oldHtml.replace(/<button.*?>Разбор с ИИ<\/button>/, '');
    } catch (e) { box.innerHTML = oldHtml; }
};

// === ПРОФИЛЬ И ПОМОЩЬ ===
window.showHelp = function() {
    const help = document.getElementById('screen-help');
    const payBlock = document.getElementById('help-payment-block');
    if (payBlock) payBlock.style.display = canPay ? 'block' : 'none';
    showScreen(help);
};

window.showProfile = async function() {
    showScreen(document.getElementById('screen-loading'));
    try {
        const resp = await fetch(`${TEST_API_URL}/profile_base/?student_id=${USER_ID || 'guest'}&vk_params=${encodeURIComponent(VK_SEARCH_PARAMS)}`);
        const data = await resp.json();
        
        let subjectsHtml = '';
        if (data.subject_counts && Object.keys(data.subject_counts).length > 0) {
            for (const [subjCode, count] of Object.entries(data.subject_counts)) {
                subjectsHtml += `<div style="padding:10px; border-bottom:1px solid #eee; display:flex; justify-content:space-between;"><span>${ALL_SUBJECTS[subjCode] || subjCode}</span> <b>${count}</b></div>`;
            }
        } else { subjectsHtml = '<p style="color:#999;">Реши первый тест, чтобы увидеть статистику!</p>'; }

        let topUp = canPay ? `<div style="background:#fff; padding:15px; border-radius:10px; margin-top:20px; border: 1px solid #e1e3e6;"><h3>Пополнить баланс</h3><button class="button" onclick="buyPackage(15)">15 кр. — 150 р.</button><button class="button" style="margin-top:10px;" onclick="buyPackage(100)">100 кр. — 700 р.</button></div>` : '';

        document.getElementById('screen-subjects').innerHTML = `
            <h2>Мой профиль</h2>
            <div style="background:white; padding:15px; border-radius:10px; margin-bottom:20px; display:flex; justify-content:space-around; text-align:center; border:1px solid #e1e3e6;">
                <div><div style="font-size:20px; font-weight:bold; color:#ff9800;">${data.balance}</div><div style="font-size:10px; color:#777;">КРЕДИТОВ</div></div>
                <div><div style="font-size:20px; font-weight:bold; color:#4CAF50;">${data.total_solved}</div><div style="font-size:10px; color:#777;">РЕШЕНО</div></div>
            </div>
            <div style="background:white; padding:10px; border-radius:10px; text-align:left; border:1px solid #e1e3e6;">
                <h4 style="margin:0 0 10px 0;">Твой прогресс:</h4>
                ${subjectsHtml}
            </div>
            ${topUp}
            <button class="button secondary" style="margin-top:20px;" onclick="showScreen(document.getElementById('screen-main-menu'))">В меню</button>
        `;
        showScreen(document.getElementById('screen-subjects'));
    } catch (e) { showScreen(document.getElementById('screen-main-menu')); }
};

window.buyPackage = async function(amt) {
    try {
        const resp = await fetch(`${TEST_API_URL}/create_payment/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ student_id: String(USER_ID || 'guest'), amount: amt, price: (amt === 15 ? 150 : 700), vk_params: VK_SEARCH_PARAMS }) });
        const res = await resp.json();
        if (res.confirmation_url) vkBridge.send("VKWebAppOpenUrl", { "url": res.confirmation_url });
    } catch (e) {}
};

window.finishSession = () => { localStorage.removeItem('active_test'); showScreen(document.getElementById('screen-main-menu')); };

window.abortTest = function() {
    if (confirm("Прервать тест? Прогресс будет утерян.")) finishSession();
};

document.addEventListener('click', function(e) {
    const link = e.target.closest('a');
    if (link && link.href) {
        e.preventDefault(); 
        vkBridge.send("VKWebAppOpenUrl", {"url": link.href}).catch(() => window.open(link.href, '_blank'));
    }
});
