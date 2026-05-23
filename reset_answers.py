import json

def reset_answers():
    print("🧹 Стираем старые некрасивые ответы...")
    with open("questions/history_ege.json", "r", encoding="utf-8") as f:
        tasks = json.load(f)

    for t in tasks:
        t["answer"] = ""

    with open("questions/history_ege.json", "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=4)

    print("✅ База обнулена и готова к новому решению!")

if __name__ == "__main__":
    reset_answers()
