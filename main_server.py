import os
import time
import logging
import random
import json
import re
import sqlite3
import httpx
import aiohttp
import asyncio
import hmac
import hashlib
import base64
import uuid
from urllib.parse import urlencode, parse_qsl
from pathlib import Path
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from yookassa import Configuration, Payment

load_dotenv()

app = FastAPI(title="Neuro Repetitor API", version="3.1.0")

# Настройка ЮKassa
Configuration.configure(
    os.getenv("YUKASSA_SHOP_ID", "TEST_ID"),
    os.getenv("YUKASSA_SECRET_KEY", "TEST_KEY")
)

VK_APP_SECRET = os.getenv("VK_APP_SECRET", "ТВОЙ_СЕКРЕТНЫЙ_КЛЮЧ_ВК")
INTERNAL_BOT_TOKEN = os.getenv("INTERNAL_BOT_TOKEN", "tg-super-secret-password-2026-xyz")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
TOKENROUTER_API_TOKEN = os.getenv("TOKENROUTER_API_TOKEN")  #  ДОБАВЛЕНО

request_times = {}
rate_lock = asyncio.Lock()

async def check_rate_limit(user_id: str, limit: int = 3, window: int = 5) -> bool:
    async with rate_lock:
        now = time.time()
        times = request_times.get(user_id, [])
        times = [t for t in times if now - t < window]
        if len(times) >= limit:
            return False
        times.append(now)
        request_times[user_id] = times
        return True

# ... (остальной код TOPIC_NAMES и остальное без изменений) ...

# =========================================================================
# 🔥 УНИВЕРСАЛЬНЫЙ ИИ-ДВИЖОК С TOKENROUTER + FALLBACK
# =========================================================================

