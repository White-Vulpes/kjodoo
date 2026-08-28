{
    'name': 'Survey Link Previews',
    'version': '19.0.1.0.0',
    'category': 'Marketing/Surveys',
    'summary': 'Open Graph link previews when a survey is shared on social media',
    'description': """
Survey share links pasted into WhatsApp, Facebook or X currently preview as the
website home page. A social scraper carries no cookies, so /survey/start/<token>
sets its answer cookie, redirects, and the cookie-less scraper is bounced to "/".

This module answers scrapers with a small page carrying the survey's own Open
Graph tags, and gives each survey an optional Social Share Image.
""",
    'author': 'Kothari Jewels',
    'license': 'LGPL-3',
    'depends': ['survey'],
    'data': [
        'views/survey_survey_views.xml',
        'views/survey_templates.xml',
    ],
    'installable': True,
    'application': False,
}
