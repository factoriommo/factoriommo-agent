# Integration with viceroypenguin's stats
# API info https://gist.github.com/viceroypenguin/82615fe83e17e2517e8ae982565d6c2b

from logrouter import router
import requests # http://docs.python-requests.org/

# TODO: Move this to config plz
VP_API_HOST = 'http://factoriommostatsdb.azurewebsites.net'

module = router.register('STATS')

@module.route('DEATH')
def death(**req):
    print("Lyfe got rekt")
    r = requests.post('%s/deaths' % VP_API_HOST, data = req.payload)
