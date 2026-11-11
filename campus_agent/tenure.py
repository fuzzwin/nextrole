"""Conservative general support tenure; never infer years using a particular tool."""
from __future__ import annotations

import calendar
from datetime import date, datetime
import re
from zoneinfo import ZoneInfo

SUPPORT = r'\b(?:(?:IT|ICT|technical|desktop|systems?|application|end[ -]user)\s+(?:systems?\s+)?support|service[ -]desk|help[ -]?desk)\b'
NUMBER = {'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,'twelve':12,'eighteen':18,'twenty':20}
DURATION = r'(?<![\w.])(\d+|'+'|'.join(NUMBER)+r')\+?\s*(years?|months?)\b'


def assessment_day():
    return datetime.now(ZoneInfo('Australia/Melbourne')).date()


def _bound(value, *, start, today):
    value=value.strip()
    if re.fullmatch(r'present|current|now',value,re.I):
        return None if start else today
    if re.fullmatch(r'\d{4}',value):
        try:
            return date(int(value),12,31) if start else date(int(value),1,1)
        except ValueError:
            return None
    for fmt in ('%B %Y','%b %Y','%m/%Y','%Y-%m','%Y-%m-%d'):
        try:
            parsed=datetime.strptime(value,fmt).date()
        except ValueError:
            continue
        if fmt!='%Y-%m-%d' and start:
            parsed=parsed.replace(day=calendar.monthrange(parsed.year,parsed.month)[1])
        return parsed
    return None


def employment_interval(value, today=None):
    today=today or assessment_day()
    # A spaced hyphen avoids splitting ISO dates; a bare dash supports year ranges.
    parts=re.split(r'\s+[–—-]\s+|[–—]|\s+to\s+|(?<=\d{4})-(?=\d{4}$)',value,flags=re.I)
    if len(parts)!=2: return None
    a,b=_bound(parts[0],start=True,today=today),_bound(parts[1],start=False,today=today)
    if not a or not b or a>=b or a>today: return None
    return a,min(b,today)


def general_support_duration(criterion, facts, *, today=None):
    """Accept only plain support tenure with matching job titles and actual support duties."""
    demand=re.search(DURATION,criterion,re.I)
    general = r'\b(?:IT|ICT|technical)\s+support\b'
    if len(list(re.finditer(DURATION,criterion,re.I)))!=1 or not re.search(general,criterion,re.I): return None
    remaining=re.sub(DURATION,' ',criterion,flags=re.I)
    remaining=re.sub(general,' ',remaining,flags=re.I)
    # Explicit alternatives allow the general IT-support branch to stand alone.
    remaining=re.sub(r',\s*(?:systems? support,\s*)?or\s+a\s+(?:closely\s+)?related role\b',' ',remaining,flags=re.I)
    allowed=set('a an the at least minimum of in with or and relevant experience professional proven demonstrated hands on working work role roles position positions required essential must have years months'.split())
    if set(re.findall(r'[a-z]+',remaining.lower()))-allowed:
        return None  # Healthcare, external customers, tools, seniority, etc. need separate evidence.
    today=today or assessment_day()
    from .fit import evidence_value, NON_PRODUCTION
    records={}
    for fact in facts:
        if not re.search(SUPPORT,fact['role'],re.I) or evidence_value(fact['text'])!=1:
            continue
        # Match the IT object directly after the action; "billing using M365"
        # is not an IT-support duty. This deliberately leaves ambiguous prose open.
        activity = (r"(?i)^\s*(?:(?:I|We)\s+)?(?:have\s+)?(?:"
                    r"(?:support(?:ed)?|resolve(?:d)?|troubleshoot(?:ed)?)\s+(?:(?:complex|end[ -]user)\s+)?(?:IT|ICT|technical|service[ -]desk|help[ -]?desk|ServiceNow|Microsoft 365|M365|software|hardware|network)\b|"
                    r"administer(?:ed)?\s+(?:Microsoft 365|M365|Exchange|Entra|Intune|SCCM|IT|network|system)\b|"
                    r"(?:run|ran)\s+IT\s+(?:onboarding|offboarding)\b|deploy(?:ed)?\s+(?:PCs|computers|devices)\b)")
        if not re.match(activity,fact['text']):
            continue
        if re.search(NON_PRODUCTION,fact.get('original_text',fact['text']),re.I):
            continue
        interval=employment_interval(fact['dates'],today)
        if interval:
            records.setdefault((fact['role'],fact['organisation'],fact['dates']),(interval,fact))
    intervals=sorted(interval for interval,_ in records.values())
    merged=[]
    for a,b in intervals:
        if merged and a<=merged[-1][1]: merged[-1]=(merged[-1][0],max(b,merged[-1][1]))
        else: merged.append((a,b))
    # Full calendar months, rounded down independently across gaps.
    months=sum(max(0,(b.year-a.year)*12+b.month-a.month-(b.day<a.day)) for a,b in merged)
    amount=NUMBER.get(demand[1].lower()) if not demand[1].isdigit() else int(demand[1])
    needed=amount*(12 if demand[2].lower().startswith('year') else 1)
    if not records or months<needed: return None
    source=next(iter(records.values()))[1]
    return {**source,'tenure':{'months_at_least':months,'required_months':needed,'as_of':today.isoformat(),
            'basis':'Dated general support roles; overlapping dates counted once. Tool-specific tenure is not inferred.',
            'roles':[{'role':f['role'],'organisation':f['organisation'],'dates':f['dates']} for _,f in records.values()]}}
