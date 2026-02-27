import logging
import os
import shutil
import subprocess

from ubuntucleaner.janitor import CruftObject, JanitorPlugin
from ubuntucleaner.utils.files import filesizeformat


log = logging.getLogger('DockerPlugin')


class DockerResourceObject(CruftObject):
    def __init__(self, name, resource_type, resource_id, path=None, size=0):
        self.name = name
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.path = path
        self.size = size

    def get_size_display(self):
        return filesizeformat(self.size)

    def get_path(self):
        return self.path

    def get_resource_id(self):
        return self.resource_id

    def get_resource_type(self):
        return self.resource_type


class DockerCachePlugin(JanitorPlugin):
    __title__ = _('Docker Cache')
    __category__ = 'system'

    cache_paths = (
        '~/.cache/docker',
        '~/.local/share/docker',
    )
    docker_bin = 'docker'

    @classmethod
    def is_active(cls):
        return cls.__utactive__ and cls._can_access_docker()

    @classmethod
    def _discover_cache_paths(cls):
        cache_paths = []
        for path in cls.cache_paths:
            expanded = os.path.expanduser(path)
            if os.path.isdir(expanded):
                cache_paths.append(expanded)
        return cache_paths

    @classmethod
    def _can_access_docker(cls):
        if shutil.which(cls.docker_bin) is None:
            return False
        try:
            return cls._run_docker(['info'], check=True)
        except Exception:
            return False

    @classmethod
    def _run_docker(cls, args, check=True):
        cmd = [cls.docker_bin] + args
        proc = subprocess.Popen(cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True)
        stdout, stderr = proc.communicate(timeout=20)
        if check and proc.returncode != 0:
            log.debug('Docker command failed: %s', stderr.strip())
            raise RuntimeError(stderr.strip() or 'Docker command failed')
        return stdout.strip()

    def get_cruft(self):
        count = 0
        total_size = 0

        # Local cache folders under HOME
        for cache_path in self._discover_cache_paths():
            try:
                size = self._du(cache_path)
                count += 1
                total_size += int(size)
                self.emit('find_object',
                          DockerResourceObject(os.path.basename(cache_path),
                                               'cache_path',
                                               cache_path,
                                               path=cache_path,
                                               size=size),
                          count)
            except Exception:
                log.exception('Failed to scan Docker cache path: %s', cache_path)
                self.emit('scan_error', cache_path)
                return

        # Dangling images (not in active use)
        try:
            images = self._run_docker(['image', 'ls', '-q', '--filter', 'dangling=true'], check=False)
            for image_id in (line.strip() for line in images.splitlines() if line.strip()):
                size = self._get_docker_image_size(image_id)
                count += 1
                total_size += int(size)
                self.emit('find_object',
                          DockerResourceObject('Image %s' % image_id, 'image', image_id, size=size),
                          count)
        except Exception:
            log.exception('Failed to list Docker dangling images')

        # Dangling local volumes
        try:
            volumes = self._run_docker(['volume', 'ls', '-q', '-f', 'dangling=true'], check=False)
            for volume_name in (line.strip() for line in volumes.splitlines() if line.strip()):
                mountpoint = self._get_volume_mountpoint(volume_name)
                size = self._du(mountpoint) if mountpoint else 0
                count += 1
                total_size += int(size)
                self.emit('find_object',
                          DockerResourceObject('Volume %s' % volume_name, 'volume', volume_name,
                                              path=mountpoint,
                                              size=size),
                          count)
        except Exception:
            log.exception('Failed to list Docker dangling volumes')

        self.emit('scan_finished', True, count, total_size)

    def clean_cruft(self, cruft_list=[], parent=None):
        for index, cruft in enumerate(cruft_list):
            try:
                resource_type = cruft.get_resource_type()
                resource_id = cruft.get_resource_id()

                if resource_type == 'cache_path':
                    if os.path.isdir(resource_id):
                        shutil.rmtree(resource_id)
                    else:
                        os.remove(resource_id)
                elif resource_type == 'image':
                    self._run_docker(['image', 'rm', '-f', resource_id], check=True)
                elif resource_type == 'volume':
                    self._run_docker(['volume', 'rm', resource_id], check=True)
                else:
                    raise RuntimeError('Unknown resource type: %s' % resource_type)

                self.emit('object_cleaned', cruft, index + 1)
            except Exception:
                log.exception('Failed to clean Docker resource: %s', cruft.get_name())
                self.emit('clean_error', cruft.get_name())
                break

        self.emit('all_cleaned', True)

    def get_summary(self, count):
        if count:
            return '[%d] %s' % (count, self.__title__)
        return '%s (No cache/images/volumes to be cleaned)' % self.__title__

    @classmethod
    def _get_docker_image_size(cls, image_id):
        try:
            size = cls._run_docker(['image', 'inspect', '--format', '{{.Size}}', image_id], check=False)
            return int(size) if size.isdigit() else 0
        except Exception:
            return 0

    @classmethod
    def _get_volume_mountpoint(cls, volume_name):
        try:
            output = cls._run_docker(['volume', 'inspect', '--format', '{{.Mountpoint}}', volume_name], check=False)
            return output.strip() if output else None
        except Exception:
            return None

    @staticmethod
    def _du(path):
        if not path or not os.path.isdir(path):
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
