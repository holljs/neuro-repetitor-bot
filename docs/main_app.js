// ЖЕЛЕЗОБЕТОННАЯ ФИКСАЦИЯ ПАРАМЕТРОВ ВК
const VK_SEARCH_PARAMS = window.location.search || window.location.hash.replace('#', '?'); 

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
const helpScreen = document.getElementById('screen-help');

// --- ТОЧНОЕ ОПРЕДЕЛЕНИЕ ПЛАТФОРМЫ ВК ---
const urlParams = new URLSearchParams(VK_SEARCH_PARAMS);
const vkPlatform = urlParams.get('vk_platform') || 'desktop_web';
const allowedPaymentPlatforms = ['desktop_web', 'mobile_web'];
const canPay = allowedPaymentPlatforms.includes(vkPlatform);

let USER_ID = urlParams.get('vk_user_id');
let currentExamType = null; 

// --- СОБСТВЕННАЯ СИСТЕМА УВЕДОМЛЕНИЙ (БЕЗ ALERT) ---
window.showCustomAlert = function(message, title = "Внимание") {
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-message').textContent = message;
    document.getElementById('custom-modal').style.display = 'flex';
};

window.closeModal = function() {
    document.getElementById('custom-modal').style.display = 'none';
};

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

const OGE_SUBJECTS = { 
    "oge_math": "Математика ОГЭ", "oge_russian": "Русский язык ОГЭ", 
    "oge_english": "Английский ОГЭ", "oge_chemistry": "Химия ОГЭ",
    "oge_physics": "Физика ОГЭ", "oge_geography": "География ОГЭ",
    "oge_biology": "Биология ОГЭ", "oge_informatics": "Информатика ОГЭ",
    "oge_history": "История ОГЭ", "oge_social": "Обществознание ОГЭ"
};

const EGE_SUBJECTS = { 
    "math_ege": "Математика (профиль)", "russian_ege": "Русский язык ЕГЭ",
    "inf_ege": "Информатика ЕГЭ", "geo_ege": "География ЕГЭ",
    "phys_ege": "Физика ЕГЭ", "ege_english": "Английский ЕГЭ",
    "chem_ege": "Химия ЕГЭ", "ege_literature": "Литература ЕГЭ"
};

const ALL_SUBJECTS = { ...OGE_SUBJECTS, ...EGE_SUBJECTS };

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
    if(screenElement) {
        screenElement.style.display = 'block';
        if (window.feather) feather.replace();
    }
}

// === ИНИЦИАЛИЗАЦИЯ VK BRIDGE ===
let isAppInitialized = false;

function finalizeInit() {
    if (isAppInitialized) return;
    isAppInitialized = true;
    
    showScreen(mainMenuScreen);

    // Безопасно получаем данные
    try {
        vkBridge.send('VKWebAppGetUserInfo')
            .then(userData => {
                if (userData && userData.id) {
                    USER_ID = userData.id;
                }
            })
            .catch(error => console.log("ВК не отдал профиль", error));
    } catch(e) {
        console.log("Ошибка вызова GetUserInfo", e);
    }
}

function startApp() {
    showScreen(mainMenuScreen); // Сразу показываем меню

    vkBridge.send('VKWebAppInit')
        .then(() => {
            console.log("VK Bridge инициализирован через Promise");
            finalizeInit();
        })
        .catch(() => console.log("VK Bridge Promise не сработал"));

    vkBridge.subscribe((e) => {
        if (e.detail.type === 'VKWebAppUpdateConfig') {
            console.log("VK Bridge инициализирован через UpdateConfig");
            finalizeInit();
        }
    });

    setTimeout(() => {
        if (!isAppInitialized) {
            console.log("VK Bridge инициализирован по таймауту");
            finalizeInit();
        }
    }, 1500);
}

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
    
    const backBtn = document.createElement('button');
    backBtn.className = 'button secondary';
    backBtn.style.marginTop = '20px';
    backBtn.innerText = '🔙 В главное меню';
    backBtn.onclick = () => showScreen(mainMenuScreen);
    subjectScreen.appendChild(backBtn);
    showScreen(subjectScreen);
};

