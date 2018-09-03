import hashlib
from unittest import TestCase

from asswecan.net import *


class TestNet(TestCase):
    URL_MD5 = 'https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/MD5SUMS'
    URL_IMG = 'https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-9.5.0-amd64-netinst.iso'

    def __init__(self, method_name='runTest'):
        super().__init__(method_name)
        self.TEST_PATH = os.path.join(os.environ['HOME'], 'Downloads/asswecan')
        if not os.path.exists(self.TEST_PATH):
            os.makedirs(self.TEST_PATH, exist_ok=True)

    def test_fake_headers(self):
        headers = fake_headers()
        for key in headers:
            print('{}: {}'.format(key, headers[key]))

    def test_urlopen_with_retry(self):
        pass

    def test_url_content(self):
        expected = ('f8446a84356a6bcbf79201cc9f46063f  debian-9.5.0-amd64-netinst.iso\n'
                    '47a5dca818220d8558d37dfa11b85550  debian-9.5.0-amd64-xfce-CD-1.iso\n'
                    '2daa085925a556d35a0eeb27768cc892  debian-mac-9.5.0-amd64-netinst.iso\n')
        self.assertEqual(expected, url_get_content(self.URL_MD5))

    def test_url_save_guess_file(self):
        self.assertEqual(('debian-9.5.0-amd64-netinst.iso', 305135616), url_save_guess_file(self.URL_IMG))

    def test_url_save(self):
        print('Downloading', self.URL_IMG)
        file, size = url_save(self.URL_IMG, out_dir=self.TEST_PATH, show_bar=True)
        print('Saved as {}, size is {}'.format(file, readable_size(size)))

        page = url_get_content(self.URL_MD5)
        md5_expected = re.search(r'^(.+) {2}debian-9\.5\.0-amd64-netinst\.iso', page).group(1)

        md5_actual = hashlib.md5()
        with open(file, "rb") as f:
            buffer = f.read(512 * 1024)
            while buffer:
                md5_actual.update(buffer)
                buffer = f.read(512 * 1024)

        self.assertEqual(md5_expected, md5_actual.hexdigest())

    def test_download_bar(self):
        bar = DownloadBar(1024 * 1024 * 100)
        bar.update()
        time.sleep(0.5)
        bar.increment(1024 * 1024 * 10)
        time.sleep(0.5)
        bar.increment(1024 * 1024 * 20)
        time.sleep(0.5)
        bar.progress = 1024 * 1024 * 99
        bar.progress = bar.total
        bar.done()
