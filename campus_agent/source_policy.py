"""Evidence-labelled source exclusions, not a certification of other websites."""
from urllib.parse import urlsplit, parse_qs, unquote

VERSION = 'source-policy-v1'
REVIEWED_ON = '2026-11-11'
SOURCES = {
    'jobleads.com': {
        'name': 'JobLeads',
        'reason': 'Excluded at your request: subscription intermediary with reported billing and listing concerns. Find the employer’s original vacancy instead.',
        'basis': 'User exclusion; published subscription terms and consumer complaints. Not a legal finding of fraud.',
        'references': [
            'https://www.jobleads.com/au/terms-of-use',
            'https://www.bbb.org/us/tx/dallas/profile/employment-agencies/jobleads-0875-91345977/complaints',
            'https://www.reddit.com/r/recruitinghell/comments/1lvqgyw/is_jobleads_a_legit_application_website/',
        ],
    },
    'bebee.com': {
        'name': 'beBee',
        'reason': 'Excluded as a subscription intermediary with reported billing/application concerns. Use a verified employer or recruiter listing instead.',
        'basis': 'Precautionary exclusion under the request to filter similar sites. Free features exist; a paid tier alone does not establish fraud.',
        'references': ['https://bebee.com/gb/terms', 'https://www.trustpilot.com/review/www.bebee.com'],
    },
}
REDIRECT_KEYS = {'url','u','redirect','redirect_url','redirect_uri','target','dest','destination','next','continue'}


def source_exclusion(url):
    """Check host boundaries and explicit wrapped destinations; never substring-match."""
    pending=[str(url)]; seen=set()
    for _ in range(5):
        current,pending=pending,[]
        for value in current:
            if value in seen: continue
            seen.add(value)
            try:
                parsed=urlsplit(value)
                host=(parsed.hostname or '').lower().rstrip('.').encode('idna').decode('ascii')
            except (ValueError,UnicodeError):
                continue
            for domain,entry in SOURCES.items():
                if host==domain or host.endswith('.'+domain):
                    return {'status':'excluded','domain':domain,'reviewed_on':REVIEWED_ON,'version':VERSION,**entry}
            for key,values in parse_qs(parsed.query).items():
                if key.lower() in REDIRECT_KEYS:
                    for target in values[:3]:
                        target=unquote(target)
                        if target.startswith(('https://','http://','//')):pending.append(target)
        if not pending:break
    return None


def require_allowed_source(url):
    exclusion=source_exclusion(url)
    if exclusion:raise ValueError(exclusion['reason'])