document.querySelectorAll('#screen-main-menu .button').forEach(button => {
    button.addEventListener('click', () => {
        if (button.dataset.examType) openSubjects(button.dataset.examType);
    });
});

window.selectTariff = function(subjectCode, subjectName) {
    subjectScreen.innerHTML = `
        <h2>${subjectName}</h2>
        <p style="text-align:center; color:#555; margin-bottom:20px;">Выберите формат тренировки:</p>

        <div style="margin-bottom: 10px;">
            <button class="button" style="background-color: #4a76a8; justify-content: space-between; padding-right: 15px;" onclick="startTest('${subjectCode}', 'standard')">
                <div style="display: flex; align-items: center;">
                    <i data-feather="play-circle" class="icon-sm"></i> Стандарт (3 кредита)
                </div>
                <div onclick="event.stopPropagation(); toggleHint('hint-standard')" style="padding: 5px; margin: -5px; cursor: pointer;">
                    <i data-feather="help-circle" class="icon-sm" style="margin: 0; opacity: 0.8;"></i>
                </div>
            </button>
            
            <div id="hint-standard" class="math-hint-box" style="margin-top: 8px;">
                <b>Стандарт:</b> Нейросеть даёт одно чёткое и понятное объяснение вашей ошибки. Идеально для быстрой тренировки.
            </div>
        </div>

        <div style="margin-bottom: 20px;">
            <button class="button" style="background-color: #2a5885; justify-content: space-between; padding-right: 15px;" onclick="startTest('${subjectCode}', 'pro')">
                <div style="display: flex; align-items: center;">
                    <i data-feather="zap" class="icon-sm"></i> Профи (4 кредита)
                </div>
                <div onclick="event.stopPropagation(); toggleHint('hint-pro')" style="padding: 5px; margin: -5px; cursor: pointer;">
                    <i data-feather="help-circle" class="icon-sm" style="margin: 0; opacity: 0.8;"></i>
                </div>
            </button>
            
            <div id="hint-pro" class="math-hint-box" style="margin-top: 8px;">
                <b>Профи:</b> Глубокий разбор. Если вы не поняли с первого раза, ИИ разжуёт ошибку повторно — ещё проще и детальнее.
            </div>
        </div>

        <button class="button secondary" onclick="openSubjects(currentExamType)">
            <i data-feather="arrow-left" class="icon-sm"></i> Назад к предметам
        </button>
    `;
    if (window.feather) feather.replace(); 
};

window.toggleHint = function(id) {
    const hint = document.getElementById(id);
    if (hint) {
        hint.style.display = hint.style.display === 'block' ? 'none' : 'block';
    }
};

window.startTest = async function(subjectCode, mode) {
    currentTestMode = mode;
    showScreen(loadingScreen);
    try {
        const payResponse = await fetch(`${TEST_API_URL}/start_test_payment/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                student_id: String(USER_ID || 'guest'), 
                test_mode: currentTestMode,
                vk_params: VK_SEARCH_PARAMS
            })
        });
        const payResult = await payResponse.json();
        
        if (payResult.success) {
            currentSubjectCode = subjectCode;
            questionNumber = 1; score = 0; mistakes = [];
            getRandomTask();
        } else { 
            showCustomAlert(payResult.error || "Недостаточно кредитов", "Ошибка"); 
            showScreen(mainMenuScreen); 
        }
    } catch (e) { 
        showCustomAlert("Ошибка соединения с сервером.", "Ошибка");
        showScreen(mainMenuScreen); 
    }
};

async function getRandomTask() {
    try {
        const response = await fetch(`${TEST_API_URL}/random_task/?exam_type=${currentSubjectCode}&student_id=${USER_ID || 'guest'}&vk_params=${encodeURIComponent(VK_SEARCH_PARAMS)}`);
        currentTask = await response.json();
        if (currentTask.done) { 
            showCustomAlert(currentTask.text, "Ура!"); 
            showScreen(mainMenuScreen); 
            return; 
        }
        showTask();
    } catch (e) { 
        showCustomAlert("Ошибка при загрузке задачи.", "Ошибка");
        showScreen(mainMenuScreen); 
    }
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
    if (!userAnswer) {
        showCustomAlert("Пожалуйста, введите ответ!", "Внимание");
        return;
    }
    showScreen(loadingScreen);
    try {
        const response = await fetch(`${TEST_API_URL}/check/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                user_answer: userAnswer, 
                task_id: currentTask.id, 
                student_id: String(USER_ID || 'guest'),
                vk_params: VK_SEARCH_PARAMS
            })
        });
        const result = await response.json();
        
        if (result.correct_was) {
            currentTask.answer = result.correct_was; 
        }

        handleQuickResult(result.is_correct, rawInput); 
    } catch (error) { 
        showCustomAlert("Ошибка при проверке ответа.", "Ошибка");
        showScreen(taskScreen); 
    }
};

