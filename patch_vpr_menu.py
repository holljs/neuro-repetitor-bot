path = 'docs/main_app.js'
src = open(path, encoding='utf-8').read()

block = '''
const VPR_GRADE_SUBJECTS = {
    4: { "math": "Математика", "russian": "Русский язык", "english": "Английский", "german": "Немецкий", "french": "Французский", "okr": "Окружающий мир", "literary": "Лит. чтение" },
    5: { "math": "Математика", "russian": "Русский язык", "biology": "Биология", "history": "История", "geography": "География", "english": "Английский", "german": "Немецкий", "french": "Французский", "literature": "Литература" },
    6: { "math": "Математика", "russian": "Русский язык", "biology": "Биология", "history": "История", "geography": "География", "english": "Английский", "german": "Немецкий", "french": "Французский", "literature": "Литература" },
    7: { "math": "Математика", "russian": "Русский язык", "physics": "Физика", "informatics": "Информатика", "biology": "Биология", "history": "История", "geography": "География", "english": "Английский", "german": "Немецкий", "french": "Французский", "literature": "Литература" },
    8: { "math": "Математика", "russian": "Русский язык", "physics": "Физика", "chemistry": "Химия", "informatics": "Информатика", "biology": "Биология", "history": "История", "geography": "География", "english": "Английский", "german": "Немецкий", "french": "Французский", "literature": "Литература" },
    10: { "math": "Математика", "russian": "Русский язык", "physics": "Физика", "chemistry": "Химия", "biology": "Биология", "history": "История", "geography": "География", "english": "Английский", "german": "Немецкий", "french": "Французский", "social": "Обществознание", "literature": "Литература" }
};

window.showVprGrades = function() {
    const s = document.getElementById('screen-subjects');
    let html = '<h1>ВПР: выбери класс</h1><div style="display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-bottom:20px;">';
    [4,5,6,7,8,10].forEach(g => { html += '<button class="button" onclick="showVprSubjects(' + g + ')">' + g + ' класс</button>'; });
    html += '</div><button class="button secondary" onclick="showScreen(document.getElementById(\\'screen-main-menu\\'))">🔙 В главное меню</button>';
    s.innerHTML = html;
    showScreen(s);
};

window.showVprSubjects = function(grade) {
    const s = document.getElementById('screen-subjects');
    s.innerHTML = '<h1>ВПР, ' + grade + ' класс</h1>';
    const subs = VPR_GRADE_SUBJECTS[grade] || {};
    for (const code in subs) {
        const btn = document.createElement('button');
        btn.className = 'button';
        btn.innerText = subs[code];
        btn.onclick = () => selectTariff('vpr_' + code + '_' + grade, 'ВПР: ' + subs[code] + ', ' + grade + ' кл.');
        s.appendChild(btn);
    }
    const back = document.createElement('button');
    back.className = 'button secondary';
    back.style.marginTop = '20px';
    back.innerText = '⬅️ Назад к классам';
    back.onclick = () => showVprGrades();
    s.appendChild(back);
    showScreen(s);
};
'''

if 'showVprGrades' not in src:
    src = src.replace('const TEST_LENGTH = 10;', block + '\nconst TEST_LENGTH = 10;')

if "showVprGrades(); return;" not in src:
    if "else if (examType === 'vpr')" in src:
        src = src.replace("else if (examType === 'vpr') subjects = VPR_SUBJECTS;", "else if (examType === 'vpr') { showVprGrades(); return; }")
    else:
        src = src.replace("else if (examType === 'olymp') subjects = OLYMP_SUBJECTS;", "else if (examType === 'olymp') subjects = OLYMP_SUBJECTS;\n    else if (examType === 'vpr') { showVprGrades(); return; }")

ins = '''console.log("🚀 [APP] Инициализация интерфейса...");
    try {
        const menu = document.getElementById('screen-main-menu');
        if (menu && !menu.querySelector('[data-exam-type="vpr"]')) {
            const anchor = menu.querySelector('[data-exam-type="olymp"]') || menu.querySelector('.button');
            if (anchor) {
                const b = document.createElement('button');
                b.className = 'button';
                b.dataset.examType = 'vpr';
                b.innerHTML = '📋 ВПР (4–10 классы)';
                b.addEventListener('click', () => openSubjects('vpr'));
                anchor.insertAdjacentElement('afterend', b);
            }
        }
    } catch(e) {}'''
src = src.replace('console.log("🚀 [APP] Инициализация интерфейса...");', ins, 1)

open(path, 'w', encoding='utf-8').write(src)
print('✅ main_app.js: меню ВПР с классами готово!')
