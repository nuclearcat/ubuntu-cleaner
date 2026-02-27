import logging
import re
import shutil
import subprocess

from ubuntucleaner.janitor import CacheObject, JanitorPlugin

log = logging.getLogger('SystemdJournalPlugin')


class SystemdJournalPlugin(JanitorPlugin):
    __title__ = _('Systemd Journal')
    __category__ = 'system'

    journalctl = shutil.which('journalctl')
    vacuum_args = (
        '--vacuum-time=7d',
    )
    journal_path = '/var/log/journal'

    @classmethod
    def is_active(cls):
        return cls.__utactive__ and bool(cls.journalctl)

    @classmethod
    def get_path(cls):
        return cls.journal_path

    def get_cruft(self):
        size = self._journal_disk_usage()
        if size is None:
            self.emit('scan_error', self.journal_path)
            return

        if size <= 0:
            self.emit('scan_finished', True, 0, 0)
            return

        count = 1
        self.emit('find_object',
                  CacheObject(_('Systemd Journal Logs'), self.journal_path, size),
                  count)
        self.emit('scan_finished', True, count, size)

    def clean_cruft(self, cruft_list=[], parent=None):
        for index, cruft in enumerate(cruft_list):
            try:
                if not self._vacuum_with_root():
                    raise RuntimeError('Failed to vacuum systemd journal')

                self.emit('object_cleaned', cruft, index + 1)
            except Exception:
                log.exception('Failed to clean systemd journal: %s', cruft.get_name())
                self.emit('clean_error', cruft.get_name())
                break

        self.emit('all_cleaned', True)

    def get_summary(self, count):
        if count:
            return '[%d] %s' % (count, self.__title__)
        return '%s (No systemd journal data to be cleaned)' % self.__title__

    @classmethod
    def _journal_disk_usage(cls):
        output = cls._run_journalctl_cmd(['--disk-usage'])
        if output is None:
            return None

        match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*([KMGTP]?)[B]?i?B?', output, re.IGNORECASE)
        if not match:
            return None

        value = float(match.group(1))
        unit = match.group(2).upper()
        unit_size = {
            '': 1,
            'K': 1024,
            'M': 1024 ** 2,
            'G': 1024 ** 3,
            'T': 1024 ** 4,
            'P': 1024 ** 5
        }

        return int(value * unit_size.get(unit, 1))

    @classmethod
    def _run_journalctl_cmd(cls, args):
        command = [cls.journalctl] + list(args)
        try:
            proc = subprocess.run(command,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  text=True,
                                  check=False)
        except Exception as e:
            log.error('Failed to run journalctl: %s', e)
            return None

        if proc.returncode != 0:
            log.error('journalctl failed: %s', proc.stderr.strip())
            return None

        return proc.stdout.strip()

    @classmethod
    def _vacuum_with_root(cls):
        command = [cls.journalctl] + list(cls.vacuum_args)
        if not command[0]:
            return False

        root_command = ['pkexec'] + command
        try:
            proc = subprocess.run(root_command,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  text=True,
                                  check=False)
        except FileNotFoundError:
            log.error('pkexec not available, cannot request root privileges')
            return False
        except Exception as e:
            log.error('Failed to run privileged journal vacuum: %s', e)
            return False

        if proc.returncode != 0:
            log.error('Root journal vacuum failed: %s', proc.stderr.strip())
            return False

        return True
