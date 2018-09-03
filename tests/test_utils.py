import random
import time
from unittest import TestCase

from asswecan.utils import *


class TestUtils(TestCase):
    def __init__(self, method_name='runTest'):
        super().__init__(method_name)
        self.TEST_PATH = os.path.join(os.environ['HOME'], 'Downloads/asswecan')
        if not os.path.exists(self.TEST_PATH):
            os.makedirs(self.TEST_PATH, exist_ok=True)

    def test_ensure_valid_path(self):
        self.assertEqual(
            os.path.join(self.TEST_PATH, '【木鱼微剧场】《Legal High_胜者即是正义》（P13）白色巨塔下的医疗纠纷案.xml'),
            ensure_valid_path(self.TEST_PATH, '【木鱼微剧场】《Legal High/胜者即是正义》（P13）白色巨塔下的医疗纠纷案.xml')
        )

    def test_readable_size(self):
        print(readable_size(1023))
        print(readable_size(1024 * 1024 * 1124))

    def test_progress_bar(self):
        bar = ProgressBar()
        bar.update()
        time.sleep(0.5)
        bar.increment(10)
        time.sleep(0.5)
        bar.increment(20)
        time.sleep(0.5)
        bar.extra = 'test extra'
        bar.progress += 69
        time.sleep(0.5)
        bar.increment(1)
        bar.done()

    def test_multi_task_manager(self):
        class DownloadManager(MultiTaskManager):
            def add_tasks(self, *items: str):
                for item in items:
                    self._queue.put(item)

            def _start_task(self, item: str):
                print('downloading:', item)
                if random.randint(0, 1) == 0:
                    1 / 0
                time.sleep(0.5)
                print('done:', item)

        d = DownloadManager(4)
        d.start()
        print('downloader started with {} threads'.format(d.num_threads))
        d.add_tasks(*[str(i) for i in range(1, 11)])
        print('{} tasks added, waiting for processing'.format(d.num_tasks))
        d.join()
        print('all tasks done')
