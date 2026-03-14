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
    
    document.getElementById('task-text').textContent = current
