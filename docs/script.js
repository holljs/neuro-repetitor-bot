const API_SERVER_URL = "https://neuro-master.online";
const TEST_API_URL = "https://neuro-master.online/repetitor-api"; 

// Экраны
const loadingScreen = document.getElementById('screen-loading');
const mainMenuScreen = document.getElementById('screen-main-menu');
const subjectScreen = document.getElementById('screen-subjects');
const taskScreen = document.getElementById('task-screen');
const quickResultScreen = document.getElementById('quick-result-screen');
const testFinishScreen = document.getElementById('test-finish-screen');
const reviewScreen = document.getElementById('review-screen');

// --- ДЕТЕКТОР ПЛАТФОРМЫ ВК ---
const urlParams = new URLSearchParams(window.location.search);
const vkPlatform = urlParams.get('vk_platform') || 'desktop_web';
const isMobileVK = vkPlatform !== 'desktop_web';

let USER_ID = null;

// Функция для отрисовки формул KaTeX
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

// ТЕ САМЫЕ КНОПКИ С ЭМОДЗИ ДЛЯ ЭКРАНА ВЫБОРА
const OGE_SUBJECTS = { 
    "oge_math": "🧮 Математика ОГЭ",
    "oge_russian": "📚 Русский язык ОГЭ", 
    "oge_english": "☕ Английский ОГЭ",
    "oge_chemistry": "🧪 Химия ОГЭ",
    "oge_physics": "⚡ Физика ОГЭ",
    "oge_geography": "🌍 География ОГЭ",
    // --- НОВЫЕ ПРЕДМЕТЫ ---
    "oge_biology": "🧬 Биология ОГЭ",
    "oge_informatics": "💻 Информатика ОГЭ",
    "oge_history": "📜 История ОГЭ",
    "oge_social": "📊 Обществознание ОГЭ"
};

const EGE_SUBJECTS = { 
    "math_ege": "📐 Математика (профиль)",
    "russian_ege": "🖋️ Русский язык ЕГЭ" // Поставил перо, смотрится очень по-экзаменационному
};

const TOPIC_TRANSLATIONS = {
    // Математика
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
    // Английский
    "grammar": "📚 Грамматика (Англ)",
    "vocabulary": "📝 Лексика (Англ)",
    // Русский
    "syntax": "🏗️ Синтаксис (Зад. 2-3)",
    "punctuation": "✍️ Пунктуация (Зад. 4-5)",
    "orthography": "📝 Орфография (Зад. 6-7)",
    "lexis": "📖 Лексика и грамматика (Зад. 8-9)",
    "chemistry_part1": "🧪 Химия (Часть 1)",
    "physics_part1": "⚡ Физика (Часть 1)"
};

// СОСТОЯНИЕ ТЕСТА
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

// 1. ЗАПУСК И ЗАПРОС РАЗРЕШЕНИЙ
function startApp() {
    showScreen(mainMenuScreen);

    // Получаем ID пользователя
    vkBridge.send('VKWebAppGetUserInfo')
        .then(userData => {
            USER_ID = userData.id;
            console.log("ID пользователя получен:", USER_ID);
            
            // СРАЗУ ПОСЛЕ ЭТОГО ПРОСИМ РАЗРЕШИТЬ СООБЩЕНИЯ
            vkBridge.send("VKWebAppAllowMessagesFromGroup", {"group_id": 235924452})
                .then(data => {
                    console.log("Разрешение на сообщения получено!", data);
                })
                .catch(error => {
                    console.log("Пользователь отказался получать сообщения", error);
                });
        })
        .catch(error => {
            console.log("ВК не отдал профиль", error);
        });
}

// 2. ВЫБОР ПРЕДМЕТА И ТАРИФА
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

// Новый экран выбора стоимости
window.selectTariff = function(subjectCode, subjectName) {
    subjectScreen.innerHTML = `
        <h2>${subjectName}</h2>
        <p style="text-align:center; color:#555; margin-bottom:20px;">Выберите формат тренировки:</p>
        
        <button class="button" style="margin-bottom:10px;" onclick="startTest('${subjectCode}', 'standard')">
            🟢 Стандарт (3 кредита)<br><small style="font-size:12px; opacity:0.8;">Обычные разборы ошибок</small>
        </button>
        
        <button class="button" style="background-color:#ff9800; margin-bottom:20px;" onclick="startTest('${subjectCode}', 'pro')">
            🔥 Профи (4 кредита)<br><small style="font-size:12px; opacity:0.9;">Разборы ошибок "на пальцах"</small>
        </button>
        
        <button class="button secondary" onclick="showScreen(mainMenuScreen)">🔙 В главное меню</button>
    `;
}

