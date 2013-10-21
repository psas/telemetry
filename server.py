import tornado.ioloop
import tornado.web
import tornado.websocket
import time
import config
import json
import os

clients = []


class MainHandler(tornado.web.RequestHandler):

    def get(self):
        self.render('client.html')


class FrontEndWebSocket(tornado.websocket.WebSocketHandler):

    def open(self):
        if self not in clients:
            clients.append(self)

    def on_message(self, message):
        pass

    def on_close(self):
        if self in clients:
            clients.remove(self)



class Webservice(object):

    def __init__(self, queue):
        static_path = os.path.join(os.path.dirname(__file__), 'static')
        self.application = tornado.web.Application([
                (r'/', MainHandler),
                (r'/ws', FrontEndWebSocket),
                (r'/(.*)', tornado.web.StaticFileHandler, dict(path=static_path)),
            ], template_path=static_path, static_path=static_path)
        self.queue = queue
        self.application.listen(config.APP_PORT)
        self.ioloop = tornado.ioloop.IOLoop.instance()
        sched = tornado.ioloop.PeriodicCallback(self.flush, config.FLUSH_RATE, io_loop=self.ioloop)
        sched.start()
        self.packets = 0
        self.last_seqn = 0
        self.last_packet_recv = time.time() #TODO: more sane init
        self.missed = 0

    def flush(self):
        packets = 0
        seqn = 0
        missed = 0
        adis = 0
        adist = 0
        adisn = 0

        packed_data = []
        while not self.queue.empty():
            for x in self.queue.get():
                if x.get('fieldID') == 'SEQN':
                    packets += 1
                    self.packets += 1
                    seqn = x.get('n')
                    missed = (seqn - self.last_seqn) - 1

                    self.last_seqn = seqn
                    self.last_packet_recv = x.get('recv')
                #elif x.get('fieldID') == 'ADIS':
                #    adis = x['Acc_X']
                #    adist += adis
                #    adisn += 1
                else:
                    packed_data.append(x)
                #for client in clients:
                #    client.write_message(json.dumps(x))

        self.missed += missed
        droprate = 0
        if packets:
            droprate = missed/float(packets+missed) * 100
        now = time.time()
        obj = {
          'fieldID': 'Stats',
          'PacketsReceivedTotal': self.packets,
          'PacketsLostTotal': self.missed,
          'PacketsReceivedRecently': packets,
          'PacketsLostRecently': missed,
          'MostRecentTimestamp': now,
          'TimeLastPacketReceived': now - self.last_packet_recv,
          'PacketRate': packets/float(config.FLUSH_RATE) * 1000,
          'DropRate': droprate,
          'CurrentSeqn': seqn,
        }

        #if adisn:
        #    for client in clients:
        #        client.write_message(json.dumps({'fieldID': 'ADIS', 'Acc_X_avg': adist / float(adisn), 'Acc_X': adis}))

        for client in clients:
            client.write_message(json.dumps(obj))
        for client in clients:
            client.write_message(json.dumps({'data': packed_data}))
        
    def run(self):
        self.ioloop.start()