function handleQuickResult(isCorrect, userAnswer) {
    const titleEl = document.getElementById('quick-result-title');
    const normUser = normalizeText(userAnswer);
    const normCorrect = normalizeText(currentTask.answer);
    const finalCorrect = isCorrect || (normUser === normCorrect);
    
    if (finalCorrect) {
        titleEl.innerHTML = '<div style="color:#4CAF50; display:flex; justify-content:center; align-items:center;"><i data-feather="check-circle" style="margin-right:8px;"></i> Верно!</div>';
        score++;
    } else {
        titleEl.innerHTML = `<div style="color:#ff5252; display:flex; justify-content:center; align-items:center;"><i data-feather="x-circle" style="margin-right:8px;"></i> Неверно!</div><br><small style="color:#555;">Ожидалось: <b>${currentTask.answer || "---"}</b></small>`;
        mistakes.push({ task: currentTask, user_answer: userAnswer });
    }
    setTimeout(() => { feather.replace(); renderMath('quick-result-screen'); }, 100);
    showScreen(quickResultScreen);
}

window.abortTest = function() {
    if (confirm("Вы уверены, что хотите прервать тренировку? Прогресс этого теста не сохранится.")) {
        showScreen(mainMenuScreen);
    }
};

window.nextTask = function() {
    questionNumber++;
    if (questionNumber <= TEST_LENGTH) getRandomTask();
    else showFinishScreen();
};

function showFinishScreen() {
    document.getElementById('final-score').textContent = score;
    document.getElementById('final-mistakes').textContent = mistakes.length;
    
    const reviewBtnBlock = document.getElementById('review-buttons');
    const oldStats = document.getElementById('topic-stats');
    if (oldStats) oldStats.remove();

    if (mistakes.length > 0) {
        reviewBtnBlock.style.display = 'block';
        const aiAnalysisBlock = `
            <div id="topic-stats" style="margin-top:20px; text-align:left; background:#f0f8ff; padding:15px; border-radius:10px; border: 1px solid #bcdcff;">
                <h3 style="margin-top:0; color:#0056b3; display:flex; align-items:center;"><i data-feather="activity" class="icon-sm"></i> Умный анализ пробелов</h3>
                <p id="ai-analysis-text" style="font-size:14px; color:#333;">Хочешь узнать, какие конкретно темы и правила тебе нужно подтянуть на основе твоих ошибок?</p>
                <button id="ai-analysis-btn" class="button" style="background-color:#007bff; padding:10px; font-size:14px;" onclick="getAIAnalysis()">
                    <i data-feather="cpu" class="icon-sm"></i> Сгенерировать ИИ-анализ
                </button>
            </div>
        `;
        reviewBtnBlock.insertAdjacentHTML('beforebegin', aiAnalysisBlock);
    } else { 
        reviewBtnBlock.style.display = 'none'; 
    }
    showScreen(testFinishScreen);
}

