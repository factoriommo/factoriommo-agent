import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from logrouter import router

class TestLogRouter(unittest.TestCase):

    def test_sanity(self):
        module = router.register('FOO')

        @module.route('BAR')
        def foobar(**req):
            return req

        res = router.req('FOO BAR test')
        self.assertEqual(res, dict(path='BAR', payload='test'))

if __name__ == '__main__':
    unittest.main()
