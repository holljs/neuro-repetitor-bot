// === script.js - ФИНАЛЬНАЯ РАБОЧАЯ ВЕРСИЯ ===

// !!! УБЕДИТЕСЬ, ЧТО ЗДЕСЬ ПРАВИЛЬНЫЙ URL !!!
// Для локального тестирования:
// const API_SERVER_URL = "http://localhost:8002";
// Для продакшена:
const API_SERVER_URL = "https://neuro-master.online";

vkBridge.send('VKWebAppInit');

const loadingScreen = document.getElementById('screen-loading');
const mainMenuScreen = document.getElementById('screen-main-menu');
const subjectScreen = document.getElementById('screen-subjects');

const OGE_SUBJECTS = {
    "oge_russian": "🇷🇺 Русский язык",
    "oge_math": "🧮 Математика"
};
const EGE_SUBJECTS = {
    "ege_russian": "🇷🇺 Русский язык",
    "ege_math_profile": "📐 Математика (профиль)"
};

function showScreen(screenElement) {
    document.querySelectorAll('.screen').forEach(s => s.style.display = 'none');
    screenElement.style.display = 'block';
}

async function startTest(subjectCode) {
    // TODO: Реализовать запуск теста (например, переход на страницу с вопросами)
    console.log(`Запуск теста по предмету: ${subjectCode}`);
    // alert(`Запуск теста по предмету: ${subjectCode}`); // Временная заглушка
}

async function startApp() {
    try {
        const userData = await vkBridge.send('VKWebAppGetUserInfo');
        showScreen(loadingScreen);
        loadingScreen.innerHTML = '<p>Проверяем подписку...</p>';

        const response = await fetch(`${API_SERVER_URL}/check_sub/${userData.id}`);
        if (!response.ok) {
            throw new Error(`Сервер вернул ошибку: ${response.status}`);
        }

        const subData = await response.json();

        if (subData.subscription === "active") {
            showScreen(mainMenuScreen);
        } else {
            loadingScreen.innerHTML = `
                <p>У вас нет активной подписки.</p>
                <p>Пожалуйста, оформите ее в нашем Телеграм-боте.</p>
            `;
        }
    } catch (error) {
        console.error('Ошибка:', error);
        loadingScreen.innerHTML = `
            <p>Ошибка соединения с сервером.</p>
            <p>Проверьте интернет-соединение и убедитесь, что сервер запущен.</p>
            <p>Ошибка: ${error.message}</p>
        `;
    }
}

// Обработчики кнопок выбора экзамена (ОГЭ/ЕГЭ)
document.querySelectorAll('#screen-main-menu .button').forEach(button => {
    button.addEventListener('click', () => {
        const examType = button.dataset.examType;
        const subjects = (examType === 'ege') ? EGE_SUBJECTS : OGE_SUBJECTS;
        
        subjectScreen.innerHTML = `<h1>Выберите предмет</h1>`;
        for (const code in subjects) {
            const btn = document.createElement('button');
            btn.className = 'button';
            btn.innerText = subjects[code];
            btn.onclick = () => startTest(code); // Запуск теста по выбранному предмету
            subjectScreen.appendChild(btn);
        }
        showScreen(subjectScreen);
    });
});

// Запуск приложения
startApp();