window.getAIAnalysis = async function() {
    const btn = document.getElementById('ai-analysis-btn');
    const textBox = document.getElementById('ai-analysis-text');
    btn.style.display = 'none';
    
    textBox.innerHTML = `<div style="display:flex; align-items:center; color:#555;"><div class="spinner" style="width:16px; height:16px; border-width:2px; margin: 0 10px 0 0;"></div> <i>ИИ анализирует ошибки...</i></div>`;

    const mistakesData = mistakes.map(m => ({
        task_text: String(m.task.task_text || m.task.text || "Текст не найден"),
        user_answer: String(m.user_answer || ""),
        correct_answer: String(m.task.answer || "")
    }));

    try {
        const response = await fetch(`${TEST_API_URL}/analyze_gaps/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                mistakes: mistakesData,
                student_id: String(USER_ID || 'guest'),
                vk_params: VK_SEARCH_PARAMS
            })
        });
        const result = await response.json();
        textBox.innerHTML = `<div style="line-height: 1.5;">${result.analysis}</div>`;
    } catch (error) {
        textBox.innerHTML = `<div style="color:#d32f2f; display:flex; align-items:center;"><i data-feather="alert-triangle" class="icon-sm"></i> Ошибка соединения с сервером.</div>`;
        if (window.feather) feather.replace();
        btn.style.display = 'block';
    }
};

window.startReview = function() { currentReviewIndex = 0; loadReviewForCurrentMistake(); };

function loadReviewForCurrentMistake() {
    const mistake = mistakes[currentReviewIndex];
    document.getElementById('review-progress').textContent = `Разбор ошибки ${currentReviewIndex + 1}`;
    
    document.getElementById('review-answers-block').innerHTML = `
        <p style="display:flex; align-items:center; color:#d32f2f; font-weight:500;"><i data-feather="x-circle" class="icon-sm"></i> Твой: ${mistake.user_answer}</p>
        <p style="display:flex; align-items:center; color:#388e3c; font-weight:500;"><i data-feather="check-circle" class="icon-sm"></i> Правильный: ${mistake.task.answer}</p>
    `;
    
    const reviewImgContainer = document.getElementById('review-image-container');
    if (mistake.task.image && mistake.task.image.length > 5) {
        const fullImgUrl = mistake.task.image.startsWith('http') ? mistake.task.image : `https://neuro-master.online/${mistake.task.image}`;
        reviewImgContainer.innerHTML = `<img src="${encodeURI(fullImgUrl)}" class="question-image" style="max-width: 100%;">`;
    } else { 
        reviewImgContainer.innerHTML = `<div style="padding:15px; background:#f9f9f9;">${mistake.task.task_text || mistake.task.text}</div>`; 
    }
    document.getElementById('review-explanation').innerHTML = `<button class="submit-btn" onclick="runAIExplanation()"><i data-feather="cpu" class="icon-sm"></i> Разбор с ИИ</button>`;
    showScreen(reviewScreen);
}

window.runAIExplanation = async function(simplify = false) {
    const mistake = mistakes[currentReviewIndex];
    const explanationBox = document.getElementById('review-explanation');
    
    explanationBox.innerHTML = `<div style="display:flex; align-items:center; color:#555;"><div class="spinner" style="width:16px; height:16px; border-width:2px; margin: 0 10px 0 0;"></div> <i>Генерирую...</i></div>`;
    
    let imageUrl = mistake.task.image ? `https://neuro-master.online/${mistake.task.image}` : null;
    try {
        const response = await fetch(`${TEST_API_URL}/review/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                user_answer: String(mistake.user_answer), 
                image_url: imageUrl, 
                task_text: mistake.task.task_text || mistake.task.text || "Текст", 
                simplify: simplify,
                student_id: String(USER_ID || 'guest'),
                vk_params: VK_SEARCH_PARAMS
            })
        });
        const result = await response.json();
        explanationBox.innerHTML = `<div style="text-align:left;">${result.explanation}</div>`;
    } catch (error) { 
        explanationBox.innerHTML = `<div style="color:#d32f2f; display:flex; align-items:center;"><i data-feather="alert-triangle" class="icon-sm"></i> Ошибка при генерации разбора.</div>`;
        if (window.feather) feather.replace();
    }
};

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
};

window.finishSession = () => showScreen(mainMenuScreen);

window.allowVkMessages = function() {
    vkBridge.send("VKWebAppAllowMessagesFromGroup", {"group_id": 235924452})
        .then(() => showCustomAlert("Отлично! Теперь мы сможем присылать тебе уведомления.", "Успешно"))
        .catch(() => showCustomAlert("Вы отменили подписку на сообщения.", "Отмена"));
};

window.buyPackage = async function(creditsAmount) {
    const priceMap = { 15: 150, 100: 700 }; 
    const price = priceMap[creditsAmount];

    showScreen(loadingScreen);

    try {
        const response = await fetch(`${TEST_API_URL}/create_payment/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                student_id: String(USER_ID || 'guest'), 
                amount: creditsAmount,
                price: price,
                vk_params: VK_SEARCH_PARAMS
            })
        });
        const result = await response.json();

        if (result.success && result.confirmation_url) {
            try {
                await vkBridge.send("VKWebAppOpenUrl", {"url": result.confirmation_url});
            } catch (bridgeError) {
                console.log("VK Bridge не смог открыть ссылку, используем window.open:", bridgeError);
                window.open(result.confirmation_url, '_blank');
            }
            showProfile();
        } else {
            showCustomAlert("Не удалось создать платеж. Попробуйте позже.", "Ошибка");
            showProfile();
        }
    } catch (e) {
        showCustomAlert("Ошибка соединения с платежным шлюзом.", "Ошибка");
        showProfile();
    }
};

