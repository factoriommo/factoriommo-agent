from factoriomcd.rcon import RconConnection

from configargparse import ArgParser
from ws4py.client.threadedclient import WebSocketClient

from multiprocessing import Value
from threading import Thread
from time import sleep, time
from queue import Queue, Empty

import asyncio
import coloredlogs
import logging
import json
import re
import os


CHAT_LOG_REGEX = re.compile(r'^(?P<year>\d{4})\-(?P<month>\d{2})\-(?P<day>\d{2}) (?P<hour>\d{2})\:(?P<minute>\d{2})\:(?P<second>\d{2}) (?P<namespace>\[\w+\]) (?P<username>\S+)\: (?P<message>.+)$')  # noqa

logger = logging.getLogger(__name__)


class LogReaderThread(Thread):
    def __init__(self, options):
        super(LogReaderThread, self).__init__()
        self.options = options
        self.running = Value('b', True)
        self.q = Queue()
        self.chat = Queue()

    def run(self):
        logger.debug("Booted log reader thread")
        f = open(self.options.log_file)
        file_len = os.stat(self.options.log_file)[6]
        f.seek(file_len)
        pos = f.tell()
        counter = 0
        last_count = time()

        while self.running.value:
            pos = f.tell()
            line = f.readline()
            if not line:
                if os.stat(self.options.log_file)[6] < pos:
                    f.close()
                    f = open(self.options.log_file)
                    pos = f.tell()
                else:
                    sleep(0.1)
                    f.seek(pos)

            elif line.startswith('##FMC::'):
                line = line.strip()
                logger.debug('Line processed: %s', line)
                self.q.put(line.lstrip('##FMC::'))
            else:
                line = line.strip()
                m = CHAT_LOG_REGEX.match(line)
                if m:
                    items = m.groupdict()
                    logger.debug("Got a line of chat: %s", items)
                    self.chat.put(items)
                else:
                    logger.debug("Line found but not processed: %s", line)

            if line:
                counter += 1

            if (time() - 10.0) > last_count:
                time_passed = time() - last_count
                avg = counter / time_passed
                logger.info("Logreader read: %d lines, %f lines/s in %f seconds.", counter, avg, time_passed)

                last_count = time()
                counter = 0

        f.close()


class RconSenderThread(Thread):
    def __init__(self, options):
        super(RconSenderThread, self).__init__()
        self.options = options
        self.running = Value('b', True)
        self.q = Queue()
        self.connected = False

    @asyncio.coroutine
    def exec_command(self, cmd):
        reconnected = False
        try:
            logger.debug("Sending command to rcon: %s", cmd)
            yield from self.conn.exec_command(cmd)
        except:
            logger.exception("Error sending command to rcon")
            while not reconnected and self.running.value:
                try:
                    self.conn = RconConnection(self.options.rcon_host, int(self.options.rcon_port),
                                               self.options.rcon_password)
                    yield from self.conn.exec_command("/silent-command print('FactorioMCd connected.')")
                    yield from self.conn.exec_command("/silent-command print('FactorioMCd connected.')")
                    reconnected = True
                    self.connected = True
                except:
                    logger.exception("Error reconnecting...")
                    sleep(1)

            reconnected = False
            yield from self.conn.exec_command(cmd)

    def run(self):
        logger.debug("Booted rcon sender thread")
        policy = asyncio.get_event_loop_policy()
        policy.set_event_loop(policy.new_event_loop())
        loop = asyncio.get_event_loop()
        last_data = time()

        try:
            self.conn = RconConnection(self.options.rcon_host, int(self.options.rcon_port), self.options.rcon_password)
            resp = loop.run_until_complete(self.conn.exec_command("/silent-command print('FactorioMCd connected.')"))
            resp = loop.run_until_complete(self.conn.exec_command("/silent-command print('FactorioMCd connected.')"))
            self.connected = True
        except:
            logger.exception("Could not connect to rcon, retry delayed.")

        while self.running.value:
            try:
                data = self.q.get(timeout=3)
                last_data = time()
            except Empty:
                data = None

            if not data:
                if (time() - last_data) > 30 and self.connected:
                    try:
                        self.conn.close()
                        self.connected = False
                        logger.info("RCON connection closed (volentarily) due to timeout")
                    except:
                        logger.exception("Error closing connection.")
                sleep(0.1)
            else:
                resp = loop.run_until_complete(self.exec_command(data))
                logger.debug(resp)


