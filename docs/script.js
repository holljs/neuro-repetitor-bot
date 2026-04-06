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

// Детектор платформы ВК
const urlParams = new URLSearchParams(window.location.search);
const vkPlatform = urlParams.get('vk_platform') || 'desktop_web';
const isMobileVK = vkPlatform !== 'desktop_web';

let USER_ID = null;

// Отрисовка формул KaTeX
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

// Список предметов ОГЭ
const OGE_SUBJECTS = { 
    "oge_math": "🧮 Математика ОГЭ",
    "oge_russian": "📚 Русский язык ОГЭ", 
    "oge_english": "☕ Английский ОГЭ",
    "oge_chemistry": "🧪 Химия ОГЭ",
    "oge_physics": "⚡ Физика ОГЭ",
    "oge_geography": "🌍 География ОГЭ",
    "oge_biology": "🧬 Биология ОГЭ",
    "oge_informatics": "💻 Информатика ОГЭ",
    "oge_history": "📜 История ОГЭ",
    "oge_social": "📊 Обществознание ОГЭ"
};

// Список предметов ЕГЭ
const EGE_SUBJECTS = { 
    "math_ege": "📐 Математика (профиль)",
    "russian_ege": "🖋️ Русский язык ЕГЭ",
    "inf_ege": "💻 Информатика ЕГЭ",
    "geo_ege": "🌍 География ЕГЭ",
    "phys_ege": "⚡ Физика ЕГЭ"
};

// Перевод тем для статистики
const TOPIC_TRANSLATIONS = {
    "topic_01": "🏠 Практические задачи",
    "topic_02": "🔢 Вычисления и дроби",
    "topic_03": "📏 Единицы измерения",
    "topic_04": "⚖️ Уравнения",
    "topic_04_eq": "⚖️ Уравнения",
    "topic_05": "📍 Координатная прямая",
    "topic_06": "📊 Графики и диаграммы",
    "topic_07": "📈 Графики функций",
    "topic_08": "🧩 Выражения",
    "topic_09": "🧪 Формулы",
    "topic_10": "🔢 Последовательности",
    "grammar": "📚 Грамматика (Англ)",
    "vocabulary": "📝 Лексика (Англ)",
    "syntax": "🏗️ Синтаксис (Зад. 2-3)",
    "punctuation": "✍️ Пунктуация (Зад. 4-5)",
    "orthography": "📝 Орфография (Зад. 6-7)",
    "lexis": "📖 Лексика и грамматика (Зад. 8-9)",
    "chemistry_part1": "🧪 Химия (Часть 1)",
    "physics_part1": "⚡ Физика (Часть 1)"
};

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
    if(screenElement) screenElement.style.display = 'block';
}

function startApp() {
    showScreen(mainMenuScreen);
    vkBridge.send('VKWebAppInit');
    vkBridge.send('VKWebAppGetUserInfo')
        .then(userData => {
            USER_ID = userData.id;
            console.log("ID пользователя получен:", USER_ID);
            vkBridge.send("VKWebAppAllowMessagesFromGroup", {"group_id": 235924452});
        })
        .catch(error => console.log("ВК не отдал профиль", error));
}

document.querySelectorAll('#screen-main-menu .button').forEach(button => {
    button.addEventListener('click', () => {
        const examType = button.dataset.examType;
        const subjects = (examType === 'ege') ? EGE_SUBJECTS : OGE_SUBJECTS;
        subjectScreen.innerHTML = `<h1>Выберите предмет</h1>`;
        for (const code in subjects) {
            const btn = document.createElement('button');
            btn.className = 'button';
            btn.innerText = subjects[code];
            btn.onclick = () => selectTariff(code, subjects[code]); 
            subjectScreen.appendChild(btn);
        }
        showScreen(subjectScreen);
    });
});

window.selectTariff = function(subjectCode, subjectName) {
    subjectScreen.innerHTML = `
        <h2>${subjectName}</h2>
        <p style="text-align:center; color:#555; margin-bottom:20px;">Выберите формат тренировки:</p>
        <button class="button" style="margin-bottom:10px;" onclick="startTest('${subjectCode}', 'standard')">🟢 Стандарт (3 кредита)</button>
        <button class="button" style="background-color:#ff9800; margin-bottom:20px;" onclick="startTest('${subjectCode}', 'pro')">🔥 Профи (4 кредита)</button>
        <button class="button secondary" onclick="showScreen(mainMenuScreen)">🔙 В главное меню</button>
    `;
}

window.startTest = async function(subjectCode, mode) {
    currentTestMode = mode;
    showScreen(loadingScreen);
    try {
        const payResponse = await fetch(`${TEST_API_URL}/start_test_payment/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ student_id: String(USER_ID || 'guest'), test_mode: currentTestMode })
        });
        const payResult = await payResponse.json();
        if (payResult.success) {
            currentSubjectCode = subjectCode;
            questionNumber = 1; score = 0; mistakes = [];
            getRandomTask();
        } else { alert("Недостаточно кредитов"); showScreen(mainMenuScreen); }
    } catch (e) { showScreen(mainMenuScreen); }
}

async function getRandomTask() {
    try {
        const response = await fetch(`${TEST_API_URL}/random_task/?exam_type=${currentSubjectCode}&student_id=${USER_ID || 'guest'}`);
        currentTask = await response.json();
        if (currentTask.done) { alert(currentTask.text); showScreen(mainMenuScreen); return; }
        showTask();
    } catch (e) { showScreen(mainMenuScreen); }
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

window.submitAnswer = async function() {
    let rawInput = document.getElementById('user-answer').value;
    let userAnswer = normalizeText(rawInput);
    if (!userAnswer) return;
    showScreen(loadingScreen);
    try {
        const response = await fetch(`${TEST_API_URL}/check/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_answer: userAnswer, task_id: currentTask.id, student_id: String(USER_ID || 'guest') })
        });
        const result = await response.json();
        handleQuickResult(result.is_correct, rawInput); 
    } catch (error) { showScreen(taskScreen); }
}