window.handleTopUpClick = function(amount) {
    const platform = urlParams.get('vk_platform') || 'desktop_web';
    if (platform.includes('iphone') || platform.includes('ipad') || platform.includes('android')) {
        showCustomAlert("По правилам Apple и Google пополнение баланса временно доступно только с компьютера. Откройте это приложение ВКонтакте на ПК!", "Ограничение платформы");
    } else {
        buyPackage(amount);
    }
};

window.showProfile = async function() {
    showScreen(loadingScreen);
    try {
        const response = await fetch(`${TEST_API_URL}/profile_base/?student_id=${USER_ID || 'guest'}&vk_params=${encodeURIComponent(VK_SEARCH_PARAMS)}`);
        
        if (!response.ok) {
            showCustomAlert("Ошибка безопасности VK. Перезапустите приложение.", "Доступ закрыт");
            showScreen(mainMenuScreen);
            return;
        }
        
        const data = await response.json();
        
        let topUpBlock = `
        <div style="margin-top:20px; padding:15px; background:#fff; border-radius:10px; border: 1px solid #e1e3e6;">
            <h3 style="margin-top:0; display:flex; align-items:center; justify-content:center;"><i data-feather="credit-card" class="icon-sm"></i> Пополнить баланс</h3>
            <button class="button" style="margin-bottom:10px; background-color:#4a76a8;" onclick="handleTopUpClick(15)">Пакет "Минимум" (15 кр.) — 150 руб.</button>
            <button class="button" style="background-color:#2a5885;" onclick="handleTopUpClick(100)">Пакет "Максимум" (100 кр.) — 700 руб.</button>
        </div>`;

        let subjectsHtml = '';
        if (data.active_subjects && data.active_subjects.length > 0) {
            data.active_subjects.forEach(subjCode => {
                const subjName = ALL_SUBJECTS[subjCode] || subjCode;
                subjectsHtml += `
                    <button class="exam-btn" onclick="loadSubjectAnalytics('${subjCode}', '${subjName}')">
                        <div class="exam-icon"><i data-feather="bar-chart-2"></i></div>
                        <div class="exam-info">
                            <h3>${subjName}</h3>
                            <p>Посмотреть анализ пробелов</p>
                        </div>
                    </button>`;
            });
        } else {
            subjectsHtml = `<p style="color:#777;">Здесь появится статистика, как только ты решишь первый вариант!</p>`;
        }

        subjectScreen.innerHTML = `
            <h2 style="display:flex; align-items:center; justify-content:center;"><i data-feather="user" style="margin-right:10px;"></i> Мой профиль</h2>
            
            <button class="button" style="background-color:#4a76a8; margin-bottom:15px; font-size:14px; padding:10px;" onclick="allowVkMessages()">
                <i data-feather="bell" class="icon-sm"></i> Включить уведомления
            </button>

            <div style="font-size:16px; margin-bottom:15px; background:white; padding:15px; border-radius:10px; border: 1px solid #e1e3e6; text-align: left;">
                <div style="display:flex; align-items:center; margin-bottom:10px;">
                    <i data-feather="database" class="icon-sm" style="color:#ff9800;"></i> Твой баланс: <b style="margin-left:6px;">${data.balance || 0} кр.</b>
                </div>
                <div style="display:flex; align-items:center;">
                    <i data-feather="check-square" class="icon-sm" style="color:#4CAF50;"></i> Решено задач: <b style="margin-left:6px;">${data.total_solved || 0}</b>
                </div>
            </div>
            
            <h3 style="margin-top:20px; text-align:left; display:flex; align-items:center;"><i data-feather="trending-up" class="icon-sm"></i> Моя статистика:</h3>
            <div id="analytics-container">
                ${subjectsHtml}
            </div>
            
            ${topUpBlock}
            <button class="button secondary" style="margin-top:20px;" onclick="showScreen(mainMenuScreen)"><i data-feather="arrow-left" class="icon-sm"></i> В главное меню</button>
            
            <div style="margin-top: 30px; font-size: 11px; color: #999; text-align: center; line-height: 1.4;">
                Продавец: Самозанятая Селяхова Наталья Викторовна<br>
                ИНН: 502209781184<br>
                Email: holljs@mail.ru<br>
                <a href="https://vk.com/neuro_repetitor" target="_blank" style="color: #999; text-decoration: underline;">Пользовательское соглашение и возврат</a>
            </div>
        `;
        showScreen(subjectScreen);
    } catch (e) {
        showCustomAlert("Не удалось загрузить профиль. Попробуйте позже.", "Ошибка сервера");
        showScreen(mainMenuScreen);
    }
};

