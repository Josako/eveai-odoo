{
    'name': 'Evie Website',
    'version': '19.0.1.0.0',
    'category': 'Website',
    'summary': 'Evie Chat Website Builder block (alongside Embed Code paste)',
    'description': """
Evie Website
============

Adds an **Evie Chat** building block to the Website Builder as an alternative
to pasting the Evie embed snippet into Odoo's built-in Embed Code / Code
Injection. Editors drag the block onto a page and fill Magic link, Chat
client URL and Chat API key in the Customize panel — the same shape as the
Strapi ``evie-chat-widget`` component. The paste-snippet path stays available
for Odoo Online and anyone who prefers it.

On the published page the block loads the Evie embed widget
(``EvieChat.init``) into the mount node. In the editor it shows a placeholder
only (the live widget is not started while designing).

Depends on ``website`` and ``evie_base``. Requires Odoo.sh or self-hosted
Odoo 19 (custom modules are not available on Odoo Online SaaS).
""",
    'author': 'Ask Eve AI',
    'website': 'https://askeveai.be',
    'license': 'LGPL-3',
    'depends': ['website', 'evie_base'],
    'data': [
        'views/snippets/s_evie_chat.xml',
        'views/snippets/snippets.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'evie_website/static/src/interactions/evie_chat.js',
            'evie_website/static/src/scss/s_evie_chat.scss',
        ],
        'website.website_builder_assets': [
            'evie_website/static/src/website_builder/evie_chat_option_plugin.js',
            'evie_website/static/src/website_builder/evie_chat_option.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