async def ask_tokenrouter(
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 1000,
    response_json: bool = False,
    image_url: Optional[str] = None
) -> str:
    """
    Основной вызов через TokenRouter (дешёвый и быстрый)
    """
    if not TOKENROUTER_API_TOKEN:
        raise Exception("TOKENROUTER_API_TOKEN не настроен в .env")
    
    headers = {
        "Authorization": f"Bearer {TOKENROUTER_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    messages = [{"role": "system", "content": system_prompt}]
    
    # Поддержка vision (если есть картинка)
    if image_url and image_url.strip().lower() not in ["", "none", "null"]:
        user_content = [
            {"type": "text", "text": user_prompt},
            {"type": "image_url", "image_url": {"url": image_url}}
        ]
        messages.append({"role": "user", "content": user_content})
    else:
        messages.append({"role": "user", "content": user_prompt})
    
    if response_json:
        messages.append({"role": "system", "content": "Отвечай СТРОГО в формате валидного JSON объекта без любого другого текста вокруг."})
    
    payload = {
        "model": model_name,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.1 if response_json else 0.3
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.tokenrouter.com/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=30.0  #  Увеличенный таймаут
            )
            
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
            else:
                raise Exception(f"TokenRouter вернул код {response.status_code}: {response.text[:100]}")
    except Exception as e:
        logging.warning(f"⚠️ TokenRouter недоступен: {e}")
        raise e


async def ask_replicate(
    system_prompt: str,
    user_prompt: str,
    image_url: Optional[str] = None,
    max_tokens: int = 1000,
    response_json: bool = False
) -> str:
    """
    🔥 ИСПРАВЛЕНО: Сначала пробуем TokenRouter, потом Replicate (fallback)
    """
    has_image = image_url and image_url.strip().lower() not in ["", "none", "null"]
    
    #  ПРИОРИТЕТ 1: TokenRouter (дешёвый и быстрый)
    if TOKENROUTER_API_TOKEN:
        try:
            # Для текстовых задач — DeepSeek, для vision — Qwen
            if has_image:
                model_name = "qwen/qwen3.7-plus"  # Зрячая модель
            else:
                model_name = "deepseek/deepseek-v4-flash"  # Супербыстрая текстовая
            
            logging.info(f"🚀 Запрос в TokenRouter ({model_name})...")
            return await ask_tokenrouter(
                model_name=model_name,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=max_tokens,
                response_json=response_json,
                image_url=image_url
            )
        except Exception as tr_err:
            logging.warning(f"⚠️ TokenRouter не ответил: {tr_err}. Переключаемся на Replicate!")
    
    # 🔥 ПРИОРИТЕТ 2: Replicate (fallback, если TokenRouter недоступен)
    if not REPLICATE_API_TOKEN:
        logging.error("❌ Ошибка: REPLICATE_API_TOKEN не найден в .env!")
        raise Exception("REPLICATE_API_TOKEN не настроен.")
    
    headers = {
        "Authorization": f"Bearer {REPLICATE_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    if has_image:
        model_name = "google/gemini-1.5-flash"  # Мультимодальная
        payload = {
            "input": {
                "prompt": f"{system_prompt}\n{user_prompt}",
                "image": image_url,
                "max_tokens": max_tokens,
                "temperature": 0.2 if response_json else 0.4
            }
        }
    else:
        model_name = "openai/gpt-4.1-nano"  # Супербыстрая текстовая
        prompt_text = f"{system_prompt}\n{user_prompt}"
        if response_json:
            prompt_text += "\nОтвечай СТРОГО в формате валидного JSON объекта без любого другого текста вокруг."
        payload = {
            "input": {
                "prompt": prompt_text,
                "max_tokens": max_tokens,
                "temperature": 0.1 if response_json else 0.4
            }
        }
    
    url = f"https://api.replicate.com/v1/models/{model_name}/predictions"
    max_attempts = 3
    
    for attempt in range(max_attempts):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=30.0)
                if response.status_code in [200, 201]:
                    prediction = response.json()
                    get_url = prediction.get("urls", {}).get("get")
                    if not get_url:
                        break
                    
                    # Ожидание результата генерации (Polling)
                    for _ in range(35):
                        await asyncio.sleep(0.8)
                        async with httpx.AsyncClient() as client:
                            poll_resp = await client.get(get_url, headers=headers, timeout=10.0)
                            if poll_resp.status_code == 200:
                                poll_data = poll_resp.json()
                                status = poll_data.get("status")
                                if status == "succeeded":
                                    output = poll_data.get("output", "")
                                    if isinstance(output, list):
                                        return "".join(output).strip()
                                    return str(output).strip()
                                elif status in ["failed", "canceled"]:
                                    logging.error(f"❌ Replicate статус ошибки: {poll_data.get('error')}")
                                    break
                else:
                    logging.warning(f"⚠️ Ошибка от Replicate API ({response.status_code}): {response.text[:100]}")
        except Exception as exc:
            logging.warning(f"⚠️ Ошибка сети Replicate (попытка {attempt + 1}): {exc}")
            if attempt == max_attempts - 1:
                break
            await asyncio.sleep(1.0)
    
    return '{"is_correct": false}' if response_json else "Ошибка генерации ответа ИИ."


# =========================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ И АВТОРИЗАЦИЯ
# =========================================================================

def verify_vk_auth(student_id: str, vk_params: str) -> bool:
    if vk_params == INTERNAL_BOT_TOKEN:
        return True
    if not vk_params or "sign=" not in vk_params:
        return False
    query_params = dict(parse_qsl(vk_params.lstrip('?'), keep_blank_values=True))
    vk_params_dict = {k: v for k, v in query_params.items() if k.startswith('vk_')}
    sorted_vk_params = dict(sorted(vk_params_dict.items()))
    encoded_params = urlencode(sorted_vk_params)
    hash_code = hmac.new(VK_APP_SECRET.encode('utf-8'), encoded_params.encode('utf-8'), hashlib.sha256).digest()
    expected_sign = base64.urlsafe_b64encode(hash_code).decode('utf-8').rstrip('=')
    return query_params.get('sign') == expected_sign

async def send_vk_message(user_id: str, message: str):
    vk_token = os.getenv("VK_REPETITOR_TOKEN")
    if not vk_token:
        return False
    url = "https://api.vk.com/method/messages.send"
    params = {
        "user_id": user_id,
        "message": message,
        "random_id": random.randint(1, 2147483647),
        "v": "5.131",
        "access_token": vk_token
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=params) as resp:
                result = await resp.json()
                return "error" not in result
    except Exception:
        return False

# ... (остальной код без изменений до конца файла) ...