window.loadSubjectAnalytics = async function(subjectCode, subjectName) {
    const container = document.getElementById('analytics-container');
    container.innerHTML = `
        <div style="text-align:center; padding: 20px;">
            <div class="spinner"></div>
            <i>ИИ пишет отчет по предмету "${subjectName}"...</i>
        </div>
    `;
    
    try {
        const response = await fetch(`${TEST_API_URL}/analyze_subject/?student_id=${USER_ID || 'guest'}&subject_key=${subjectCode}&vk_params=${encodeURIComponent(VK_SEARCH_PARAMS)}`);
        const data = await response.json();
        
        container.innerHTML = `
            <div style="padding:15px; background:#f0f8ff; border-radius:10px; border: 1px solid #bcdcff; text-align:left;">
                <h3 style="margin-top:0; color:#0056b3; display:flex; align-items:center;"><i data-feather="cpu" class="icon-sm"></i> Отчет ИИ: ${subjectName}</h3>
                <div style="font-size:14px; line-height:1.6; color:#333;">${data.analysis}</div>
                <button class="button secondary" style="margin-top:15px;" onclick="showProfile()"><i data-feather="arrow-left" class="icon-sm"></i> Назад к предметам</button>
            </div>
        `;
        if (window.feather) feather.replace(); 
    } catch(e) {
        container.innerHTML = `
            <div style="color:#d32f2f; display:flex; align-items:center; justify-content:center; padding:15px;">
                <i data-feather="alert-triangle" style="margin-right:8px;"></i> Ошибка загрузки.
            </div>
            <button class="button secondary" style="margin-top:10px;" onclick="showProfile()"><i data-feather="arrow-left" class="icon-sm"></i> Назад</button>
        `;
        if (window.feather) feather.replace();
    }
};

// Запускаем приложение!
startApp();
