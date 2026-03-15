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

// ПЕРЕМЕННЫЕ СОСТОЯНИЯ
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

// Кнопки меню
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

function showTask() {
    document.getElementById('test-progress').textContent = `Вопрос ${questionNumber} из ${TEST_LENGTH}`;
    const imageContainer = document.getElementById('task-image-container');
    const taskTextElement = document.getElementById('task-text');

    // Очистка номера (удаляет "27." или "Решите 27.")
    if (currentTask.text) {
        let cleanText = currentTask.text.replace(/Решите уравнения\s*/gi, '')
                                      .replace(/^\d+[\.\)]\s*/, '')
                                      .replace(/\s\d+[\.\)]\s/, ' ')
                                      .trim();
        taskTextElement.textContent = cleanText;
        taskTextElement.style.display = 'block';
    } else { taskTextElement.style.display = 'none'; }

    if (currentTask.image && currentTask.image.length > 50) {
        imageContainer.innerHTML = `<img src="${currentTask.image}" class="question-image" style="max-width: 100%; border-radius: 8px;">`;
        imageContainer.style.display = 'block';
    } else { imageContainer.style.display = 'none'; }

    document.getElementById('user-answer').value = '';
    showScreen(taskScreen);
}

// ВОТ ЭТА ФУНКЦИЯ МОГЛА СЛОМАТЬСЯ
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
        titleEl.innerHTML = `<span style="color:red">❌ Неверно!</span><br><small>Ожидалось: ${currentTask.answer || 'не указано'}</small>`;
        mistakes.push({ task: currentTask, user_answer: userAnswer });
    }
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
    showScreen(testFinishScreen);
}

window.startReview = function() { currentReviewIndex = 0; loadReviewForCurrentMistake(); }

function loadReviewForCurrentMistake() {
    const mistake = mistakes[currentReviewIndex];
    document.getElementById('review-progress').textContent = `Разбор ошибки ${currentReviewIndex + 1}`;
    document.getElementById('review-answers-block').innerHTML = `
        <p><b>❌ Твой ответ:</b> ${mistake.user_answer}</p>
        <p><b>✅ Правильный ответ:</b> ${mistake.task.answer || "---"}</p>`;
    showScreen(reviewScreen);
}

window.finishSession = () => showScreen(mainMenuScreen);

startApp();
