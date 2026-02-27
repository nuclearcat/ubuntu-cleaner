import logging
import os
import shutil

from ubuntucleaner.janitor import CacheObject, JanitorPlugin


log = logging.getLogger('SteamCachePlugin')


class SteamCachePlugin(JanitorPlugin):
    __title__ = _('Steam Cache')
    __category__ = 'application'

    cache_roots = (
        '~/.steam/steam',
        '~/.local/share/Steam',
    )
    cache_targets = (
        'appcache',
        'depotcache',
        'dumps',
        'httpcache',
        'logs',
    )

    @classmethod
    def is_active(cls):
        return cls.__utactive__ and bool(cls._discover_roots())

    @classmethod
    def _discover_roots(cls):
        roots = []
        for root in cls.cache_roots:
            expanded_root = os.path.expanduser(root)
            if os.path.exists(expanded_root):
                roots.append(expanded_root)
        return roots

    @classmethod
    def _discover_cache_paths(cls):
        cache_paths = []
        for root_path in cls._discover_roots():
            if not os.path.exists(root_path):
                continue

            for target in cls.cache_targets:
                path = os.path.join(root_path, target)
                if os.path.exists(path):
                    cache_paths.append(path)

        return cache_paths

    def get_cruft(self):
        count = 0
        total_size = 0

        for path in self._discover_cache_paths():
            try:
                count += 1
                size = self._get_path_size(path)

                total_size += int(size)
                self.emit('find_object',
                          CacheObject(os.path.basename(path), path, size),
                          count)
            except Exception:
                log.exception("Error while scanning Steam cache path: %s", path)
                self.emit('scan_error', str(path))
                return

        self.emit('scan_finished', True, count, total_size)

    @staticmethod
    def _get_path_size(path):
        if os.path.isfile(path):
            return os.path.getsize(path)

        total_size = 0
        for root, _, files in os.walk(path):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                try:
                    total_size += os.path.getsize(file_path)
                except OSError:
                    log.debug('Cannot read file size: %s', file_path)
        return total_size

    def clean_cruft(self, cruft_list=[], parent=None):
        for index, cruft in enumerate(cruft_list):
            try:
                if os.path.isdir(cruft.get_path()):
                    shutil.rmtree(cruft.get_path())
                else:
                    os.remove(cruft.get_path())
                self.emit('object_cleaned', cruft, index + 1)
            except Exception:
                log.exception("Error while cleaning Steam cache item")
                self.emit('clean_error', cruft.get_name())
                break

        self.emit('all_cleaned', True)
