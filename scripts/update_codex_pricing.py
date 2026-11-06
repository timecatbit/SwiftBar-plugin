#!/usr/bin/env python3
"""Regenerate lib/codex-pricing.json from a ccusage checkout (MIT, see lib/CCUSAGE_LICENSE).

Only OpenAI models that Codex logs can name are kept. Prices are USD per million
tokens; missing cache prices use ccusage's defaults (read 10%, write 125% of input).
"""
import argparse
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OPENAI = re.compile(r'(?:gpt-|o\d|codex-|chatgpt-)[^/@:]*')


def rates(cost):
    data = {'input': cost['input'], 'output': cost['output'],
            'cacheRead': cost.get('cache_read', cost['input'] * 0.1),
            'cacheWrite': cost.get('cache_write', cost['input'] * 1.25)}
    return {key: round(value, 6) for key, value in data.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ccusage', type=Path, help='Path to a ccusage git checkout')
    args = parser.parse_args()
    repo = args.ccusage.resolve()
    snapshot = json.loads((repo / 'rust/crates/ccusage-pricing-snapshots/src/models-dev-pricing.json').read_text())
    models = {}
    for name, entry in sorted(snapshot.items()):
        cost = entry.get('cost') or {}
        if not OPENAI.fullmatch(name) or not {'input', 'output'} <= set(cost):
            continue
        models[name] = rates(cost)
        tier = next((t for t in cost.get('tiers', []) if t.get('tier', {}).get('type') == 'context'), None)
        if tier:
            models[name]['longContext'] = dict(rates(tier), threshold=tier['tier']['size'])
    pricing = (repo / 'rust/crates/ccusage-core/src/pricing.rs').read_text()
    body = pricing.split('fn pricing_alias(', 1)[1].split('\n}\n', 1)[0]
    aliases = dict(re.findall(r'"([^"]+)" => Some\("([^"]+)"\)', body))
    multipliers = {}
    for tier in ('fast', 'flex', 'ultrafast'):
        exact = json.loads((repo / 'rust/crates/ccusage-core/src' / (tier + '-multiplier-overrides.json')).read_text())['exact']
        multipliers[tier] = {name: value for name, value in sorted(exact.items()) if name in models}
    fallbacks = json.loads((repo / 'rust/adapters/codex/src/codex-auto-review-fallbacks.json').read_text())
    commit = subprocess.run(['git', '-C', str(repo), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    result = {'source': {'project': 'ccusage', 'commit': commit, 'license': 'MIT'},
              'aliases': aliases, 'autoReviewFallbacks': fallbacks, 'multipliers': multipliers, 'models': models}
    (ROOT / 'lib/codex-pricing.json').write_text(json.dumps(result, ensure_ascii=False, indent=1) + '\n')
    print('models:', len(models), 'commit:', commit[:8])


if __name__ == '__main__':
    main()
