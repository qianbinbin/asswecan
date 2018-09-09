from unittest import TestCase

from asswecan.barrages.bilibili import *


class TestBilibili(TestCase):
    def __init__(self, method_name='runTest'):
        super().__init__(method_name)
        self.TEST_PATH = os.path.join(os.environ['HOME'], 'Downloads/asswecan')
        if not os.path.exists(self.TEST_PATH):
            os.makedirs(self.TEST_PATH, exist_ok=True)

    def test_bili_task_manager(self):
        manager = BiliTaskManager(self.TEST_PATH, convert=False, all_pages=True)
        manager.add_tasks(
            'https://www.bilibili.com/video/av2910036',  # single video page
            'https://www.bilibili.com/bangumi/play/ep204779',  # single episode of bangumi
            'https://www.bilibili.com/video/av30335311/?p=2',  # multi-video page 2
            'https://www.bilibili.com/bangumi/play/ep199612',  # movie page
            'https://space.bilibili.com/268990278/#/',  # user space
            'https://space.bilibili.com/927587/#/favlist?fid=442293',  # favorite list
            'https://space.bilibili.com/927587/#/favlist?fid=570027',  # favorite list multi-pages
        )
        manager.start()
        manager.join()
