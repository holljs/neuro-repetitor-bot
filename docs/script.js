// === script.js - ПОЛНАЯ ВЕРСИЯ С АНАЛИТИКОЙ ТЕМ И ИСПРАВЛЕННЫМИ КАВЫЧКАМИ ===

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

function showScreen(screenElement) {
    document.querySelectorAll('.screen').forEach(s => {
        if(s) s.style.display = 'none';
    });
    if(screenElement) screenElement.style.display = 'block';
}

// ПЕРЕМЕННЫЕ СОСТОЯНИЯ ТЕСТА
const TEST_LENGTH = 15;
let currentTask = null;
let currentSubjectCode = null;
let questionNumber = 1;
let score = 0;
let mistakes = []; 
let currentReviewIndex = 0;

// === ЗАПУСК И ПРОВЕРКА ПОДПИСКИ ===
async function startApp() {
    try {
        const userData = await vkBridge.send('VKWebAppGetUserInfo');
        USER_ID = userData.id;
        
        showScreen(loadingScreen);
        if(loadingScreen) loadingScreen.innerHTML = '<p>Проверяем подписку...</p>';

        const response = await fetch(`${API_SERVER_URL}/check_sub/${USER_ID}`);
        if (!response.ok) throw new Error(`Сервер вернул ошибку: ${response.status}`);
        
        const subData = await response.json();
        if (subData.subscription === "active") {
            showScreen(mainMenuScreen);
        } else {
            if(loadingScreen) loadingScreen.innerHTML = `<p>У вас нет активной подписки.</p><p>Пожалуйста, оформите ее в нашем Телеграм-боте.</p>`;
        }
    } catch (error) {
        console.error('Ошибка:', error);
        showScreen(mainMenuScreen); 
    }
}

// --- ВЫБОР ПРЕДМЕТА ---
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
        
        const backBtn = document.createElement('button');
        backBtn.className = 'button back-btn';
        backBtn.innerText = "🔙 Назад";
        backBtn.onclick = () => showScreen(mainMenuScreen);
        subjectScreen.appendChild(backBtn);
        
        showScreen(subjectScreen);
    });
});

// === ЛОГИКА ТЕСТИРОВАНИЯ ===

window.startTest = async function(subjectCode) {
    if(subjectCode === 'oge') subjectCode = 'oge_math';
    if(subjectCode === 'ege') subjectCode = 'ege_math_profile';
    
    if(loadingScreen) loadingScreen.innerHTML = "<p>Проверяем баланс и готовим тест...</p><div class='spinner'></div>";
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
            questionNumber = 1;
            score = 0;
            mistakes = [];
            getRandomTask();
        } else {
            alert("⛔ " + (payResult.error || "Недостаточно кредитов. Нужно 3 кр. для теста."));
            showScreen(mainMenuScreen);
        }
    } catch (error) {
        console.error('Ошибка оплаты:', error);
        alert('Ошибка связи с сервером при списании кредитов.');
        showScreen(mainMenuScreen);
    }
}

async function getRandomTask() {
    try {
        const response = await fetch(`${TEST_API_URL}/random_task/?exam_type=${currentSubjectCode}`);
        if(!response.ok) throw new Error("Не удалось загрузить задачу");
        
        currentTask = await response.json();
        showTask();
    } catch (error) {
        alert('Ошибка получения задачи: ' + error.message);
        showScreen(mainMenuScreen);
    }
}

function showTask() {
    document.getElementById('test-progress').textContent = `Вопрос ${questionNumber} из ${TEST_LENGTH}`;
    
    // ИСПРАВЛЕНО: Обратные кавычки для корректного отображения Base64
    document.getElementById('task-image-container').innerHTML = `<img src="${currentTask.image}" alt="Задача" style="max-width: 100%; border-radius: 8px;">`;
    
    document.getElementById('task-text').textContent = currentTask.text || "";
    document.getElementById('user-answer').value = '';
    
    showScreen(taskScreen);
}