function handleQuickResult(isCorrect, userAnswer) {
    const titleEl = document.getElementById('quick-result-title');
    const normUser = normalizeText(userAnswer);
    const normCorrect = normalizeText(currentTask.answer);
    const finalCorrect = isCorrect || (normUser === normCorrect);
    if (finalCorrect) {
        titleEl.innerHTML = '<span style="color:green">🎉 Верно!</span>';
        score++;
    } else {
        titleEl.innerHTML = `<span style="color:red; display:block; margin-bottom:10px;">❌ Неверно!</span><br><small style="color:#555;">Ожидалось: <b>${currentTask.answer || "---"}</b></small>`;
        mistakes.push({ task: currentTask, user_answer: userAnswer });
    }
    setTimeout(() => { renderMath('quick-result-screen'); }, 100);
    showScreen(quickResultScreen);
}

window.nextTask = function() {
    questionNumber++;
    if (questionNumber <= TEST_LENGTH) getRandomTask();
    else showFinishScreen();
}

function showFinishScreen() {
    document.getElementById('final-score').textContent = score;
    document.getElementById('final-mistakes').textContent = mistakes.length;
    let topicAnalysis = {};
    mistakes.forEach(m => {
        let t = m.task.topic || "unknown";
        topicAnalysis[t] = (topicAnalysis[t] || 0) + 1;
    });
    let statsHTML = "";
    if (mistakes.length > 0) {
        statsHTML = `<div id="topic-stats" style="margin-top:15px; text-align:left;"><b>🚩 Темы для повторения:</b><ul style="padding-left:20px;">`;
        for (let topic in topicAnalysis) { 
            const prettyName = TOPIC_TRANSLATIONS[topic] || topic;
            statsHTML += `<li>${prettyName}</li>`; 
        }
        statsHTML += `</ul></div>`;
    }
    const oldStats = document.getElementById('topic-stats');
    if (oldStats) oldStats.remove();
    const reviewBtnBlock = document.getElementById('review-buttons');
    if (mistakes.length > 0) {
        reviewBtnBlock.style.display = 'block';
        reviewBtnBlock.insertAdjacentHTML('beforebegin', statsHTML);
    } else { reviewBtnBlock.style.display = 'none'; }
    showScreen(testFinishScreen);
}

window.startReview = function() { currentReviewIndex = 0; loadReviewForCurrentMistake(); }

function loadReviewForCurrentMistake() {
    const mistake = mistakes[currentReviewIndex];
    document.getElementById('review-progress').textContent = `Разбор ошибки ${currentReviewIndex + 1}`;
    document.getElementById('review-answers-block').innerHTML = `<p>❌ Твой: ${mistake.user_answer}</p><p>✅ Правильный: ${mistake.task.answer}</p>`;
    const reviewImgContainer = document.getElementById('review-image-container');
    if (mistake.task.image && mistake.task.image.length > 5) {
        const fullImgUrl = mistake.task.image.startsWith('http') ? mistake.task.image : `https://neuro-master.online/${mistake.task.image}`;
        reviewImgContainer.innerHTML = `<img src="${encodeURI(fullImgUrl)}" class="question-image" style="max-width: 100%;">`;
    } else { 
        reviewImgContainer.innerHTML = `<div style="padding:15px; background:#f9f9f9;">${mistake.task.task_text || mistake.task.text}</div>`; 
    }
    document.getElementById('review-explanation').innerHTML = `<button class="button" onclick="runAIExplanation()">🧠 Разбор с ИИ</button>`;
    showScreen(reviewScreen);
}

window.runAIExplanation = async function(simplify = false) {
    const mistake = mistakes[currentReviewIndex];
    const explanationBox = document.getElementById('review-explanation');
    explanationBox.innerHTML = "<i>⏳ Генерирую...</i>";
    const taskText = mistake.task.task_text || mistake.task.text || "Текст";
    let imageUrl = mistake.task.image ? `https://neuro-master.online/${mistake.task.image}` : null;
    try {
        const response = await fetch(`${TEST_API_URL}/review/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_answer: String(mistake.user_answer), image_url: imageUrl, task_text: taskText, simplify: simplify })
        });
        const result = await response.json();
        explanationBox.innerHTML = `<div style="text-align:left;">${result.explanation}</div>`;
    } catch (error) { explanationBox.innerHTML = `⚠️ Ошибка.`; }
}

document.addEventListener('click', function (e) {
    if (e.target.tagName === 'IMG' && e.target.classList.contains('question-image')) {
        const fullScreen = document.createElement('div');
        fullScreen.style = "position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.9); z-index:1000; display:flex; align-items:center; justify-content:center;";
        fullScreen.innerHTML = `<img src="${e.target.src}" style="max-width:95%; max-height:95%;">`;
        fullScreen.onclick = () => fullScreen.remove();
        document.body.appendChild(fullScreen);
    }
});

window.nextReview = function() {
    currentReviewIndex++;
    if (currentReviewIndex < mistakes.length) loadReviewForCurrentMistake();
    else showScreen(mainMenuScreen);
}

window.finishSession = () => showScreen(mainMenuScreen);

window.showProfile = async function() {
    showScreen(loadingScreen);
    subjectScreen.innerHTML = `<h2>👤 Профиль</h2><p>Баланс: 5 кр.</p><button class="button secondary" onclick="showScreen(mainMenuScreen)">🔙 Назад</button>`;
    showScreen(subjectScreen);
}

startApp();
