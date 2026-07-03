"""Smoke check Claude API — ruční diagnostický skript (NENÍ pytest test).

Volá ostré API (stojí tokeny). Spouštět ručně:
    venv/bin/python scripts/check_api.py
"""
import anthropic
import sys
import io
import os

# Fix pro Windows konzoli
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Skript žije ve scripts/ — přidej projektový root do sys.path kvůli `import config`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

print("🧪 Test Claude API")
print(f"API klíč: {config.CLAUDE_API_KEY[:20]}...")

try:
    client = anthropic.Anthropic(api_key=config.CLAUDE_API_KEY)

    print("\n📡 Zkouším základní volání...")

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=50,
        messages=[{
            "role": "user",
            "content": "Odpověz jedním slovem: Funguje to?"
        }]
    )

    print(f"✅ API funguje!")
    print(f"Odpověď: {message.content[0].text}")
    print(f"Model: claude-sonnet-4-6")

except Exception as e:
    print(f"❌ Chyba: {e}")
