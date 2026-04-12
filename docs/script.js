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

// Усиленный детектор мобильных устройств (ВК + UserAgent)
const urlParams = new URLSearchParams(window.location.search);
const vkPlatform = urlParams.get('vk_platform') || 'desktop_web';
const isMobileDevice = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
const isMobileVK = vkPlatform !== 'desktop_web' || isMobileDevice;

let USER_ID = null;
let currentExamType = null; // Запоминаем, ОГЭ или ЕГЭ выбрал юзер

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
    "phys_ege": "⚡ Физика ЕГЭ",
    "ege_english": "🇬🇧 Английский ЕГЭ" // <--- добавили кнопку для ВК/сайта
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

// 📌 НАВИГАЦИЯ: Открытие списка предметов
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
    
    // КНОПКА ВОЗВРАТА В ГЛАВНОЕ МЕНЮ
    const backBtn = document.createElement('button');
    backBtn.className = 'button secondary';
    backBtn.style.marginTop = '20px';
    backBtn.innerText = '🔙 В главное меню';
    backBtn.onclick = () => showScreen(mainMenuScreen);
    subjectScreen.appendChild(backBtn);

    showScreen(subjectScreen);
}

// Обработчик кнопок ОГЭ / ЕГЭ в главном меню
document.querySelectorAll('#screen-main-menu .button').forEach(button => {
    button.addEventListener('click', () => {
        const examType = button.dataset.examType;
        if (examType) {
            openSubjects(examType);
        }
    });
});

// 📌 НАВИГАЦИЯ: Открытие тарифов с кнопкой "Назад к предметам"
window.selectTariff = function(subjectCode, subjectName) {
    subjectScreen.innerHTML = `
        <h2>${subjectName}</h2>
        <p style="text-align:center; color:#555; margin-bottom:20px;">Выберите формат тренировки:</p>
        <button class="button" style="margin-bottom:10px;" onclick="startTest('${subjectCode}', 'standard')">🟢 Стандарт (3 кредита)</button>
        <button class="button" style="background-color:#ff9800; margin-bottom:20px;" onclick="startTest('${subjectCode}', 'pro')">🔥 Профи (4 кредита)</button>
        
        <button class="button secondary" onclick="openSubjects(currentExamType)">🔙 Назад к предметам</button>
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

// ФИНАЛ И АНАЛИТИКА (С УМНЫМ ИИ-АНАЛИЗОМ)
function showFinishScreen() {
    document.getElementById('final-score').textContent = score;
    document.getElementById('final-mistakes').textContent = mistakes.length;
    
    const reviewBtnBlock = document.getElementById('review-buttons');
    const oldStats = document.getElementById('topic-stats');
    if (oldStats) oldStats.remove();

    if (mistakes.length > 0) {
        reviewBtnBlock.style.display = 'block';
        
        // Создаем блок для ИИ-анализа
        const aiAnalysisBlock = `
            <div id="topic-stats" style="margin-top:20px; text-align:left; background:#f0f8ff; padding:15px; border-radius:10px; border: 1px solid #bcdcff;">
                <h3 style="margin-top:0; color:#0056b3;">🧠 Умный анализ пробелов</h3>
                <p id="ai-analysis-text" style="font-size:14px; color:#333;">Хочешь узнать, какие конкретно темы и правила тебе нужно подтянуть на основе твоих ошибок?</p>
                <button id="ai-analysis-btn" class="button" style="background-color:#007bff; padding:10px; font-size:14px;" onclick="getAIAnalysis()">
                    ✨ Сгенерировать ИИ-анализ
                </button>
            </div>
        `;
        reviewBtnBlock.insertAdjacentHTML('beforebegin', aiAnalysisBlock);
    } else { 
        reviewBtnBlock.style.display = 'none'; 
    }
    
    showScreen(testFinishScreen);
}

// Запрос к нейросети для анализа ошибок
window.getAIAnalysis = async function() {
    const btn = document.getElementById('ai-analysis-btn');
    const textBox = document.getElementById('ai-analysis-text');
    
    btn.style.display = 'none';
    textBox.innerHTML = "<i>⏳ Нейросеть анализирует твои ошибки... Это займет пару секунд.</i>";

    const mistakesData = mistakes.map(m => ({
        task_text: String(m.task.task_text || m.task.text || "Текст не найден"),
        user_answer: String(m.user_answer || ""),
        correct_answer: String(m.task.answer || "")
    }));

    try {
        const response = await fetch(`${TEST_API_URL}/analyze_gaps/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mistakes: mistakesData })
        });
        const result = await response.json();
        
        textBox.innerHTML = `<div style="line-height: 1.5;">${result.analysis}</div>`;
    } catch (error) {
        textBox.innerHTML = `⚠️ Ошибка соединения с сервером. Попробуй позже.`;
        btn.style.display = 'block';
    }
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

