const API_SERVER_URL = "https://neuro-master.online";
const TEST_API_URL = "https://neuro-master.online/repetitor-api"; 

vkBridge.send('VKWebAppInit');

// Экраны
const loadingScreen = document.getElementById('screen-loading');
const mainMenuScreen = document.getElementById('screen-main-menu');
const subjectScreen = document.getElementById('screen-subjects');
const taskScreen = document.getElementById('task-screen');
const quickResultScreen = document.getElementById('quick-result-screen');
const testFinishScreen = document.getElementById('test-finish-screen');
const reviewScreen = document.getElementById('review-screen');

let USER_ID = null;
const OGE_SUBJECTS = { "oge_russian": "🇷🇺 Русский язык", "oge_math": "🧮 Математика" };
const EGE_SUBJECTS = { "ege_russian": "🇷🇺 Русский язык", "ege_math_profile": "📐 Математика (профиль)" };

// СОСТОЯНИЕ ТЕСТА
const TEST_LENGTH = 15;
let currentTask = null;
let currentSubjectCode = null;
let questionNumber = 1;
let score = 0;
let mistakes = []; 
let currentReviewIndex = 0;

function showScreen(screenElement) {
    document.querySelectorAll('.screen').forEach(s => { if(s) s.style.display = 'none'; });
    if(screenElement) screenElement.style.display = 'block';
}

// 1. ЗАПУСК
async function startApp() {
    try {
        const userData = await vkBridge.send('VKWebAppGetUserInfo');
        USER_ID = userData.id;
        showScreen(loadingScreen);
        const response = await fetch(`${API_SERVER_URL}/check_sub/${USER_ID}`);
        const subData = await response.json();
        if (subData.subscription === "active") { showScreen(mainMenuScreen); } 
        else { loadingScreen.innerHTML = `<p>У вас нет активной подписки.</p>`; }
    } catch (error) { showScreen(mainMenuScreen); }
}

// 2. ВЫБОР ПРЕДМЕТА
document.querySelectorAll('#screen-main-menu .button').forEach(button => {
    button.addEventListener('click', () => {
        const examType = button.dataset.examType;
        const subjects = (examType === 'ege') ? EGE_SUBJECTS : OGE_SUBJECTS;
        subjectScreen.innerHTML = `<h1>Выберите предмет</h1>`;
        for (const code in subjects) {
            const btn = document.createElement('button');
            btn.className = 'button';
            btn.innerText = subjects[code];
            btn.onclick = () => startTest(code);
            subjectScreen.appendChild(btn);
        }
        showScreen(subjectScreen);
    });
});

// 3. НАЧАЛО ТЕСТА
window.startTest = async function(subjectCode) {
    showScreen(loadingScreen);
    try {
        const payResponse = await fetch(`${TEST_API_URL}/start_test_payment/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task_id: String(USER_ID || 12345) })
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
        const response = await fetch(`${TEST_API_URL}/random_task/?exam_type=${currentSubjectCode}`);
        currentTask = await response.json();
        showTask();
    } catch (e) { showScreen(mainMenuScreen); }
}

// 4. ОТОБРАЖЕНИЕ ЗАДАЧИ
function showTask() {
    document.getElementById('test-progress').textContent = `Вопрос ${questionNumber} из ${TEST_LENGTH}`;
    const imageContainer = document.getElementById('task-image-container');
    const taskTextElement = document.getElementById('task-text');

    // ОЧИСТКА ТЕКСТА (убираем "Решите уравнения" и номер задачи)
    if (currentTask.text) {
        let cleanText = currentTask.text
            .replace(/Решите уравнения/gi, '')
            .replace(/Решите уравнение/gi, '')
            .replace(/^\d+[\.\)]\s*/, '') // Номер в начале
            .replace(/\s\d+[\.\)]\s/, ' ') // Номер в середине
            .trim();
        taskTextElement.textContent = cleanText;
        taskTextElement.style.display = 'block';
    } else { taskTextElement.style.display = 'none'; }

    // КАРТИНКА (прячем если пустая)
    if (currentTask.image && currentTask.image.length > 50) {
        imageContainer.innerHTML = `<img src="${currentTask.image}" class="question-image" style="max-width: 100%; border-radius: 8px; cursor: zoom-in;">`;
        imageContainer.style.display = 'block';
    } else { imageContainer.style.display = 'none'; }

    document.getElementById('user-answer').value = '';
    showScreen(taskScreen);
}

// 5. ПРОВЕРКА ОТВЕТА (Исправленная!)
window.submitAnswer = async function() {
    let userAnswer = document.getElementById('user-answer').value.trim().replace('.', ',');
    if (!userAnswer) return;
    
    showScreen(loadingScreen);
    try {
        const response = await fetch(`${TEST_API_URL}/check/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_answer: userAnswer,
                task_id: currentTask.id,
                student_id: USER_ID || 12345
            })
        });
        const result = await response.json();
        handleQuickResult(result.is_correct, userAnswer);
    } catch (error) { showScreen(taskScreen); }
}

