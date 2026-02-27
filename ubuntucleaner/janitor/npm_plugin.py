import logging
import os
import shutil

from ubuntucleaner.janitor import CacheObject, JanitorPlugin

log = logging.getLogger('NPMCachePlugin')


class NPMCachePlugin(JanitorPlugin):
    __title__ = _('NPM Cache')
    __category__ = 'application'

    cache_paths = (
        '~/.npm/_cacache',
        '~/.npm/_logs',
        '~/.npm/_npx',
        '~/.cache/npm',
        '~/.cache/npm/_cacache',
        '~/.cache/npm/_logs',
    )

    @classmethod
    def is_active(cls):
        return cls.__utactive__ and bool(cls._discover_cache_paths())

    @classmethod
    def _discover_cache_paths(cls):
        paths = []
        for path in cls.cache_paths:
            expanded = os.path.expanduser(path)
            if not os.path.exists(expanded):
                continue

            expanded = os.path.abspath(expanded)
            if any(expanded.startswith(existing + os.sep) for existing in paths):
                continue

            paths = [existing for existing in paths if not existing.startswith(expanded + os.sep)]
            paths.append(expanded)

        return paths

    def get_cruft(self):
        total_size = 0
        count = 0

        for path in self._discover_cache_paths():
            try:
                size = self._du(path)
                count += 1
                total_size += int(size)

                self.emit('find_object',
                          CacheObject(os.path.basename(path), path, size),
                          count)
            except Exception:
                log.exception('Failed to scan NPM cache path: %s', path)
                self.emit('scan_error', path)
                return

        self.emit('scan_finished', True, count, total_size)

    def clean_cruft(self, cruft_list=[], parent=None):
        for index, cruft in enumerate(cruft_list):
            try:
                if not os.path.exists(cruft.get_path()):
                    self.emit('object_cleaned', cruft, index + 1)
                    continue

                if os.path.isdir(cruft.get_path()):
                    shutil.rmtree(cruft.get_path())
                else:
                    os.remove(cruft.get_path())

                self.emit('object_cleaned', cruft, index + 1)
            except Exception:
                log.exception('Failed to clean npm cache: %s', cruft.get_name())
                self.emit('clean_error', cruft.get_name())
                break

        self.emit('all_cleaned', True)

    def get_summary(self, count):
        if count:
            return '[%d] %s' % (count, self.__title__)
        return '%s (No npm cache to be cleaned)' % self.__title__

    @staticmethod
    def _du(path):
        if os.path.isfile(path):
            try:
                return os.path.getsize(path)
            except OSError:
                return 0

        total_size = 0
        for root, _, files in os.walk(path):
            for filename in files:
                full_path = os.path.join(root, filename)
                try:
                    total_size += os.path.getsize(full_path)
                except OSError:
                    pass
        return total_size
