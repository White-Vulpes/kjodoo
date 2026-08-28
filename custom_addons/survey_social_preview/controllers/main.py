import re

from odoo import http
from odoo.http import request
from odoo.addons.survey.controllers.main import Survey

# Clients that fetch a URL only to build a link-preview card. They keep no
# cookies, so the ordinary /survey/start/ flow (create answer -> set cookie ->
# redirect) bounces them to "/" and the card ends up describing the website
# home page instead of the survey.
SOCIAL_SCRAPER_RE = re.compile(
    r'facebookexternalhit|facebookcatalog|whatsapp|twitterbot|linkedinbot|'
    r'slackbot|telegrambot|discordbot|pinterest|redditbot|skypeuripreview|'
    r'embedly|quora link preview|nuzzel|vkshare|bitlybot|iframely|mastodon|'
    r'googlebot|google-inspectiontool|bingbot|applebot|yandexbot|duckduckbot',
    re.IGNORECASE,
)


class SurveySocialPreview(Survey):

    @http.route('/survey/<string:survey_token>/get_social_image', type='http',
                auth='public', website=True, sitemap=False)
    def survey_get_social_image(self, survey_token):
        """Serve the survey's share image.

        Mirrors survey_get_background: public and token-scoped, because a
        scraper has no session to authenticate with.
        """
        survey_sudo, dummy = self._fetch_from_access_token(survey_token, False)
        return request.env['ir.binary']._get_image_stream_from(
            survey_sudo, 'og_image'
        ).get_response()

    @http.route()
    def survey_start(self, survey_token, answer_token=None, email=False, **post):
        """Answer scrapers with the preview card instead of the redirect.

        Stopping here rather than deferring to super() is the point twice over:
        the scraper gets a page it can actually read tags from, and it no longer
        leaves a blank survey.user_input behind. Every scrape of a shared link
        was creating one, skewing the participant count.
        """
        if self._is_social_scraper():
            survey_sudo, dummy = self._fetch_from_access_token(survey_token, False)
            if survey_sudo and survey_sudo.active:
                return request.render(
                    'survey_social_preview.survey_social_preview_page',
                    {'survey': survey_sudo},
                )
        return super().survey_start(
            survey_token, answer_token=answer_token, email=email, **post)

    def _is_social_scraper(self):
        user_agent = request.httprequest.headers.get('User-Agent') or ''
        return bool(SOCIAL_SCRAPER_RE.search(user_agent))
