// === script.js - С УМНЫМ ТЕСТИРОВАНИЕМ И РАЗБОРОМ ОШИБОК ===

const API_SERVER_URL = "https://neuro-master.online";
const TEST_API_URL = "https://neuro-master.online/repetitor-api"; // Путь для задач

vkBridge.send('VKWebAppInit');

// Экраны (убедитесь, что эти ID есть в вашем index.html)
const loadingScreen = document.getElementById('screen-loading');
const mainMenuScreen = document.getElementById('screen-main-menu');
const subjectScreen = document.getElementById('screen-subjects');

// Новые экраны для тестирования
const taskScreen = document.getElementById('task-screen');
const quickResultScreen = document.getElementById('quick-result-screen');
const testFinishScreen = document.getElementById('test-finish-screen');
const reviewScreen = document.getElementById('review-screen');

let USER_ID = null;

const OGE_SUBJECTS = { "oge_russian": "🇷🇺 Русский язык", "oge_math": "🧮 Математика" };
const EGE_SUBJECTS = { "ege_russian": "🇷🇺 Русский язык", "ege_math_profile": "📐 Математика (профиль)" };

function showScreen(screenElement) {
    document.querySelectorAll('.screen').forEach(s => {
        if(s) s.style.display = 'none'; // Скрываем все
    });
    if(screenElement) screenElement.style.display = 'block'; // Показываем нужный
}

// --- ПЕРЕМЕННЫЕ СОСТОЯНИЯ ТЕСТА ---
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
        loadingScreen.innerHTML = '<p>Проверяем подписку...</p>';

        const response = await fetch(`${API_SERVER_URL}/check_sub/${USER_ID}`);
        if (!response.ok) throw new Error(`Сервер вернул ошибку: ${response.status}`);
        
        const subData = await response.json();
        if (subData.subscription === "active") {
            showScreen(mainMenuScreen);
        } else {
            loadingScreen.innerHTML = `<p>У вас нет активной подписки.</p><p>Пожалуйста, оформите ее в нашем Телеграм-боте.</p>`;
        }
    } catch (error) {
        console.error('Ошибка:', error);
        loadingScreen.innerHTML = `<p>Ошибка соединения с сервером.</p><p>Проверьте интернет-соединение.</p>`;
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
            btn.onclick = () => startTest(code); // Начинаем тест!
            subjectScreen.appendChild(btn);
        }
        
        // Кнопка назад
        const backBtn = document.createElement('button');
        backBtn.className = 'button back-btn';
        backBtn.innerText = "🔙 Назад";
        backBtn.onclick = () => showScreen(mainMenuScreen);
        subjectScreen.appendChild(backBtn);
        
        showScreen(subjectScreen);
    });
});

// === ЛОГИКА ТЕСТИРОВАНИЯ ===

function startTest(subjectCode) {
    currentSubjectCode = subjectCode;
    questionNumber = 1;
    score = 0;
    mistakes = [];
    
    loadingScreen.innerHTML = "<p>Ищем задачу...</p><div class='spinner'></div>";
    showScreen(loadingScreen);
    getRandomTask();
}

async function getRandomTask() {
    try {
        // Запрашиваем задачу по выбранному предмету (например, exam_type=oge_math)
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
    document.getElementById('task-image-container').innerHTML = `<img src="${currentTask.image}" alt="Задача" style="max-width: 100%; border-radius: 8px;">`;
    document.getElementById('task-text').textContent = currentTask.text || "";
    document.getElementById('user-answer').value = '';
    
    showScreen(taskScreen);
}

// ОТПРАВКА ОТВЕТА
async function submitAnswer() {
    const userAnswer = document.getElementById('user-answer').value.trim();
    if (!userAnswer) return;
    
    loadingScreen.innerHTML = "<p>Проверяю ответ...</p><div class='spinner'></div>";
    showScreen(loadingScreen);
    
    try {
       const response = await fetch(`${TEST_API_URL}/check/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_answer: userAnswer,
                image_url: currentTask.image.split(',')[1], 
                task_text: currentTask.text, 
                student_id: USER_ID
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
        loadingScreen.innerHTML = "<p>Грузим вопрос...</p><div class='spinner'></div>";
        showScreen(loadingScreen);
        getRandomTask();
    } else {
        showFinishScreen();
    }
}

function showFinishScreen() {
    document.getElementById('final-score').textContent = score;
    document.getElementById('final-mistakes').textContent = mistakes.length;
    
    const reviewBtnBlock = document.getElementById('review-buttons');
    if (mistakes.length > 0) {
        reviewBtnBlock.style.display = 'block';
    } else {
        reviewBtnBlock.style.display = 'none';
    }
    
    showScreen(testFinishScreen);
}

// === РАЗБОР ОШИБОК ===

window.startReview = function() {
    currentReviewIndex = 0;
    loadReviewForCurrentMistake();
}

async function loadReviewForCurrentMistake(simplify = false) {
    const mistake = mistakes[currentReviewIndex];
    
    document.getElementById('review-progress').textContent = `Разбор ошибки ${currentReviewIndex + 1} из ${mistakes.length}`;
    document.getElementById('review-user-answer').textContent = mistake.user_answer;
    document.getElementById('review-image-container').innerHTML = `<img src="${mistake.task.image}" style="max-width: 100%; border-radius: 8px;">`;
    document.getElementById('review-explanation').innerHTML = "<i>⏳ Нейросеть пишет подробное объяснение. Подождите 10-20 секунд...</i>";
    
    showScreen(reviewScreen);

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
        document.getElementById('review-explanation').innerHTML = result.explanation;
    } catch (error) {
        document.getElementById('review-explanation').innerHTML = `<span style="color:red;">Ошибка связи с сервером.</span>`;
    }
}

window.simplifyReview = function() {
    document.getElementById('review-explanation').innerHTML = "<i>⏳ Прошу нейросеть объяснить проще...</i>";
    loadReviewForCurrentMistake(true);
}

window.nextReview = function() {
    currentReviewIndex++;
    if (currentReviewIndex < mistakes.length) {
        loadReviewForCurrentMistake();
    } else {
        alert("Все ошибки разобраны! Вы молодец!");
        showScreen(mainMenuScreen);
    }
}

window.finishSession = function() {
    showScreen(mainMenuScreen);
}

// Запуск
startApp();
