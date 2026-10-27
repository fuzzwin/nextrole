"""Location facts for browsing; discovery search areas are never job locations."""
import re

STATES = {'VIC':'Victoria', 'NSW':'New South Wales', 'QLD':'Queensland',
          'WA':'Western Australia', 'SA':'South Australia', 'TAS':'Tasmania',
          'ACT':'Australian Capital Territory', 'NT':'Northern Territory'}
CITIES = {'Melbourne':'VIC', 'Sydney':'NSW', 'Brisbane':'QLD', 'Perth':'WA',
          'Adelaide':'SA', 'Hobart':'TAS', 'Canberra':'ACT', 'Darwin':'NT',
          'Geelong':'VIC', 'Ballarat':'VIC', 'Bendigo':'VIC', 'Gold Coast':'QLD',
          'Newcastle':'NSW', 'Wollongong':'NSW'}


def location_info(job, search_area, override=None):
    from .listing_view import normalize_listing
    text = re.sub(r'(?m)^L\d+: ?', '', normalize_listing(job['description'],job.get('title','')))
    text = re.split(r'(?im)^\s*(?:#+\s*)?(?:Recommended Jobs|Related jobs|Similar jobs|Find similar jobs|People also viewed|More jobs like this|Show more Show less)\b', text)[0]
    header = text[:1800]
    stated = override
    evidence = 'Saved by you' if override else ''
    if not stated:
        # A labelled field may contain suburbs, several cities or an overseas address.
        field = re.search(r'\b(?:Job location|Location|Locations|Based in)\s*[:\n]\s*([^\n|]{2,180})', header, re.I)
        if not field:
            field = re.search(r'\bLocation\s+((?:[A-Z][\w-]*[, ]+){0,5}(?:Australia|VIC|NSW|QLD|WA|SA|TAS|ACT|NT))\b', header)
        if field:
            candidate = re.split(r'\s+(?:Region|Work type|Work format|Salary|Category|Posted|Department|We|This|The role|Job|Focus)\b|\s*[•·]|\s+[-–]\s+|\.{3}|#{2,}|\s+\d+ days?\b', field[1], flags=re.I)[0].strip(' ,:;*`📍')
            if candidate and len(candidate)<=100 and re.search(r'[A-Za-z]{2}',candidate):
                stated, evidence = candidate, field[0]
    if not stated:
        explicit=re.search(r'\b(?:this role|this position|the role|the position|you)\b.{0,45}\b(?:based|located|working)\s+(?:in|at)\s+([A-Z][^.!?\n]{2,90})',header,re.I)
        if explicit:
            stated,evidence=explicit[1].strip(),explicit[0]
    # Unlabelled place headers must not come from office marketing or contacts.
    header_places='\n'.join(line for line in header.splitlines() if not re.search(r'\b(?:our|office|offices|headquarters|contact|supports|company)\b',line,re.I))
    if not stated:
        state_names='|'.join(map(re.escape,STATES.values()))
        place=re.search(r'\b([A-Z][a-z]+(?: [A-Z][a-z]+){0,2}),?\s+('+state_names+r')(?:[, ]+Australia)?\b',header_places)
        if place:
            stated,evidence=place[0],place[0]
    if not stated:
        # Common unlabelled board headers: “Scoresby VIC, Australia” or “Sydney, NSW”.
        place = re.search(r'\b([A-Z][a-z]+(?: [A-Z][a-z]+){0,2}),?\s+(VIC|NSW|QLD|WA|SA|TAS|ACT|NT)\b(?:[, ]+Australia)?', header_places)
        if place:
            stated, evidence = place[0], place[0]
    if not stated:
        city_pattern = '|'.join(map(re.escape, CITIES))
        place = re.search(r'(?:'+city_pattern+r')\s+(?:VIC|NSW|QLD|WA|SA|TAS|ACT|NT)\b',header_places)
        if not place:
            place = re.search(r'\b(?:'+city_pattern+r')[, ]+Australia\b', header_places, re.I)
        if place:
            stated, evidence = place[0], place[0]
    if not stated:
        # A saved explicit location differs from the broad discovery hint.
        saved = job.get('location','')
        if saved and saved not in {search_area, 'Melbourne Victoria Australia', 'Long Beach, CA'}:
            stated, evidence = saved, 'Saved listing location'
    # Strip only an explicitly known employer prefix, retaining the source evidence.
    employer = (job.get('employer') or '').strip()
    if stated and employer and evidence != 'Saved by you' and stated.casefold().startswith(employer.casefold()+' '):
        remainder = stated[len(employer):].strip(' ,–-')
        if any(re.search(r'\b'+re.escape(city)+r'\b', remainder, re.I) for city in CITIES):
            stated = remainder
    if stated and re.fullmatch(r'\s*remote\s*[-–·,]\s*remote\s*', stated, re.I):
        stated = 'Remote'
    mode = ''
    if re.search(r'\b(?:hybrid(?: work(?:ing)?)?|work (?:format|arrangement)\s*:?\s*hybrid)\b', header, re.I):
        mode = 'Hybrid'
    elif re.search(r'\b(?:100%\s*remote|fully remote|remote[- ]first|work (?:format|arrangement)\s*:?\s*remote|remote\s*(?:\(|[·:,-])?\s*(?:Australia|Sydney|Melbourne)|work remotely|remote work(?:ing)?|work from home)\b', header, re.I):
        mode = 'Remote'
    elif re.search(r'\b(?:on[- ]site|onsite)\b', header, re.I):
        mode = 'On-site'
    if stated and re.search(r'\bremote\b', stated, re.I) and not mode:
        mode = 'Remote'
    geographic = stated or ''
    cities = [city for city in CITIES if re.search(r'\b'+re.escape(city)+r'\b', geographic, re.I)]
    states = [code for code,name in STATES.items() if re.search(r'\b(?:'+code+'|'+name+r')\b', geographic, re.I)]
    states = list(dict.fromkeys(states+[CITIES[c] for c in cities]))
    return {'display':stated or 'Location not stated', 'stated':bool(stated),
            'cities':cities, 'states':states, 'arrangement':mode, 'evidence':evidence}


def preferred_location(info, search_area):
    """Use extracted places, never a city mentioned in duties or company offices."""
    if not info.get('stated'): return False
    cities=[c for c in CITIES if re.search(r'\b'+re.escape(c)+r'\b',search_area,re.I)]
    regions=[c for c,n in STATES.items() if re.search(r'\b(?:'+c+'|'+n+r')\b',search_area,re.I)]
    if cities and set(cities)&set(info.get('cities',[])): return True
    if not cities and regions and set(regions)&set(info.get('states',[])): return True
    australian=bool(cities or regions or re.search(r'\bAustralia\b',search_area,re.I))
    if australian and info.get('arrangement')=='Remote' and re.search(r'\bAustralia\b',info.get('display',''),re.I): return True
    return info.get('display','').strip().casefold()==search_area.strip().casefold()
