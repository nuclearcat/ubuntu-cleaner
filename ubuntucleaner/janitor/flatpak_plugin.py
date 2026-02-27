import logging
import os
import shutil
import subprocess

from ubuntucleaner.janitor import CacheObject, JanitorPlugin

log = logging.getLogger('FlatpakCachePlugin')


class FlatpakCachePlugin(JanitorPlugin):
    __title__ = _('Flatpak Cache')
    __category__ = 'system'

    cache_paths = (
        '~/.cache/flatpak',
        '/var/cache/flatpak',
    )

    @classmethod
    def is_active(cls):
        return cls.__utactive__ and bool(cls._discover_cache_paths())

    @classmethod
    def _discover_cache_paths(cls):
        discovered = []
        for path in cls.cache_paths:
            expanded = os.path.expanduser(path)
            if os.path.isdir(expanded):
                discovered.append(os.path.abspath(expanded))

        discovered.extend(cls._discover_var_app_cache_paths())
        return discovered

    @classmethod
    def _discover_var_app_cache_paths(cls):
        base = os.path.expanduser('~/.var/app')
        cache_paths = []

        if not os.path.isdir(base):
            return cache_paths

        for name in sorted(os.listdir(base)):
            cache_path = os.path.join(base, name, 'cache')
            if os.path.isdir(cache_path):
                cache_paths.append(os.path.abspath(cache_path))

        return cache_paths

    @classmethod
    def _remove_with_root(cls, path):
        command = ['pkexec', 'rm', '-rf', '--', path]
        try:
            result = subprocess.run(command,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    text=True)
        except FileNotFoundError:
            log.error('pkexec not found, cannot request root cleanup')
            return False
        except Exception as e:
            log.error('Failed to run privileged flatpak cleanup: %s', e)
            return False

        if result.returncode != 0:
            log.error('Privileged flatpak cleanup failed for %s: %s', path, result.stderr.strip())
            return False

        return True

    def get_cruft(self):
        count = 0
        total_size = 0

        for path in self._discover_cache_paths():
            try:
                size = self._du(path)
                count += 1
                total_size += int(size)
                self.emit('find_object',
                          CacheObject(os.path.basename(path), path, size),
                          count)
            except Exception:
                log.exception('Failed to scan flatpak cache path: %s', path)
                self.emit('scan_error', path)
                return

        self.emit('scan_finished', True, count, total_size)

    def clean_cruft(self, cruft_list=[], parent=None):
        for index, cruft in enumerate(cruft_list):
            try:
                path = cruft.get_path()
                if not os.path.exists(path):
                    self.emit('object_cleaned', cruft, index + 1)
                    continue

                deleted = False
                try:
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                    deleted = True
                except PermissionError:
                    deleted = self._remove_with_root(path)

                if not deleted:
                    raise RuntimeError('Failed to remove %s' % path)

                self.emit('object_cleaned', cruft, index + 1)
            except Exception:
                log.exception('Failed to clean flatpak cache item: %s', cruft.get_name())
                self.emit('clean_error', cruft.get_name())
                break

        self.emit('all_cleaned', True)

    def get_summary(self, count):
        if count:
            return '[%d] %s' % (count, self.__title__)
        return '%s (No flatpak cache to be cleaned)' % self.__title__

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
