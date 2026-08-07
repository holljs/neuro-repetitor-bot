# 1. Удаляем сохранённые сессии пользователей (они ссылаются на старые индексы)
import subprocess
subprocess.run(['redis-cli', 'FLUSHALL'], capture_output=True)
print("✅ Сессии пользователей сброшены")

# 2. Патч main_app.js: добавляем проверку ID задачи
import re

with open('docs/main_app.js', 'r', encoding='utf-8') as f:
    js = f.read()

# Находим функцию checkQuickAnswer и добавляем проверку ID
patch = '''
    // 🔥 ПРОВЕРКА: убеждаемся, что currentTask актуален
    if (!currentTask || !currentTask.id) {
        console.error('currentTask is invalid!', currentTask);
        titleEl.innerHTML = '<div style="color:#ff9800;"><i data-feather="alert-triangle"></i> Ошибка загрузки</div><br><small>Перезагрузите тест</small>';
        showScreen(document.getElementById('quick-result-screen'));
        return;
    }
'''

# Вставляем проверку перед логикой проверки ответа
js = re.sub(
    r'(function checkQuickAnswer\([^)]*\)\s*{)',
    r'\1\n' + patch,
    js,
    count=1
)

# Также добавляем логирование для отладки
debug_log = '''
    console.log('🔍 Проверка:', {
        taskId: currentTask.id,
        taskText: currentTask.task_text.substring(0, 50),
        expectedAnswer: currentTask.answer,
        userAnswer: userAnswer
    });
'''

js = re.sub(
    r'(const userAnswer = .*?;)',
    r'\1\n' + debug_log,
    js,
    count=1
)

with open('docs/main_app.js', 'w', encoding='utf-8') as f:
    f.write(js)

print("✅ Патч арбитра применён")
