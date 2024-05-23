
import asyncio


class SocketClosed(Exception):
    pass

async def cancel_gather_wait_for_ms(tasks, timeout_ms=1000):
    for t in filter(lambda t: t and not t.done(), tasks):
        t.cancel()
    await gather_wait_for_ms(tasks      = tasks,)

async def gather_wait_for_ms(tasks, timeout_ms=1000):
    #gather CAN definitely wait forever and lockup. <<<<<<<<<<<<<
    #cancel one-by-one, gather's runtime error will abort entire gather
    #surround with wait_for to prevent lockup
    errs = []
    for t in filter(lambda t: t and not t.done(), tasks):
        try:
            await asyncio.wait_for_ms(asyncio.gather(t, return_exceptions=True), timeout_ms)
        except RuntimeError as err:
            # trap "RuntimeError: can't gather"
            # this is thrown if task is done.  Very hard to guarantee pure atomic behavior between
            # checking for done and running gather. Micropython devs don't want to skip done tasks.
            # Being EXPLICIT with this is protection to make sure we never err out because gathering done task
            pass
        except asyncio.TimeoutError as err:
            if not t.done():
                errs.append((repr_task(t), err))
        except Exception as err:
            if not t.done():
                errs.append((repr_task(t), err))
    if errs:
        raise Exception('GATHER ERRS:'+str(errs))

def byteify_pkt(pkt):
    if isinstance(pkt, (bytes, bytearray, memoryview)):
        return pkt
    elif isinstance(pkt, uctypes.struct): #ctypes
        return bytes(pkt)
    elif hasattr(pkt, 'pkt'):
        return byteify_pkt(pkt.pkt)
    # elif isinstance(pkt, str):
        # return bytes(pkt,'utf8')
        # # return pkt
    # elif isinstance(pkt, (list, dict)):
        # j = ujson.dumps(pkt) #convert object to string
        # return bytes(j,'utf8')
    else:
        raise Exception('CANT BYTIFY PKT {}'.format(pkt))

