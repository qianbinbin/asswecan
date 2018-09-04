import os
import threading
from abc import abstractmethod, ABCMeta
from typing import Union, Iterator
from urllib.parse import urlparse

from asswecan.utils import MultiTaskManager, ProgressBar, ensure_valid_path


class Barrage(metaclass=ABCMeta):
    def __init__(self, bid: str = None, url: str = None, title: str = None, out_dir: str = os.curdir,
                 content: str = None, file: str = None, ass: str = None, ass_file: str = None):
        self.bid = bid
        self.url = url
        self.title = title
        self.out_dir = out_dir
        self._content = content
        self.file = file
        self._ass = ass
        self.ass_file = ass_file

    @property
    def content(self):
        if not self._content:
            if self.file:
                with open(self.file) as f:
                    self._content = f.read()
            elif self.url:
                self._content = self.retrieve_content()
            else:
                raise RuntimeError('cannot load content, no file or url specified')
        return self._content

    @property
    def ass(self):
        if not self._ass:
            self._ass = self.to_ass()
        return self._ass

    @classmethod
    @abstractmethod
    def from_info(cls, *args, **kwargs):
        pass

    @classmethod
    def from_file(cls, file: str, out_dir: str = os.curdir, **kwargs):
        return cls(title=os.path.basename(file).rsplit('.', 1)[0], out_dir=out_dir, file=file, **kwargs)

    @abstractmethod
    def filename(self) -> str:
        pass

    @abstractmethod
    def retrieve_content(self) -> str:
        pass

    def save(self, force: bool = True) -> str:
        target_file = ensure_valid_path(self.out_dir, self.filename(), force)
        content = self.content
        with open(target_file, 'w') as f:
            f.write(content)
        if not self.file:
            self.file = target_file
        return target_file

    @abstractmethod
    def to_ass(self) -> str:
        pass

    def save_ass(self, force: bool = True) -> str:
        target_file = ensure_valid_path(self.out_dir, self.title + '.ass', force)
        ass = self.ass
        with open(target_file, 'w') as f:
            f.write(ass)
        if not self.ass_file:
            self.ass_file = target_file
        return target_file

    def __str__(self):
        return self.title

    def __hash__(self):
        if self.bid:
            return hash(self.bid)
        else:
            return hash(self.file)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            if self.bid:
                return self.bid == other.bid
            else:
                return self.file == other.file
        return False


class BarrageTaskManager(MultiTaskManager, metaclass=ABCMeta):
    def __init__(self, out_dir: str = os.curdir, save: bool = True, convert: bool = True,
                 all_pages: bool = False, num_threads: int = 4, show_bar: bool = True):
        super().__init__(num_threads)
        self.__LOCK = threading.Lock()
        self.__set = set()
        self._out_dir = out_dir
        self._save = save
        self._convert = convert
        self._all_pages = all_pages
        self._show_bar = show_bar
        if self._show_bar:
            self._bar = ProgressBar(0, extra='barrage(s)')

    def add_tasks(self, *items: Union[str, Barrage]):
        for item in items:
            self.__LOCK.acquire()
            if item not in self.__set:
                self._queue.put(item)
                self.__set.add(item)
            self.__LOCK.release()

    def _start_task(self, item: Union[str, Barrage]):
        if isinstance(item, str):
            p = urlparse(item)
            if (p.scheme == 'http' or p.scheme == 'https') and p.netloc:
                for result in self.process_url(item):
                    self.__LOCK.acquire()
                    if result not in self.__set:
                        self._queue.put(result)
                        self.__set.add(result)
                        if self._show_bar:
                            self._bar.total += 1
                    self.__LOCK.release()
            else:
                result = self.process_file(item)
                self.__LOCK.acquire()
                if result not in self.__set:
                    self._queue.put(result)
                    self.__set.add(result)
                    if self._show_bar:
                        self._bar.total += 1
                self.__LOCK.release()
        elif isinstance(item, Barrage):
            self.process_barrage(item)
            if self._show_bar:
                self._bar.progress += 1
        else:
            raise ValueError('unknown item: {}'.format(item))

    def _start_all_tasks(self):
        super()._start_all_tasks()
        if self._show_bar:
            self._bar.done()

    @abstractmethod
    def process_url(self, url: str) -> Iterator[Barrage]:
        pass

    @abstractmethod
    def process_file(self, file: str) -> Barrage:
        pass

    def process_barrage(self, brg: Barrage):
        if self._save:
            brg.save()
        if self._convert:
            brg.save_ass()
