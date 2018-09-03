import logging
import os
import re
import sys
import threading
from abc import ABCMeta, abstractmethod
from queue import Queue
from typing import Callable


def ensure_valid_path(path: str, file: str, force: bool = False) -> str:
    logging.debug('ensure path, path={}, file={}, force={}'.format(path, file, force))
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
    file = re.sub(r'[/:*?"<>|]', '_', file)
    file_path = os.path.join(path, file)
    if force:
        return file_path
    while os.path.exists(file_path):
        name = file.rsplit('.', 1)
        ext = None if len(name) == 1 else name[1]
        name = name[0]
        m = re.search(r'\(([1-9]\d*)\)$', name)
        if not m:
            name += ' (1)'
        else:
            name = re.sub(r'\(([1-9]\d*)\)$', '(' + str(int(m.group(1)) + 1) + ')', name)
        file = name
        if ext is not None:
            file += '.' + ext
        file_path = os.path.join(path, file)
    logging.debug('ensure path, file_path={}'.format(file_path))
    return file_path


def readable_size(value: int) -> str:
    if value < 0:
        raise ValueError('\'value\' can\'t be negative')
    if value < 1024:
        return '{} B'.format(value)
    value = round(value / 1024, 1)
    if value < 1024:
        return '{} KB'.format(value)
    value = round(value / 1024, 1)
    if value < 1024:
        return '{} MB'.format(value)
    value = round(value / 1024, 1)
    return '{} GB'.format(value)


class ProgressBar:
    def __init__(self, total: int = 100, progress: int = 0, detail: Callable[[int], str] = None, extra: str = None):
        self._total = total
        self._progress = progress
        self._detail = detail
        self._extra = extra
        self._show = False
        self._formation = '{:>5}% ├{:─<50}┤ {:>9} / {:<9}{:>12}'

    @property
    def total(self):
        return self._total

    @total.setter
    def total(self, total: int):
        self._total = total
        self.update()

    @property
    def progress(self):
        return self._progress

    @progress.setter
    def progress(self, progress: int):
        self._progress = progress
        self.update()

    @property
    def extra(self):
        return self._extra

    @extra.setter
    def extra(self, extra: str):
        self._extra = extra
        self.update()

    def update(self):
        if not self._show:
            self._show = True
        percentage = round(self._progress * 100 / self._total, 1)
        if percentage >= 100:
            percentage = 100
        bar_count = int(percentage) // 2
        if self._detail:
            progress, total = self._detail(self._progress), self._detail(self._total)
        else:
            progress, total = self._progress, self._total
        extra = '' if self._extra is None else self._extra
        line = self._formation.format(percentage, '█' * bar_count, progress, total, extra)
        sys.stdout.write('\r' + line)
        sys.stdout.flush()

    def increment(self, n: int):
        self._progress += n
        self.update()

    def done(self):
        if self._show:
            print()
            self._show = False


class MultiTaskManager(metaclass=ABCMeta):
    def __init__(self, num_threads: int = 1):
        self._queue = Queue()
        self._num_threads = num_threads
        self._threads = []

    @property
    def num_tasks(self):
        return self._queue.qsize()

    @property
    def num_threads(self):
        return self._num_threads

    @abstractmethod
    def add_tasks(self, *args, **kwargs):
        pass

    @abstractmethod
    def _start_task(self, item):
        pass

    def _start_all_tasks(self):
        while True:
            item = self._queue.get()
            if item is None:
                break
            try:
                self._start_task(item)
            except Exception as e:
                logging.error('error occurs when processing item: {}, skipping'.format(item))
                logging.exception(e)
            self._queue.task_done()

    def start(self):
        for _ in range(self._num_threads):
            t = threading.Thread(target=self._start_all_tasks)
            t.start()
            self._threads.append(t)

    def join(self):
        self._queue.join()
        for _ in range(self._num_threads):
            self._queue.put(None)
        for t in self._threads:
            t.join()
