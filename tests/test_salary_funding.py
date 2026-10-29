from campus_agent.listing_view import salary_info


def test_funding_is_not_pay_even_with_compensation_and_based():
    for text in [
        'Based in Melbourne, we raised US$75M Series C, and offer competitive compensation.',
        'Our compensation philosophy is transparent. We raised US$75M in funding.',
        'We have a valuation of US$75M and revenue of US$20M.',
        'The company is based in Sydney and has secured US$75M Series C funding.',
    ]:
        assert salary_info(text)['status']=='not_stated', text


def test_pay_after_funding_retains_source_figures_currency_and_unit():
    for text in [
        'We raised US$75M Series C. Base salary: AUD $120,000 - $140,000 per year.',
        'We raised US$75M Series C, and base salary: AUD $120,000 - $140,000 per year.',
    ]:
        salary=salary_info(text)
        assert salary['status']=='stated', salary
        assert salary['minimum']==120000 and salary['maximum']==140000
        assert salary['currency']=='AUD' and salary['period']=='year'
        assert '120,000' in salary['display'] and '75' not in salary['display']
        assert salary['evidence']==text