// 3. НАЧАЛО ТЕСТА
window.startTest = async function(subjectCode, mode) {
    currentTestMode = mode; // Сохраняем тариф
    showScreen(loadingScreen);
    
    try {
        const payResponse = await fetch(`${TEST_API_URL}/start_test_payment/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                student_id: String(USER_ID || 'guest'), 
                test_mode: currentTestMode
            })
        });
        const payResult = await payResponse.json();
        
        if (payResult.success) {
            currentSubjectCode = subjectCode;
            questionNumber = 1; score = 0; mistakes = [];
            getRandomTask();
        } else { 
            alert("Недостаточно кредитов"); 
            showScreen(mainMenuScreen); 
        }
    } catch (e) { showScreen(mainMenuScreen); }
}

async function getRandomTask() {
    try {
        const response = await fetch(`${TEST_API_URL}/random_task/?exam_type=${currentSubjectCode}&student_id=${USER_ID || 'guest'}`);
        currentTask = await response.json();
        
        if (currentTask.done) {
            alert(currentTask.text);
            showScreen(mainMenuScreen);
            return;
        }
        
        showTask();
    } catch (e) { showScreen(mainMenuScreen); }
}

// 4. ОТОБРАЖЕНИЕ ЗАДАЧИ
function showTask() {
    document.getElementById('test-progress').textContent = `Вопрос ${questionNumber} из ${TEST_LENGTH}`;
    const taskTextElement = document.getElementById('task-text');
    const imageContainer = document.getElementById('task-image-container');

    let rawText = currentTask.task_text || currentTask.text || "";
    
    if (!rawText && currentTask.number) {
        rawText = "Задача №" + currentTask.number;
    }

    if (rawText) {
        let cleanText = rawText;
        
        // Очистка только для Математики (ОГЭ и ЕГЭ)
if (currentSubjectCode === 'oge_math' || currentSubjectCode === 'math_ege') {
    cleanText = cleanText
        .replace(/Решите уравнения/gi, '')
        .replace(/Решите уравнение/gi, '')
        .replace(/^\d+[\.\)]\s*/, '') 
        .trim();
    cleanText = cleanText.charAt(0).toUpperCase() + cleanText.slice(1);
}

        // Красивое форматирование для Английского
        if (currentSubjectCode === 'oge_english') {
            cleanText = cleanText.replace(/____/g, '<span style="display:inline-block; width: 60px; border-bottom: 2px solid #333; margin: 0 5px;"></span>');
        }

        taskTextElement.innerHTML = `<div style="font-size: 1.1em; line-height: 1.5;">${cleanText}</div>`;
        taskTextElement.style.display = 'block';
    } else {
        taskTextElement.textContent = "Текст задачи не найден в базе";
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
    return str.toString()
        .replace(/[\u2012\u2013\u2014\u2212]/g, '-')
        .replace(',', '.')
        .replace(/\s+/g, '')
        .trim()
        .toLowerCase();
}

// 5. ПРОВЕРКА ОТВЕТА
window.submitAnswer = async function() {
    let rawInput = document.getElementById('user-answer').value;
    let userAnswer = normalizeText(rawInput);
    if (!userAnswer) return;
    
    showScreen(loadingScreen);
    try {
        const response = await fetch(`${TEST_API_URL}/check/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_answer: userAnswer,
                task_id: currentTask.id,
                student_id: String(USER_ID || 'guest')
            })
        });
        const result = await response.json();
        handleQuickResult(result.is_correct, rawInput); 
    } catch (error) {
        showScreen(taskScreen); 
    }
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
        titleEl.innerHTML = `<span style="color:red; display:block; margin-bottom:10px;">❌ Неверно!</span>
                             <small style="color:#555;">Ожидалось: <b>${currentTask.answer || "---"}</b><br>Твой ввод: <b>${userAnswer}</b></small>`;
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