class MasterConnectionClient(WebSocketClient):
    def __init__(self, url, parent, **kwargs):
        super(MasterConnectionClient, self).__init__(url, **kwargs)
        self.parent = parent

    def opened(self):
        self.parent.needs_reconnect = False
        logger.debug("Websocket connection established!")
        self.send(json.dumps({
            'namespace': 'auth',
            'data': {
                'token': self.parent.options.ws_password
            }
        }))

    def closed(self, code, reason=None):
        logger.info("Websocket to master closed with code %i, reason: %s", code, reason)
        self.parent.needs_reconnect = True

    def received_message(self, m):
        try:
            decoded = json.loads(str(m))
            if not decoded.get('namespace', False) == 'auth':
                logger.debug("Got a websocket message: %s", decoded)
                self.parent.from_server.put(decoded)
            else:
                logger.debug("Auth response: %s", decoded)
        except:
            logger.exception("Could not decode json message: %s", str(m))


class MasterConnectionThread(Thread):
    def __init__(self, options):
        super(MasterConnectionThread, self).__init__()
        self.options = options
        self.running = Value('b', True)
        self.from_server = Queue()
        self.to_server = Queue()
        self.needs_reconnect = True

    def run(self):
        logger.debug("Booting master connection websocket thread")

        self.client = MasterConnectionClient(self.options.ws_url, self, protocols=['http-only', 'chat'])
        while self.running.value:
            if self.needs_reconnect:
                try:
                    logger.info("Reconnecting websockets")
                    self.client.connect()
                    sleep(3)
                except:
                    pass
            try:
                data = self.to_server.get(timeout=3)
                logger.debug("Sending data to ws: %s", data)
                self.client.send(json.dumps(data))
            except Empty:
                data = None
                sleep(0.1)

        self.client.close()


