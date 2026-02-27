import os
import logging

from ubuntucleaner.janitor import CacheObject, JanitorCachePlugin
from ubuntucleaner.settings.common import RawConfigSetting

log = logging.getLogger('MozillaCachePlugin')


class MozillaCachePlugin(JanitorCachePlugin):
    __category__ = 'application'
    cache_path = ''

    #targets = ['Cache',
    #           'safebrowsing',
    #           'startupCache',
    #           'thumbnails',
    #           'cache2',
    #           'OfflineCache']
    app_path = ''

    @classmethod
    def is_active(cls):
        return cls.__utactive__ and bool(cls._discover_cache_roots())

    @classmethod
    def _discover_profile_root(cls, cache_root, section, config):
        try:
            profile_path = config.get_value(section, 'Path')
        except Exception:
            return None

        try:
            is_relative = str(config.get_value(section, 'IsRelative')).lower()
        except Exception:
            is_relative = '1'

        if is_relative in ['0', 'false', 'no']:
            return os.path.expanduser(profile_path)

        return os.path.join(cache_root, profile_path)

    @classmethod
    def _discover_cache_roots(cls):
        profiles_path = os.path.expanduser('%s/profiles.ini' % cls.app_path)
        cache_path = getattr(cls, 'cache_path', '')
        if cache_path:
            cache_root = os.path.expanduser(cache_path)
        else:
            cache_root = os.path.expanduser(getattr(cls, 'root_path', ''))
        cache_root = cache_root.rstrip(os.sep)

        if not os.path.isdir(cache_root):
            return []

        discovered = []

        if os.path.exists(profiles_path):
            config = RawConfigSetting(profiles_path)
            try:
                for section in config.sections():
                    if not section.startswith('Profile'):
                        continue
                    profile_root = cls._discover_profile_root(cache_root, section, config)
                    if not profile_root:
                        continue

                    profile_root = os.path.abspath(profile_root)
                    if os.path.isdir(profile_root):
                        cache2_root = os.path.join(profile_root, 'cache2')
                        if os.path.isdir(cache2_root):
                            discovered.append(profile_root)
            except Exception as e:
                log.error(e)

        # Include any cache profile directories present on disk, even if
        # they are missing from profiles.ini.
        for child in sorted(os.listdir(cache_root)):
            profile_root = os.path.join(cache_root, child)
            if os.path.isdir(profile_root) and \
                    os.path.isdir(os.path.join(profile_root, 'cache2')):
                discovered.append(os.path.abspath(profile_root))

        # Deduplicate and keep stable order.
        unique_roots = []
        for path in discovered:
            if path not in unique_roots:
                unique_roots.append(path)

        return unique_roots

    @classmethod
    def _cache_size(cls, cache_root):
        cache2_root = os.path.join(cache_root, 'cache2')
        if not os.path.isdir(cache2_root):
            return 0

        try:
            size = os.popen('du -bs "%s"' % cache2_root).read().split()[0]
            return int(size)
        except Exception:
            return 0

    @classmethod
    def get_path(cls):
        cache_roots = cls._discover_cache_roots()
        if not cache_roots:
            return cls.root_path

        cache_roots.sort(key=cls._cache_size, reverse=True)
        return cache_roots[0]

    def get_cruft(self):
        total_size = 0
        count = 0

        for cache_root in self._discover_cache_roots():
            if not self.targets:
                if not os.path.isdir(cache_root):
                    continue

                for root, dirs, files in os.walk(cache_root):
                    if root != cache_root or not dirs:
                        continue

                    dirs.sort()
                    files.sort()

                    for path in sorted(dirs + files):
                        full_path = os.path.join(cache_root, path)
                        try:
                            size = os.popen('du -bs "%s"' % full_path).read().split()[0]
                        except Exception:
                            size = 0
                        count += 1
                        total_size += int(size)

                        self.emit('find_object',
                                  CacheObject(path, full_path, size),
                                  count)

                    break

                continue

            for target in self.targets:
                new_root_path = os.path.join(cache_root, target)

                if not os.path.exists(new_root_path):
                    continue

                if os.path.isdir(new_root_path):
                    try:
                        size = os.popen('du -bs "%s"' % new_root_path).read().split()[0]
                    except Exception:
                        size = 0
                else:
                    size = os.path.getsize(new_root_path)

                display_name = '%s/%s' % (os.path.basename(cache_root), target)
                total_size += int(size)
                count += 1

                self.emit('find_object',
                          CacheObject(display_name, new_root_path, size),
                          count)

        self.emit('scan_finished', True, count, total_size)



class FirefoxCachePlugin(MozillaCachePlugin):
    __title__ = _('Firefox Cache')

    app_path = '~/.mozilla/firefox'
    cache_path = '~/.cache/mozilla/firefox'
    targets = ['cache2']


class ThunderbirdCachePlugin(MozillaCachePlugin):
    __title__ = _('Thunderbird Cache')

    app_path = '~/.thunderbird'
    cache_path = '~/.cache/thunderbird'
