"""Test Claude API"""
import anthropic
import sys
import io

# Fix pro Windows konzoli
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import config

print("🧪 Test Claude API")
print(f"API klíč: {config.CLAUDE_API_KEY[:20]}...")

try:
    client = anthropic.Anthropic(api_key=config.CLAUDE_API_KEY)

    print("\n📡 Zkouším základní volání...")

    message = client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=50,
        messages=[{
            "role": "user",
            "content": "Odpověz jedním slovem: Funguje to?"
        }]
    )

    print(f"✅ API funguje!")
    print(f"Odpověď: {message.content[0].text}")
    print(f"Model: claude-3-haiku-20240307")

except Exception as e:
    print(f"❌ Chyba: {e}")