class FactorioMCd:
    def __init__(self, options):
        self.options = options

    def run(self):
        self.log = LogReaderThread(self.options)
        self.rcon = RconSenderThread(self.options)
        self.ws = MasterConnectionThread(self.options)

        self.log.start()
        self.rcon.start()
        self.ws.start()

        try:
            self.main_loop()
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt caught: terminating...")
        finally:
            self.log.running.value = False
            self.rcon.running.value = False
            self.ws.running.value = False

            logger.debug("Stopping log thread")
            self.log.join()
            logger.debug("Stopping rcon thread")
            self.rcon.join()
            logger.debug("Stopping master connection websocket thread")
            self.ws.join()

        logger.info("Terminated.")

    def main_loop(self):
        logger.debug("In main loop")
        while True:
            sleeptime = 0.1
            if self.options.debug:
                import ipdb
                ipdb.set_trace()

            try:
                logdata = self.log.q.get(False)
                self.parse_logdata(logdata)
                sleeptime = 0.1
            except Empty:
                sleeptime = 0.5
            except:
                logger.exception("Something went wrong handling some log data")

            try:
                chatdata = self.log.chat.get(False)
                self.parse_chatdata(chatdata)
                sleeptime = 0.1
            except Empty:
                if sleeptime != 0.1:
                    sleeptime = 0.5
            except:
                logger.exception("Something went wrong handling some chat data")

            try:
                wsdata = self.ws.from_server.get(False)
                self.parse_wsdata(wsdata)
                sleeptime = 0.1
            except Empty:
                if sleeptime != 0.1:
                    sleeptime = 0.5
            except:
                logger.exception("Something went wrong handling some ws data")

            sleep(sleeptime)

    def parse_chatdata(self, data):
        if data.get('namespace', False):
            del data['namespace']

        self.ws.to_server.put({
            "namespace": "chat",
            "data": data
        })

    def parse_logdata(self, data):
        splitted = data.split("::")
        key = splitted[0]
        value = "::".join(splitted[1:])
        if key in ['science-pack-1', 'science-pack-2', 'science-pack-3', 'alien-science-pack']:
            value = int(value)
            if value <= 0:
                return
            self.ws.to_server.put({
                "namespace": "consumption",
                "data": {
                    "type": key,
                    "data": value
                }
            })
        elif key in ['productivity-module-3', 'efficiency-module-3', 'speed-module-3']:
            value = int(value)
            if value <= 0:
                return
            self.ws.to_server.put({
                "namespace": "production",
                "data": {
                    "type": key,
                    "data": value
                }
            })
        elif key in ['player-online-count', 'rocket-progress']:
            value = int(value)
            if value < 0:
                return
            self.ws.to_server.put({
                "namespace": "updatecounter",
                "data": {
                    "type": key,
                    "data": value
                }
            })
        elif key in ['player_joined', 'player_left']:
            logger.debug("Sending player event for %s : %s", key, value)
            self.ws.to_server.put({
                "namespace": "event",
                "data": {
                    "type": key,
                    "data": {
                        "playername": value
                    }
                }
            })
        elif key == 'rocket_launched':
            logger.debug("Sending player event for %s : %s", key, value)
            self.ws.to_server.put({
                "namespace": "event",
                "data": {"type": key}
            })
        elif key in ['rocket-silo-built', 'rocket-silo-mined']:
            logger.debug("Sending event for rocket built")
            self.ws_to_server.put({
                "namespace": "event",
                "data": {
                    "type": "rocket-silo-built",
                    "playername": value
                }
            })
        else:
            logger.debug("Left data with key %s untouched, value: %s", key, value)

    def parse_wsdata(self, data):
        namespace = data.get('namespace')
        if not namespace:
            return

        if namespace == 'chat':
            self.broadcast_message_ingame(data['data']['msg'])

        elif namespace == 'scores':
            enemy_scores = None
            idata = data['data']
            for k, v in idata.items():
                if str(k) == str(self.options.server_id):
                    continue
                else:
                    enemy_scores = v
                    break

            if not enemy_scores:
                return

            for k, v in enemy_scores.items():
                if k == 'players-online':
                    try:
                        self.send_enemy_score('player-online-count', v)
                    except ValueError:
                        pass
                elif k in ['science-pack-1', 'science-pack-2', 'science-pack-3', 'alien-science-pack',
                           'rocket-progress', 'productivity-module-3', 'efficiency-module-3', 'speed-module-3']:
                    try:
                        self.send_enemy_score(k, int(v))
                    except ValueError:
                        pass
        elif namespace == 'victory':
            try:
                winner = bool(data['data']['winner'])
                if winner:
                    self.rcon.q.put("/silent-command remote.call('rconstats', 'callvictory', true)")
                else:
                    self.rcon.q.put("/silent-command remote.call('rconstats', 'callvictory', false)")
            except:
                logger.exception("Error parsing victory command")

        elif namespace == 'rconcommand':
            try:
                self.rcon.q.put(data['data'])
            except:
                pass

    def broadcast_message_ingame(self, message):
        self.rcon.q.put("#GLOBAL: " + message)

    def send_enemy_score(self, key, value):
        self.rcon.q.put('/silent-command remote.call("rconstats", "updatestats", "{0}", "{1}")'.format(key, value))


def main():
    parser = ArgParser(default_config_files=['/etc/factoriomcd.ini', '~/.factoriomcd.ini'])
    parser.add('-d', '--debug', action='store_true')
    parser.add('-v', '--verbose', action='store_true')

    parser.add('--log-file', default="/opt/factorio/server.out")

    parser.add('--server-id', default="1")

    parser.add('--rcon-host', default="localhost")
    parser.add('--rcon-password', default="asdasd")
    parser.add('--rcon-port', default=31337)

    parser.add('--ws-url', default="ws://127.0.0.1:8000/ws_v1/server_callback/1/")
    parser.add('--ws-password', default="asdasd")

    options = parser.parse_args()
    if options.verbose:
        coloredlogs.install(level='DEBUG')
        logger.debug("FactorioMCd initializing...")
    else:
        coloredlogs.install(level='INFO')

    FactorioMCd(options).run()


if __name__ == "__main__":
    main()
