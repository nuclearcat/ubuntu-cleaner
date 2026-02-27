import os
import shutil
import logging

from ubuntucleaner.janitor import CacheObject, JanitorPlugin


log = logging.getLogger('EspressifSDKCachePlugin')


class EspressifSDKCachePlugin(JanitorPlugin):
    __title__ = _('Espressif SDK Cache')
    __category__ = 'application'

    root_path = '~/.espressif/dist'

    @classmethod
    def is_active(cls):
        return cls.__utactive__ and os.path.isdir(os.path.expanduser(cls.root_path))

    def get_cruft(self):
        cache_root = os.path.expanduser(self.root_path)
        count = 0
        total_size = 0

        try:
            for name in sorted(os.listdir(cache_root)):
                full_path = os.path.join(cache_root, name)

                if not os.path.exists(full_path):
                    continue

                size = self._du(full_path)
                count += 1
                total_size += int(size)
                self.emit('find_object',
                          CacheObject(name, full_path, size),
                          count)

            self.emit('scan_finished', True, count, total_size)
        except Exception:
            log.exception('Failed to scan Espressif cache')
            self.emit('scan_error', cache_root)

    def clean_cruft(self, cruft_list=[], parent=None):
        for index, cruft in enumerate(cruft_list):
            try:
                path = cruft.get_path()
                if not os.path.exists(path):
                    self.emit('object_cleaned', cruft, index + 1)
                    continue

                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                self.emit('object_cleaned', cruft, index + 1)
            except Exception:
                log.exception('Failed to clean Espressif cache item: %s', cruft.get_name())
                self.emit('clean_error', cruft.get_name())
                break

        self.emit('all_cleaned', True)

    def get_summary(self, count):
        if count:
            return '[%d] %s' % (count, self.__title__)
        return '%s (No Espressif cache to be cleaned)' % self.__title__

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
