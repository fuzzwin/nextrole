"""Display metadata from explicit listing statements, never crawler timestamps."""
from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

MONTH = r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
DATE = rf'(?:20\d{{2}}-\d{{2}}-\d{{2}}(?:T\d{{2}}:\d{{2}}(?::\d{{2}})?(?:Z|[+-]\d{{2}}:\d{{2}})?)?|\d{{1,2}}\s+{MONTH}\s+20\d{{2}}|{MONTH}\s+\d{{1,2}},?\s+20\d{{2}}|\d{{1,2}}/\d{{1,2}}/20\d{{2}})'


def parse_date(value, timezone='Australia/Melbourne'):
    value = re.sub(r'\s+', ' ', value.strip())
    if 'T' in value:
        try:
            moment = datetime.fromisoformat(value.replace('Z','+00:00'))
            return (moment.astimezone(ZoneInfo(timezone)) if moment.tzinfo else moment).date().isoformat()
        except ValueError:
            return None
    for pattern in ['%Y-%m-%d','%d %B %Y','%d %b %Y','%B %d, %Y','%b %d, %Y','%B %d %Y','%b %d %Y','%d/%m/%Y']:
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            pass
    return None


def extract_dates(text):
    text = re.sub(r'(?m)^L\d+: ?', '', text)
    text = re.split(r'(?im)^\s*(?:#+\s*)?(?:Recommended Jobs|Similar jobs|People also viewed|More jobs like this|Explore more jobs)\b', text)[0]
    result = {'posted_on':None,'closes_on':None,'posted_hint':None,'closing_hint':None,'date_evidence':{}}
    patterns = {
        'posted_on':rf'(?:\bdatePosted\b["\s]*:?["\s]*|\b(?:Date posted|Posted date|Posted on|Posted)\b\s*:?\s*)({DATE})',
        'closes_on':rf'(?:\bvalidThrough\b["\s]*:?["\s]*|\b(?:End Date|Closing Date|Applications? close[sd]?|closes)\b\s*:?\s*)(?:\d{{1,2}}:\d{{2}}\s*(?:am|pm)?\s*(?:on\s+)?)?({DATE})',
    }
    for field, pattern in patterns.items():
        match = re.search(pattern, text, re.I)
        if match and (date := parse_date(match[1])):
            result[field] = date
            result['date_evidence'][field] = match[0]
    # Preserve relative source wording without inventing an absolute date from
    # an indexed/cached page whose original observation time may be unknown.
    relative = re.search(r'\bPosted(?: on)?\s*:?\s*(\d+\s+(?:minutes?|hours?|days?|weeks?|months?)\s+ago|today|yesterday)\b', text, re.I)
    if relative and not result['posted_on']:
        result['posted_hint'] = relative[1] + ' (source wording)'
        result['date_evidence']['posted_hint'] = relative[0]
    if re.search(r'\b(?:open|applications? (?:are )?open) until filled\b', text, re.I):
        result['closing_hint'] = 'Open until filled'
    return result


def date_state(metadata, timezone):
    today = datetime.now(ZoneInfo(timezone)).date()
    closing = metadata.get('closes_on')
    days = (datetime.fromisoformat(closing).date() - today).days if closing else None
    return {'closed':days is not None and days < 0,'days_to_close':days}


def clean_summary(text):
    text = re.sub(r'[^]*|【[^】]*】|\[wordlim\s*:?\s*\d+\]', '', text)
    text = re.sub(r'^\s*(?:(?:Published|Crawled):[^;\n]*;\s*)+', '', text)
    text = re.sub(r'(?m)^L\d+: ?', '', text)
    text = re.sub(r'(?<!\w)#{1,6}\s*', '', text)
    return re.sub(r'\s+', ' ', text).strip()
