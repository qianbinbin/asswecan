import logging
import mimetypes
import os
import re
import socket
import time
import urllib.parse
import zlib
from http.client import HTTPResponse
from typing import Dict, Union, Tuple, Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from asswecan.utils import ProgressBar, readable_size, ensure_valid_path


def fake_headers() -> Dict[str, str]:
    return {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Charset': 'utf-8,*;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'utf-8, *;q=0.5',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36'
    }


def urlopen_with_retry(url: Union[str, Request], retry: int = 3, **kwargs) -> HTTPResponse:
    logging.debug('urlopen, request {}'.format(url))
    for i in range(retry):
        try:
            return urlopen(url, **kwargs)
        except socket.timeout as e:
            logging.info('request attempt {} timeout'.format(i + 1))
            if i + 1 == retry:
                raise e
        except HTTPError as e:
            logging.info('HTTPError with code {}'.format(e.code))
            if i + 1 == retry:
                raise e


def url_get_content(url: Union[str, Request], decode: bool = True, **kwargs) -> Union[bytes, str]:
    logging.debug('get content, request {}'.format(url))
    response = urlopen_with_retry(url, **kwargs)
    data = response.read()

    content_encoding = response.headers['Content-Encoding']
    if content_encoding == 'gzip':
        data = zlib.decompress(data, zlib.MAX_WBITS | 16)
    elif content_encoding == 'deflate':
        try:
            data = zlib.decompress(data)
        except zlib.error:
            logging.debug('cannot decompress, treat as deflate data')
            data = zlib.decompress(data, -zlib.MAX_WBITS)
    elif content_encoding:
        raise NotImplementedError('unknown encoding: ' + content_encoding)

    if decode:
        charset = None
        content_type = response.headers['Content-Type']
        if content_type:
            m = re.search(r'charset=([\w-]+)', content_type)
            if m:
                charset = m.group(1)
        if charset:
            data = data.decode(charset)
        else:
            data = data.decode('utf-8', 'ignore')
    return data


def url_save_guess_file(url: Union[str, Request], **kwargs) -> Tuple[str, Optional[int]]:
    logging.debug('guess file, request {}'.format(url))
    name, size = None, None
    with urlopen_with_retry(url, **kwargs) as response:
        if response.headers['Content-Disposition']:
            m = re.search(r'filename="(.+)"', response.headers['Content-Disposition'])
            if m:
                name = m.group(1)
        if not name:
            name = urllib.parse.unquote(os.path.basename(urllib.parse.urlparse(response.geturl()).path))
            if not name:
                name = 'file'
                ext = mimetypes.guess_extension(response.headers['Content-Type'].rsplit(';', 1)[0])
                if ext:
                    name += ext
        if response.headers['Content-Length']:
            size = int(response.headers['Content-Length'])
    logging.debug('guess file, name={}, size={}'.format(name, size))
    return name, size


def url_save(url: str, headers: Dict[str, str] = None,
             out_dir: str = os.curdir, filename: str = None,
             force: bool = False, show_bar: bool = False, **kwargs) -> Tuple[str, int]:
    logging.debug(
        'url save, url={}, headers={}, out={}, file={}, force={}, show_bar={}'.format(
            url, headers, out_dir, filename, force, show_bar
        )
    )
    if headers is None:
        headers = {}
    name, total_size = url_save_guess_file(Request(url, headers=headers), **kwargs)
    if total_size is None:
        total_size = float('inf')

    if filename is None:
        filename = name
    file_path = ensure_valid_path(out_dir, filename, force)

    mode = 'wb'
    part_file = file_path + '.part' if total_size != float('inf') else file_path
    part_size = 0
    if os.path.exists(part_file):
        part_size = os.path.getsize(part_file)
        if 0 < part_size < total_size:
            logging.info('\'.part\' file already exists, try to append')
            mode = 'ab'
        else:
            part_size = 0

    bar = None
    if show_bar:
        bar = DownloadBar(total_size, part_size)
        bar.update()

    if part_size < total_size:
        if part_size:
            headers['Range'] = 'bytes={}-'.format(part_size)
        response = urlopen_with_retry(Request(url, headers=headers), **kwargs)
        remaining_size = float('inf')
        if response.headers['Content-Range']:
            m = re.search(r'(\d+)-(\d+)/(\d+)$', response.headers['Content-Range'])
            remaining_size = int(m.group(3)) - int(m.group(1))
        elif response.headers['Content-Length']:
            remaining_size = int(response.headers['Content-Length'])
        if part_size + remaining_size != total_size:
            logging.info('\'.part\' file inconsistent with server, retrieving')
            part_size = 0
            mode = 'wb'
            if show_bar:
                bar.progress = part_size
        with open(part_file, mode) as f:
            while part_size < total_size:
                buffer = None
                try:
                    buffer = response.read(512 * 1024)
                except socket.timeout:
                    logging.info('timeout during downloading, retrying')
                    pass
                if buffer:
                    f.write(buffer)
                    part_size += len(buffer)
                    if show_bar:
                        bar.increment(len(buffer))
                else:
                    if part_size >= total_size or total_size == float('inf'):
                        break
                    headers['Range'] = 'bytes={}-'.format(part_size)
                    response = urlopen_with_retry(Request(url, headers=headers), **kwargs)
    if show_bar:
        bar.done()
    assert part_size == os.path.getsize(part_file)
    if part_file != file_path:
        if os.access(file_path, os.W_OK):
            os.remove(file_path)
        os.rename(part_file, file_path)
    logging.debug('downloading completed, file={}, size={}'.format(file_path, part_size))
    return file_path, part_size


class DownloadBar(ProgressBar):
    def __init__(self, total: int = 100, progress: int = 0):
        super().__init__(total, progress, readable_size)
        self.unix_time = time.time()

    def increment(self, n: int):
        t = time.time()
        self._extra = '{}/s'.format(readable_size(int(n // (t - self.unix_time))))
        super().increment(n)
        self.unix_time = t

    def done(self):
        if self._extra:
            self._extra = None
            self.update()
        super().done()
