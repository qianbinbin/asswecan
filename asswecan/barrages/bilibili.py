import json
import logging
import os
import re
from typing import Iterator
from urllib.parse import parse_qsl, urlparse
from urllib.request import Request

from asswecan.barrages.barrage import Barrage, BarrageTaskManager
from asswecan.net import url_get_content, fake_headers

URL_AV = 'https://www.bilibili.com/video/av{}'

# API_COMMENT = 'https://api.bilibili.com/x/v1/dm/list.so?oid={}'

API_COMMENT = 'https://comment.bilibili.com/{}.xml'

API_SUBMISSION = 'https://space.bilibili.com/ajax/member/getSubmitVideos?mid={}&pagesize={}&page={}'

API_ALL_FAV = 'https://api.bilibili.com/x/space/fav/nav?mid={}'

API_FAV = 'https://api.bilibili.com/x/space/fav/arc?vmid={}&ps={}&fid={}&pn={}'

SUBTITLE = '{}_#{}_{}'


class BiliBarrage(Barrage):
    @classmethod
    def from_info(cls, bid: str, title: str, out_dir: str = os.curdir, **kwargs):
        return cls(bid, API_COMMENT.format(bid), title, out_dir, **kwargs)

    def filename(self):
        return self.title + '.xml'

    def retrieve_content(self) -> str:
        return url_get_content(Request(self.url, headers=fake_headers()))

    def to_ass(self) -> str:
        raise NotImplementedError


class BiliTaskManager(BarrageTaskManager):
    def process_url(self, url: str) -> Iterator[BiliBarrage]:
        pr = urlparse(url)
        if re.match(r'/video/av\d+/?$', pr.path) or re.match(r'/bangumi/play/ep\d+/?$', pr.path):
            yield from self.__video2barrages(url)
        elif pr.netloc == 'space.bilibili.com' and re.match(r'/\d+/?$', pr.path):
            mid = re.match(r'/(\d+)?/', pr.path).group(1)
            if pr.fragment.startswith('/favlist'):
                fid = re.match(r'/favlist\?fid=(\d+)?', pr.fragment)
                if fid:
                    yield from self.__fav2barrages(mid, fid.group(1))
                else:
                    fav_info = url_get_content(Request(API_ALL_FAV.format(mid), headers=fake_headers()))
                    fav_info = json.loads(fav_info)
                    for fav in fav_info['data']['archive']:
                        yield from self.__fav2barrages(mid, fav['fid'])
            else:
                p, pages = 1, 1
                while p <= pages:
                    sub_info = url_get_content(Request(API_SUBMISSION.format(mid, 100, p), headers=fake_headers()))
                    sub_info = json.loads(sub_info)
                    pages = int(sub_info['data']['pages'])
                    for video_info in sub_info['data']['vlist']:
                        yield from self.__video2barrages(URL_AV.format(video_info['aid']))
                    p += 1
        else:
            raise NotImplementedError('unknown url: {}'.format(url))

    def __video2barrages(self, url: str) -> Iterator[BiliBarrage]:
        html = url_get_content(Request(url, headers=fake_headers()))
        info = json.loads(re.search(r'__INITIAL_STATE__=(.*?);\(function\(\)', html).group(1))
        if 'videoData' in info:
            if 'title' not in info['videoData']:
                logging.warning(info['error'])
                return
            title = info['videoData']['title']
            pages = info['videoData']['pages']
            if self._all_pages:
                if len(pages) > 1:
                    for p in range(len(pages)):
                        full_title = SUBTITLE.format(title, p + 1, pages[p]['part'])
                        yield BiliBarrage.from_info(str(pages[p]['cid']), full_title, self._out_dir)
                else:
                    yield BiliBarrage.from_info(str(info['videoData']['cid']), title, self._out_dir)
            else:
                if len(pages) > 1:
                    p = 0
                    pr = urlparse(url)
                    q = dict(parse_qsl(pr.query))
                    if 'p' in q:
                        p = int(q['p']) - 1
                    full_title = SUBTITLE.format(title, p + 1, pages[p]['part'])
                    yield BiliBarrage.from_info(str(pages[p]['cid']), full_title, self._out_dir)
                else:
                    yield BiliBarrage.from_info(str(info['videoData']['cid']), title, self._out_dir)
        elif 'mediaInfo' in info:
            title = info['mediaInfo']['title']
            ep_info = info['epInfo']
            ep_list = info['epList']
            if self._all_pages:
                if len(ep_list) > 1:
                    for p in range(len(ep_list)):
                        full_title = SUBTITLE.format(title, p + 1, ep_list[p]['index_title'])
                        yield BiliBarrage.from_info(str(ep_list[p]['cid']), full_title, self._out_dir)
                else:
                    yield BiliBarrage.from_info(str(ep_info['cid']), title, self._out_dir)
            else:
                if len(ep_list) > 1:
                    full_title = SUBTITLE.format(title, ep_info['index'], ep_info['index_title'])
                    yield BiliBarrage.from_info(str(ep_info['cid']), full_title, self._out_dir)
                else:
                    yield BiliBarrage.from_info(str(ep_info['cid']), title, self._out_dir)
        else:
            raise RuntimeError('cannot parse page: {}'.format(url))

    def __fav2barrages(self, mid: str, fid: str) -> Iterator[BiliBarrage]:
        p, pages = 1, 1
        while p <= pages:
            fav_info = json.loads(url_get_content(Request(API_FAV.format(mid, 30, fid, p), headers=fake_headers())))
            # require login
            if not fav_info['data']:
                logging.warning(fav_info)
                break
            pages = fav_info['data']['pagecount']
            for video in fav_info['data']['archives']:
                if video['videos'] == 1:
                    if 'cid' in video:
                        yield BiliBarrage.from_info(str(video['cid']), video['title'], self._out_dir)
                    else:
                        logging.warning('cannot parse data, video may be removed, skipping')
                        logging.warning(video)
                else:
                    yield from self.__video2barrages(URL_AV.format(video['aid']))
            p += 1

    def process_file(self, file: str) -> BiliBarrage:
        return BiliBarrage.from_file(file, self._out_dir)
