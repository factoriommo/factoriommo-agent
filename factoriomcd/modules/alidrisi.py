from logrouter import router

# class AlidrisiHandler:
module = router.register('ALI')

@module.route('CHNK')
def chunk(**req):
    print(req)

@module.route('TICK')
def tick(**req):
    print('tick %s' % req['payload'])
