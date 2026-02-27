import os

from ubuntucleaner.janitor import JanitorCachePlugin


class TelegramDesktopCachePlugin(JanitorCachePlugin):
    __title__ = _('Telegram Desktop Cache')
    __category__ = 'application'

    root_path = '~/.local/share/TelegramDesktop/tdata'
    targets = [
        'audio_cache',
        'dumps',
        'emoji',
        'webview',
        'webview-tonsite',
    ]

    @classmethod
    def is_active(cls):
        return cls.__utactive__ and os.path.isdir(os.path.expanduser(cls.root_path))
