# -*- coding: utf-8 -*-

import os
import logging
import threading
import tornado.ioloop

from monitor import Monitor
from models import Objects
from urls import Application
from tornado.log import LogFormatter
from tornado.options import define, options, parse_command_line

define("port", default=8020, help="run on the given port", type=int)
LOCKFILE = os.path.dirname(os.path.abspath(__file__)) + "/system.lock"

class LogFormatters(LogFormatter):
    '''
    定义日志
    '''
    def __init__(self):
        super(LogFormatters, self).__init__(
            fmt='%(color)s[%(asctime)s %(filename)s:%(funcName)s:%(lineno)d %(levelname)s]%(end_color)s %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )


class MyThread(threading.Thread):
    def __init__(self, interval, func):
        threading.Thread.__init__(self)
        self.func = func
        self.interval = interval
        self.finished = threading.Event()

    def cancel(self):
        self.finished.set()

    def run(self):
        while True:
            self.finished.wait(self.interval)
            if not self.finished.is_set():
                if not self.func(): break
            else:
                self.finished.set()
                break


def main():
    monitors = Monitor(LOCKFILE)
    mt = MyThread(60, monitors.skynet)
    try:
        parse_command_line()
        #Objects.database.allow_sync = False
        app = Application()
        [i.setFormatter(LogFormatters()) for i in logging.getLogger().handlers]
        # 脚本
        mt.start()
        app.listen(options.port)
        tornado.ioloop.IOLoop.current().start()
    except Exception as e:
        print(e)
    finally:
        mt.cancel()
        monitors.close()
        print('清理结束')

if __name__ == "__main__":
    main()
