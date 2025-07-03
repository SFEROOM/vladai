import openai
from config import OPENAI_API_KEY

# Устанавливаем API ключ
openai.api_key = OPENAI_API_KEY

try:
    # Пытаемся сделать простой запрос
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say hello"}
        ],
        max_tokens=10
    )
    
    print("✅ API работает!")
    print(f"Ответ: {response['choices'][0]['message']['content']}")
    
except openai.error.AuthenticationError as e:
    print("❌ Ошибка аутентификации: неверный API ключ")
    print(f"Детали: {e}")
    
except openai.error.RateLimitError as e:
    print("❌ Превышен лимит запросов")
    print(f"Детали: {e}")
    
except Exception as e:
    print(f"❌ Ошибка: {type(e).__name__}")
    print(f"Детали: {e}") 