// 6. ФИНАЛ И АНАЛИТИКА
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
        statsHTML = `<div id="topic-stats" style="margin-top:15px; text-align:left;"><b>🚩 Рекомендуем повторить темы:</b><ul style="padding-left:20px; margin-top:5px;">`;
        for (let topic in topicAnalysis) { 
            const prettyName = TOPIC_TRANSLATIONS[topic] || topic;
            statsHTML += `<li>${prettyName} (${topicAnalysis[topic]} ошиб.)</li>`; 
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

// 7. РАЗБОР ОШИБОК И ИИ
window.startReview = function() { currentReviewIndex = 0; loadReviewForCurrentMistake(); }

function loadReviewForCurrentMistake() {
    const mistake = mistakes[currentReviewIndex];
    document.getElementById('review-progress').textContent = `Разбор ошибки ${currentReviewIndex + 1} из ${mistakes.length}`;
    
    document.getElementById('review-answers-block').innerHTML = `
        <p><b>❌ Твой ответ:</b> <span style="color:red;">${mistake.user_answer}</span></p>
        <p><b>✅ Правильный ответ:</b> <span style="color:green;">${mistake.task.answer || "---"}</span></p>
    `;
    
    const reviewImgContainer = document.getElementById('review-image-container');
    if (mistake.task.image && mistake.task.image.length > 5) {
        const fullImgUrl = mistake.task.image.startsWith('http') ? mistake.task.image : `https://neuro-master.online/${mistake.task.image}`;
        reviewImgContainer.innerHTML = `<img src="${encodeURI(fullImgUrl)}" class="question-image" style="max-width: 100%; border-radius: 8px;">`;
    } else { 
        let cleanText = mistake.task.task_text || mistake.task.text;
        if (cleanText) cleanText = cleanText.replace(/____/g, '<span style="display:inline-block; width: 60px; border-bottom: 2px solid #333; margin: 0 5px;"></span>');
        reviewImgContainer.innerHTML = `<div style="padding:15px; background:#f9f9f9; border-radius:8px; font-size: 14px;">${cleanText}</div>`; 
    }
        
    document.getElementById('review-explanation').innerHTML = `<button class="button" onclick="runAIExplanation()">🧠 Разбор этой задачи с ИИ</button>`;
    
    setTimeout(() => { 
        renderMath('review-answers-block');
        renderMath('review-image-container'); 
    }, 100);

    showScreen(reviewScreen);
}

window.runAIExplanation = async function(simplify = false) {
    const mistake = mistakes[currentReviewIndex];
    const explanationBox = document.getElementById('review-explanation');
    explanationBox.innerHTML = simplify ? "<i>⏳ Объясняю просто...</i>" : "<i>⏳ Пишу решение...</i>";

    const taskText = mistake.task.task_text || mistake.task.text || "Текст задачи";
    let imageUrl = mistake.task.image || null;
    if (imageUrl && !imageUrl.startsWith('http')) {
        imageUrl = `https://neuro-master.online/${imageUrl}`; 
    }

    try {
        const response = await fetch(`${TEST_API_URL}/review/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_answer: String(mistake.user_answer),
                image_url: imageUrl, 
                task_text: taskText,
                simplify: simplify
            })
        });
        const result = await response.json();
        
        let proButtonHTML = "";
        if (currentTestMode === "pro" && !simplify) {
            proButtonHTML = `<button class="button secondary" onclick="runAIExplanation(true)" style="margin-top:10px;">🍎 Объяснить проще ("на пальцах")</button>`;
        }

        explanationBox.innerHTML = `<div style="text-align:left; font-size:14px; background:#fff; padding:12px; border-radius:8px; border:1px solid #ddd; margin-bottom:10px;">
                                        ${result.explanation}
                                    </div>
                                    ${proButtonHTML}`;
        
        setTimeout(() => { renderMath('review-explanation'); }, 100);

    } catch (error) { 
        explanationBox.innerHTML = `⚠️ Ошибка сервера.`; 
    }
}

// 8. ЗУМ КАРТИНОК
document.addEventListener('click', function (e) {
    if (e.target.tagName === 'IMG' && e.target.classList.contains('question-image')) {
        const fullScreen = document.createElement('div');
        fullScreen.style = "position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.9); z-index:1000; display:flex; align-items:center; justify-content:center;";
        fullScreen.innerHTML = `<img src="${e.target.src}" style="max-width:95%; max-height:95%; object-fit:contain;">`;
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

// 👤 ЭКРАН ПРОФИЛЯ (С УМНЫМ СКРЫТИЕМ ОПЛАТЫ)
window.showProfile = async function() {
    showScreen(loadingScreen);
    
    let userCredits = 5; // Заглушка, пока сервер не пришлет точную цифру
    
    let topUpBlock = "";
    
    if (isMobileVK) {
        topUpBlock = `
            <div style="margin-top:20px; padding:15px; background:#f0f4f8; border-radius:10px; font-size:13px; color:#555;">
                ℹ️ Пополнение баланса доступно только в полной веб-версии ВКонтакте (с компьютера).
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

    subjectScreen.innerHTML = `
        <h2>👤 Мой профиль</h2>
        <div style="font-size:18px; margin-bottom:10px;">
            💰 Твой баланс: <b>${userCredits} кр.</b>
        </div>
        
        ${topUpBlock}
        
        <button class="button secondary" style="margin-top:20px;" onclick="showScreen(mainMenuScreen)">🔙 В главное меню</button>
    `;
    
    showScreen(subjectScreen);
}

// Заглушка для функции покупки
window.buyPackage = function(creditsAmount) {
    alert("Здесь будет вызов ЮКассы для покупки " + creditsAmount + " кредитов!");
}

// Запуск без ожиданий
vkBridge.send('VKWebAppInit');
startApp();
