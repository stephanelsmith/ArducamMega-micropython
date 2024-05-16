

class DebugMixin:
    def debug(self, *args):
        if self._name:
            print(self._name,end='')
        for el in args:
            print(' | ',end='')
            print(el,end='')
        print('')
    async def adebug(self, *args):
        if self._name:
            print(self._name,end='')
        for el in args:
            print(' | ',end='')
            print(el,end='')
        print('')