function handleQuickResult(isCorrect, userAnswer) {
    const titleEl = document.getElementById('quick-result-title');
    if (isCorrect) {
        titleEl.innerHTML = '<span style="color:green">🎉 Верно!</span>';
        score++;
    } else {
        titleEl.innerHTML = `<span style="color:red; display:block; margin-bottom:10px;">❌ Неверно!</span>
                             <small style="color:#555;">Ожидалось: <b>${currentTask.answer || "---"}</b><br>Твой ввод: <b>${userAnswer}</b></small>`;
        mistakes.push({ task: currentTask, user_answer: userAnswer });
    }
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
        let t = m.task.topic || "Общая тема";
        topicAnalysis[t] = (topicAnalysis[t] || 0) + 1;
    });

    let statsHTML = "";
    if (mistakes.length > 0) {
        statsHTML = `<div id="topic-stats"><b>🚩 Рекомендуем повторить темы:</b><ul>`;
        for (let topic in topicAnalysis) { statsHTML += `<li>${topic} (${topicAnalysis[topic]} ошиб.)</li>`; }
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
    if (mistake.task.image && mistake.task.image.length > 50) {
        reviewImgContainer.innerHTML = `<img src="${mistake.task.image}" class="question-image" style="max-width: 100%; border-radius: 8px;">`;
    } else { reviewImgContainer.innerHTML = `<div style="padding:10px; background:#f9f9f9; border-radius:8px;">${mistake.task.text}</div>`; }
    
    document.getElementById('review-explanation').innerHTML = `<button class="button" onclick="runAIExplanation()">🧠 Разбор этой задачи с ИИ</button>`;
    showScreen(reviewScreen);
}

window.runAIExplanation = async function(simplify = false) {
    const mistake = mistakes[currentReviewIndex];
    const explanationBox = document.getElementById('review-explanation');
    explanationBox.innerHTML = simplify ? "<i>⏳ Объясняю просто...</i>" : "<i>⏳ Пишу решение...</i>";

    try {
        const response = await fetch(`${TEST_API_URL}/review/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_answer: mistake.user_answer,
                image_url: mistake.task.image ? mistake.task.image.split(',')[1] : null, 
                task_text: mistake.task.text,
                simplify: simplify
            })
        });
        const result = await response.json();
        explanationBox.innerHTML = `<div style="text-align:left; font-size:14px;">${result.explanation}</div>
                                    <button class="button secondary" onclick="runAIExplanation(true)" style="margin-top:10px;">🍎 Объяснить проще</button>`;
    } catch (error) { explanationBox.innerHTML = `Ошибка сервера.`; }
}

window.nextReview = function() {
    currentReviewIndex++;
    if (currentReviewIndex < mistakes.length) loadReviewForCurrentMistake();
    else showScreen(mainMenuScreen);
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

window.finishSession = () => showScreen(mainMenuScreen);
startApp();
