from odoo import api, fields, models
from odoo.tools import html2plaintext


class SurveySurvey(models.Model):
    _inherit = 'survey.survey'

    # A survey already has a background image, but that is a full-bleed backdrop
    # whose subject is usually off-centre; a 1.91:1 social crop cuts it badly.
    # So the preview gets its own field and falls back to the background only
    # when nobody has set one.
    og_image = fields.Image(
        'Social Share Image',
        help="Shown when this survey's link is pasted into WhatsApp, Facebook "
             "or X. Landscape images around 1200x630 px crop best. Left empty, "
             "the Background Image is used instead.",
    )
    og_image_url = fields.Char(
        'Social Share Image URL', compute='_compute_og_image_url',
        help="Absolute URL of the preview image. Scrapers fetch it from "
             "outside any session, so a relative path would not resolve.",
    )
    og_share_url = fields.Char(
        'Share Link', compute='_compute_og_share_url',
        help="The canonical link to share for this survey.",
    )
    og_description_text = fields.Char(
        'Social Share Description', compute='_compute_og_description_text',
        help="Plain-text extract of the description, for the preview card.",
    )

    def _get_base_url(self):
        """Absolute site root, for the URLs handed to social scrapers."""
        return (self.env['ir.config_parameter'].sudo().get_param('web.base.url') or '').rstrip('/')

    @api.depends('og_image', 'background_image', 'access_token')
    def _compute_og_image_url(self):
        base_url = self._get_base_url()
        self.og_image_url = False
        if not base_url:
            return
        for survey in self:
            if not survey.access_token:
                continue
            if survey.og_image:
                survey.og_image_url = '%s/survey/%s/get_social_image' % (
                    base_url, survey.access_token)
            elif survey.background_image:
                # Already served by survey's own public route.
                survey.og_image_url = '%s/survey/%s/get_background_image' % (
                    base_url, survey.access_token)

    @api.depends('access_token')
    def _compute_og_share_url(self):
        base_url = self._get_base_url()
        self.og_share_url = False
        for survey in self:
            if survey.access_token and base_url:
                survey.og_share_url = '%s/survey/start/%s' % (base_url, survey.access_token)

    @api.depends('description')
    def _compute_og_description_text(self):
        for survey in self:
            text = ''
            if survey.description:
                # html2plaintext also unescapes entities, which striptags leaves behind.
                text = ' '.join(html2plaintext(survey.description).split())
            survey.og_description_text = text[:200]
