import sys, os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import test
print (test.__file__)
# suite = test.suite

if __name__ == '__main__':
    test.main()
