# -*- coding: utf-8 -*-
import pymysql
import time
import os

class Monitor:
    def __init__(self, path):
        self.db = pymysql.Connection(host='127.0.0.1', database='blog', user='root', password='Nkx.29083X', charset='utf8')
        self.sql = """insert into skynet (min1,min5,min15,uscpu,sycpu,total,used,free,netin,netout,create_time) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
        self.cursor = self.db.cursor(cursor=pymysql.cursors.DictCursor)
        self.netstatus = False
        self.lastin = 0
        self.lastout = 0
        self.path = path
        self.LockFile(True, self.path)

    def LockFile(self, val, lockpath):
        if val and not os.path.isfile(lockpath):
            with open(lockpath, 'w') as f:
                f.close()
        elif not val and os.path.isfile(lockpath):
            os.remove(lockpath)

    def skynet(self):
        if os.path.isfile(self.path):
            try:
                loads = os.popen('uptime').read()
                loads = loads.split()
                min1 = float(loads[-3].split(',')[0])
                min5 = float(loads[-2].split(',')[0])
                min15 = float(loads[-1].split(',')[0])
            except:
                min1 = min5 = min15 = 0
            finally:
                if min15 > 1:
                    print('WARING!!!')

            try:
                cpus = os.popen("top -b -n 1 |grep Cpu").read()
                cpus = cpus.split()
                uscpu = float(cpus[1].split('%')[0])
                sycpu = float(cpus[2].split('%')[0])
            except:
                uscpu = sycpu = 0
            finally:
                if uscpu + sycpu > 90:
                    print('WARING!!!')

            try:
                memory = os.popen("free -m | grep Mem").read()
                memory = memory.split()
                total = int(memory[1])
                used = int(memory[2])
                free = int(memory[3])
            except:
                total = 1
                used = free = 0
            finally:
                if used / total > 0.9:
                    print('WARING!!!')

            try:
                net = os.popen("cat /proc/net/dev | grep eth").read()
                net = net.split()
                if self.netstatus:
                    netin = int(net[2]) - self.lastin
                    netout = int(net[10]) - self.lastout
                else:
                    netin = netout = 0
                    self.netstatus = True
                self.lastin = int(net[2])
                self.lastout = int(net[10])
            except:
                netin = netout = 0

            create_time = time.strftime('%Y-%m-%d %H:%M:%S')
            number = self.cursor.execute(self.sql,(min1,min5,min15,uscpu,sycpu,total,used,free,netin,netout,create_time))
            return True
        else:
            return False

    def close(self):
        self.LockFile(False, self.path)
        self.cursor.close()