window.submitAnswer = async function() {
    const userAnswer = document.getElementById('user-answer').value.trim();
    if (!userAnswer) return;
    
    if(loadingScreen) loadingScreen.innerHTML = "<p>Проверяю ответ...</p><div class='spinner'></div>";
    showScreen(loadingScreen);
    
    try {
       const response = await fetch(`${TEST_API_URL}/check/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_answer: userAnswer,
                image_url: currentTask.image.split(',')[1], 
                task_text: currentTask.text, 
                student_id: USER_ID || 12345
            })
        });
        
        const result = await response.json();
        handleQuickResult(result.is_correct, userAnswer);
    } catch (error) {
        alert('Ошибка проверки ответа: ' + error.message);
        showScreen(taskScreen);
    }
}

function handleQuickResult(isCorrect, userAnswer) {
    const titleEl = document.getElementById('quick-result-title');
    
    if (isCorrect) {
        titleEl.textContent = '🎉 Верно!';
        titleEl.style.color = 'green';
        score++;
    } else {
        titleEl.textContent = '❌ Неверно!';
        titleEl.style.color = 'red';
        mistakes.push({ task: currentTask, user_answer: userAnswer });
    }
    
    showScreen(quickResultScreen);
}

window.nextTask = function() {
    questionNumber++;
    if (questionNumber <= TEST_LENGTH) {
        if(loadingScreen) loadingScreen.innerHTML = "<p>Грузим вопрос...</p><div class='spinner'></div>";
        showScreen(loadingScreen);
        getRandomTask();
    } else {
        showFinishScreen();
    }
}

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
        statsHTML = `<div id="topic-stats">
                        <b>🚩 Рекомендуем повторить темы:</b><ul>`;
        for (let topic in topicAnalysis) {
            statsHTML += `<li>${topic} (${topicAnalysis[topic]} ошиб.)</li>`;
        }
        statsHTML += `</ul></div>`;
    }

    const oldStats = document.getElementById('topic-stats');
    if (oldStats) oldStats.remove();
    
    const reviewBtnBlock = document.getElementById('review-buttons');
    if (mistakes.length > 0) {
        reviewBtnBlock.style.display = 'block';
        reviewBtnBlock.insertAdjacentHTML('beforebegin', statsHTML);
    } else {
        reviewBtnBlock.style.display = 'none';
    }
    
    showScreen(testFinishScreen);
}

window.startReview = function() {
    currentReviewIndex = 0;
    loadReviewForCurrentMistake();
}

function loadReviewForCurrentMistake() {
    const mistake = mistakes[currentReviewIndex];
    document.getElementById('review-progress').textContent = `Разбор ошибки ${currentReviewIndex + 1} из ${mistakes.length}`;
    
    const answersBlock = document.getElementById('review-answers-block');
    if (answersBlock) {
        answersBlock.innerHTML = `
            <p><b>❌ Твой ответ:</b> <span style="color:red;">${mistake.user_answer}</span></p>
            <p><b>✅ Правильный ответ:</b> <span style="color:green;">${mistake.task.answer || "см. в разборе"}</span></p>
        `;
    }
    
    document.getElementById('review-image-container').innerHTML = `<img src="${mistake.task.image}" style="max-width: 100%; border-radius: 8px;">`;
    document.getElementById('review-explanation').innerHTML = `
        <button class="button" onclick="runAIExplanation()">🧠 Разбор этой задачи с ИИ</button>
    `;
    
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
                image_url: mistake.task.image.split(',')[1], 
                task_text: mistake.task.text,
                simplify: simplify
            })
        });
        
        const result = await response.json();
        explanationBox.innerHTML = result.explanation;
    } catch (error) {
        explanationBox.innerHTML = `<span style="color:red;">Ошибка сервера.</span>`;
    }
}

window.nextReview = function() {
    currentReviewIndex++;
    if (currentReviewIndex < mistakes.length) {
        loadReviewForCurrentMistake();
    } else {
        alert("Все разборы окончены!");
        showScreen(mainMenuScreen);
    }
}

window.finishSession = function() { showScreen(mainMenuScreen); }
window.showHelp = function() { alert('Помощь в разработке...'); }
window.showProfile = function() { alert('Профиль в разработке...'); }

// Функция для увеличения картинки при клике
document.addEventListener('click', function (e) {
    // Проверяем, что кликнули именно по картинке задачи
    if (e.target.tagName === 'IMG' && (e.target.classList.contains('question-image') || e.target.classList.contains('task-img'))) {
        const fullScreen = document.createElement('div');
        // Стили для затемнения экрана и центрирования картинки
        fullScreen.style = "position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.9); z-index:1000; display:flex; align-items:center; justify-content:center; cursor:zoom-out;";
        fullScreen.innerHTML = `<img src="${e.target.src}" style="max-width:95%; max-height:95%; object-fit:contain; border: 2px solid white;">`;
        
        // Закрываем при повторном клике
        fullScreen.onclick = () => fullScreen.remove();
        document.body.appendChild(fullScreen);
    }
});

// САМАЯ ВАЖНАЯ СТРОЧКА В КОНЦЕ
startApp();