// 👤 ЭКРАН ПРОФИЛЯ (ЖЕСТКОЕ СКРЫТИЕ ОПЛАТЫ НА ТЕЛЕФОНАХ + ИИ)
window.showProfile = async function() {
    showScreen(loadingScreen);
    
    try {
        // Запрашиваем данные с сервера
        const response = await fetch(`${TEST_API_URL}/profile_analytics/?student_id=${USER_ID || 'guest'}`);
        const data = await response.json();
        
        let topUpBlock = "";
        
        if (isMobileVK) {
            topUpBlock = `
                <div style="margin-top:20px; padding:15px; background:#f0f4f8; border-radius:10px; font-size:13px; color:#555;">
                    ℹ️ Правила ВКонтакте запрещают прием платежей с мобильных устройств. <b>Для пополнения баланса, пожалуйста, зайди в приложение с компьютера.</b>
                </div>
            `;
        } else {
            topUpBlock = `
                <div style="margin-top:20px; padding:15px; background:#fff; border-radius:10px; border: 1px solid #e1e3e6;">
                    <h3 style="margin-top:0;">💳 Пополнить баланс</h3>
                    <button class="button" style="margin-bottom:10px; background-color:#4CAF50;" onclick="buyPackage(15)">
                        Пакет "Минимум" (15 кр.) — 150 руб.
                    </button>
                    <button class="button" style="background-color:#ff9800;" onclick="buyPackage(100)">
                        Пакет "Максимум" (100 кр.) — 700 руб.
                    </button>
                </div>
            `;
        }

        // Блок ИИ-Аналитики
        let analysisBlock = `
            <div style="margin-top:20px; padding:15px; background:#f0f8ff; border-radius:10px; border: 1px solid #bcdcff; text-align:left;">
                <h3 style="margin-top:0; color:#0056b3;">📈 Динамика твоего обучения</h3>
                <div style="font-size:14px; line-height:1.6; color:#333;">
                    ${data.analysis}
                </div>
            </div>
        `;

        subjectScreen.innerHTML = `
            <h2>👤 Мой профиль</h2>
            <div style="font-size:18px; margin-bottom:10px;">
                💰 Твой баланс: <b>${data.balance || 0} кр.</b><br>
                📝 Решено задач всего: <b>${data.total_solved || 0}</b>
            </div>
            
            ${analysisBlock}
            ${topUpBlock}
            
            <button class="button secondary" style="margin-top:20px;" onclick="showScreen(mainMenuScreen)">🔙 В главное меню</button>
        `;
        
        showScreen(subjectScreen);
    } catch (e) {
        alert("Не удалось загрузить профиль. Проверьте интернет.");
        showScreen(mainMenuScreen);
    }
}

startApp();

// Функция для открытия/закрытия шпаргалки по математике
    window.toggleMathHint = function() {
        const hintBox = document.getElementById('math-hint-box');
        if (hintBox.style.display === 'block') {
            hintBox.style.display = 'none';
        } else {
            hintBox.style.display = 'block';
        }
    }
