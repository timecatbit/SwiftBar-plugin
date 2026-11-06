"""Display catalog. Membership, API configuration and usage are separate facts.

A portal capability is intentionally not a quota collector: its API key is only
sent for an explicit, read-only key check. Never infer a paid membership or
report a synthetic balance.
"""
from typing import NamedTuple

# Keep category identifiers stable while explaining what each group measures.
GROUP_LABELS = {'Harness': 'Harness Token 用量', '订阅': '订阅用量', 'API': 'API'}

class Service(NamedTuple):
    key: str
    brand: str
    category: str
    url: str
    credential: str = ''
    capability: str = 'portal'

    @property
    def label(self):
        return self.brand + (' 订阅' if self.category == '订阅' else ' API')

SERVICES = (
    Service('chatgpt', 'ChatGPT', '订阅', 'https://chatgpt.com', capability='client'),
    Service('claude-subscription', 'Claude', '订阅', 'https://claude.ai/settings/usage', capability='desktop-usage'),
    Service('minimax', 'MiniMax', '订阅', 'https://platform.minimax.io/user-center/payment/token-plan', 'MINIMAX_API_KEY', 'quota'),
    Service('gemini-subscription', 'Gemini', '订阅', 'https://gemini.google.com'),
    Service('grok-subscription', 'Grok', '订阅', 'https://grok.com'),
    Service('kimi-subscription', 'Kimi', '订阅', 'https://www.kimi.com'),
    Service('chatgpt-api', 'ChatGPT', 'API', 'https://platform.openai.com/usage', 'OPENAI_API_KEY'),
    Service('claude-api', 'Claude', 'API', 'https://platform.claude.com/usage', 'ANTHROPIC_API_KEY', 'cost'),
    Service('deepseek', 'DeepSeek', 'API', 'https://platform.deepseek.com/usage', 'DEEPSEEK_API_KEY', 'balance'),
    Service('minimax-api', 'MiniMax', 'API', 'https://platform.minimax.io/user-center/payment/balance', 'MINIMAX_PLATFORM_API_KEY'),
    Service('gemini-api', 'Gemini', 'API', 'https://aistudio.google.com/usage', 'GEMINI_API_KEY'),
    Service('grok', 'Grok', 'API', 'https://console.x.ai', 'XAI_MANAGEMENT_API_KEY', 'balance'),
    Service('kimi-api', 'Kimi', 'API', 'https://platform.moonshot.cn/console/account', 'MOONSHOT_API_KEY', 'balance'),
)
BY_KEY = {s.key: s for s in SERVICES}
MANUAL_SUBSCRIPTIONS = tuple(s.key for s in SERVICES if s.category == '订阅' and s.capability == 'portal')
PORTAL_APIS = tuple(s.key for s in SERVICES if s.category == 'API' and s.capability == 'portal')
# A key alone configures these; DeepSeek can also come from OpenCodex and Grok needs a Team ID.
KEY_ONLY_APIS = tuple(s.key for s in SERVICES if s.category == 'API' and s.key not in ('deepseek', 'grok'))
API_KEYS = {s.key: s.credential for s in SERVICES if s.credential}
# These aliases only identify API configuration; they never imply subscription.
KEY_ALIASES = {'gemini-api': ('GOOGLE_API_KEY',)}

def credential_names(key):
    primary = API_KEYS.get(key)
    return ((primary,) if primary else ()) + KEY_ALIASES.get(key, ())
