import argparse
import asyncio
import random
import signal
import sys
import time
import traceback
import yaml
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtNetwork import *
from PyQt5.QtWidgets import *

from b4 import *


class B4:
    conf = dict()
    groups = dict()
    room_names = 's1234'
    def __init__(self):
        pass

b4 = B4()

def scene_add(scene, tick, kind, role, action):
    if tick in scene:
        if kind in scene[tick]:
            if role in scene[tick][kind]:
                scene[tick][kind][role].add(action)
            else:
                scene[tick][kind][role] = {action}
        else:
            scene[tick][kind] = {role:{action}}
    else:
        scene[tick] = {kind: {role:{action}}}


def scene_add_action(scene, tick, role, action):
    scene_add(scene, tick, 'actions', role, action)


def scene_add_expect(scene, tick, role, expect):
    scene_add(scene, tick, 'expects', role, expect)


TYPE_BEFORE_TARGET = 1
TYPE_BEFORE_KEEP   = 2
TYPE_AFTER_KEEP    = 3

def scene_create_one(scene, tc_init, type):
    for room_name in b4.room_names[1:]:
        it = random.randint(b4.conf['it'][0][0], b4.conf['it'][0][1])
        if room_name > '2':
            it = random.randint(b4.conf['it'][1][0], b4.conf['it'][1][1])

        tc = random.randint(2, 5)
        tt = random.randint(b4.conf['tt'][0], b4.conf['tt'][1])
        w = random.randint(1, 3)
        scene_add_action(scene, tc, room_name, f'it={it} tt={tt} w={w} tc={tc} ts={b4.conf["ts"]}')
        scene_add_expect(scene, tc+1, 's', f'r={room_name} tc={tc} t={it}')

        temp_step = 1 if it<tt else -1

        if type == TYPE_BEFORE_TARGET:
            tt = tt - temp_step

        for t in range(it + temp_step, tt + temp_step, temp_step):
            tc = tc + (4-w)
            scene_add_expect(scene, tc+1, 's', f'r={room_name} tc={tc} t={t}')

        temp_diff = abs(tt - it)

        if type == TYPE_BEFORE_TARGET:
            scene_add_action(scene, tc, room_name, f'w=0 tc={tc}')
            scene_add_expect(scene, tc+1, 's', f'r={room_name} tc={tc} w=0')
            tc = tc + 1
            bill = temp_diff
            scene_add_action(scene, tc, 's', f'b={room_name} tc={tc}')
            scene_add_expect(scene, tc+1, 's', f'r={room_name} tc={tc} b={bill}')
            continue

        tick_keep_tt = random.randint(10, 20)

        bill = temp_diff * (1 + tick_keep_tt)

        for tc in range(tc, tc + tick_keep_tt):
            scene_add_expect(scene, tc+1, 's', f'r={room_name} tc={tc} t={t}')

        tc = tc + 1
        scene_add_action(scene, tc, room_name, f'w=0 tc={tc}')
        scene_add_expect(scene, tc+1, 's', f'r={room_name} tc={tc} w=0')

        tc = random.randint(tc+4, tc+5)
        scene_add_action(scene, tc, 's', f'b={room_name} tc={tc}')
        scene_add_expect(scene, tc+1, 's', f'r={room_name} tc={tc} b={bill}')

    return tc


def scene_dump(scene):
    text = ''
    for tick, actions in scene.items():
        text = text + f'{tick}\n'
        for room_name, cmd in actions.items():
            text = text + f'  "{room_name}" {cmd}\n'
    return text


def scene_create(group_name):
    scene = dict()
    random.seed()
    tc = 1
    if group_name in 'ace':
        tc = scene_create_one(scene, tc, TYPE_BEFORE_TARGET)
    else:
        tc = scene_create_one(scene, tc, TYPE_BEFORE_KEEP)
    # tc = scene_create_one(scene, tc, TYPE_AFTER_KEEP)

    scene = {k: scene[k] for k in sorted(scene)} 

    print(scene_dump(scene))
    return scene


async def scene_execute(scene, group_name, happens_all, log_prefix):
    prev_tick = 0
    for tick in scene.keys():
        await asyncio.sleep((tick - prev_tick) * b4.conf['ts'])
        prev_tick = tick
        log.info(f'{log_prefix} tc {tick}')
        if 'actions' in scene[tick]:
            actions = scene[tick]['actions']
            log.info(f'{log_prefix} actions {actions}')
            for room_name,commands in actions.items():
                for command in commands:
                    send_line(b4.groups[group_name]['rooms'][room_name]['w'], command)
        if 'expects' in scene[tick]:
            expects = scene[tick]['expects']['s']
            happens = happens_all.get(tick-1, None)
            log.info(f'{log_prefix} expects {expects}')
            log.info(f'{log_prefix} happens {happens}')
            if not happens:
                raise B4Error(f'e=ExpectHappenNone tc={tick}')
            for expect in expects:
                expect_dict = dict_from_line(expect)
                found = False
                for happen in happens:
                    happen_dict = dict_from_line(happen)
                    if set(expect_dict.items()).issubset(set(happen_dict.items())):
                        found = True
                        break
                if not found:
                    raise B4Error(f'e=ExpectHappenMiss tc={tick}')

    b4.groups[group_name]['pass'] = True
    b4.udp_transport.sendto(f'g={group_name} p=1'.encode('utf8'))


async def recv_task(r, group_name, happens_all, log_prefix):
    while True:
        kv_dict = await recv_line(r)
        log.info(f'{log_prefix} recv {kv_dict}')
        tc = kv_dict.get('tc', None)
        if not tc:
            raise B4Error(f'e=LackTickCount')
        line = ' '.join([f'{k}={v}' for (k,v) in kv_dict.items()])
        tc = int(tc)
        if tc in happens_all:
            happens_all[tc].add(line)
        else:
            happens_all[tc] = {line}
        b4.udp_transport.sendto(f'g={group_name} {line}'.encode('utf8'))


async def t_do_testee(r, w):
    group_name, room_name, rooms, room = None, None, None, None
    peer_host, peer_port, *_ = w.get_extra_info('peername')
    log_prefix = f'{peer_host:>15}:{peer_port:>5}'
    scene = ''
    try:
        group_key, room_name = await recv_line(r, 'k', 'r')
        group_name = b4.conf['k'].get(group_key, None)
        if not group_name:
            raise B4Error(f'e=ErrorKey', False)

        log_prefix = f'{log_prefix} g={group_name}'
        group = b4.groups[group_name]
        if group['pass']:
            raise B4Error(f'e=AlreadyPass')

        if not room_name in list(b4.room_names):
            raise B4Error(f'e=ErrorRoom')

        log_prefix = f'{log_prefix} r={room_name}'
        rooms = group['rooms']
        if room_name in rooms:
            raise B4Error(f'e=DuplicatedRoom')
        
        log.info(f'{log_prefix} logined!')
        send_line(w, f'e=0')
        b4.udp_transport.sendto(f'g={group_name} r={room_name} c=1'.encode('utf8'))

        room = rooms[room_name] = {'r':r, 'w':w}
        if room_name != 's':
            while True:
                await recv_line(r)

        log.info(f'{log_prefix} waiting i=1 ...')
        await recv_line(r, 'i')
        log.info(f'{log_prefix} test start!')
        if len(rooms) < len(b4.room_names):
            raise B4Error(f'e=LackRoom')

        happens_all = dict()
        scene = scene_create(group_name)
        task_scene = b4.loop.create_task(scene_execute(scene, group_name, happens_all, log_prefix))
        task_recv = b4.loop.create_task(recv_task(r, group_name, happens_all, log_prefix))

        # done, pending = await asyncio.wait({task_scene, task_recv}, loop=b4.loop)
        result = await asyncio.gather(task_scene, task_recv, loop=b4.loop)

    except B4Error as e:
        log.warning(f'{log_prefix} exc {e.args}')
        send_line(w, e.args[0] + '\n' + scene_dump(scene) + '\n\n')
    except Exception as e:
        log.warning(f'{log_prefix} {e.args}')
    finally:
        if not room:
            w.close()
        else:
            for room_name in rooms:
                rooms[room_name]['w'].close()
                b4.udp_transport.sendto(f'g={group_name} r={room_name} c=0'.encode('utf8'))
            rooms.clear()


class BlockView(QPushButton):
    styles = {'0':'background:red; color:white', '1':'background:lime; color:black', '2':'background:cyan; color:black', '3':'background:yellow; color:black'}
    def __init__(self, parent=None):
        QPushButton.__init__(self, parent)
        self.setStyleSheet(BlockView.styles['0'])
        self.setEnabled(False)


class MainWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowStaysOnTopHint|Qt.WindowMinMaxButtonsHint)
        # QDialog.__init__(self, parent, Qt.WindowStaysOnTopHint|Qt.WindowMinMaxButtonsHint)
        # QDialog.__init__(self, parent, Qt.WindowCloseButtonHint|Qt.WindowStaysOnTopHint|Qt.WindowMinMaxButtonsHint)
        # self.setStyleSheet('*{font:Consolas}')
        self.setStyleSheet('*{font:20pt Consolas}')

        mainLayout = QGridLayout()
        self.groups = dict()
        group_count = 0
        for group_name in b4.group_names:
            groupLayout = QVBoxLayout()
            groupLayout.setSpacing(0)
            groupLayout.setContentsMargins(0,0,0,0)

            groupNameWidget = BlockView(group_name)

            roomNameWidget = BlockView('s')
            rooms = {'s': [roomNameWidget]}

            groupLayout.addWidget(groupNameWidget)
            groupLayout.addWidget(roomNameWidget)

            roomsLayout = QHBoxLayout()

            for room_name in b4.room_names[1:]:

                roomNameWidget = BlockView(room_name)
                roomStateWidget = BlockView('--=---\n\n\n\n')
                roomStateWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding);
                rooms[room_name] = [roomNameWidget, roomStateWidget]

                roomLayout = QVBoxLayout()
                roomLayout.addWidget(roomNameWidget)
                roomLayout.addWidget(roomStateWidget)

                roomsLayout.addLayout(roomLayout)
            self.groups[group_name] = {'group':groupNameWidget, 'rooms': rooms}
            groupLayout.addLayout(roomsLayout)
            mainLayout.addLayout(groupLayout, group_count/3, group_count % 3)
            group_count = group_count + 1
        self.setLayout(mainLayout)
        self.move(923, 103)

        self.udpSocket = QUdpSocket(self)
        self.udpSocket.bind(QHostAddress.LocalHost, 8999)
        self.udpSocket.readyRead.connect(self.udpReadyRead)

    def keyPressEvent(self, event):
        key = event.key()
        if Qt.Key_Escape != key:
            event.accept()
        else:
            event.ignore()

    def moveEvent(self, event):
        self.setWindowTitle(f'{self.pos()}')
        event.accept()

    def udpReadyRead(self):
        while self.udpSocket.hasPendingDatagrams():
            data, host, port = self.udpSocket.readDatagram(self.udpSocket.pendingDatagramSize())
            data = data.decode('utf8').strip()
            # log.debug(f'{data}')
            kv_list = data.split()
            kv_dict = dict()
            for kv in kv_list:
                k,v, = kv.split('=')
                kv_dict[k] = v
            group_name = kv_dict.get('g', None)
            room_name =  kv_dict.get('r', None)
            conn_bool = kv_dict.get('c', None)
            wind_speed = kv_dict.get('w', None)
            pass_bool = kv_dict.get('p', None)
            if pass_bool:
                self.groups[group_name]['group'].setStyleSheet(BlockView.styles[pass_bool])
            if 'c' in kv_dict:
                self.groups[group_name]['rooms'][room_name][0].setStyleSheet(BlockView.styles[conn_bool])
                if conn_bool=='0' and room_name!='s':
                    self.groups[group_name]['rooms'][room_name][1].setStyleSheet(BlockView.styles[conn_bool])
                    self.groups[group_name]['rooms'][room_name][1].setText('')
            if 'tc' in kv_dict:
                wind_bool = '3' if wind_speed=='0' else '3'
                self.groups[group_name]['rooms'][room_name][1].setStyleSheet(BlockView.styles[wind_bool])
                kv_dict = {k: v for k,v in filter(lambda x:x[0] not in ('g','r'), kv_dict.items())}
                state = '\n'.join([f'{k:>2}={v:>3}' for (k,v) in kv_dict.items()])
                self.groups[group_name]['rooms'][room_name][1].setText(state)


def qt_main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())


async def async_main():
    b4.udp_transport, b4.udp_protocol = await b4.loop.create_datagram_endpoint(lambda: asyncio.DatagramProtocol(), local_addr=('127.0.0.1', 8998), remote_addr=('127.0.0.1', 8999))


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    with open('t.yml') as f:
        b4.conf = yaml.load(f.read())

    b4.conf['k'] = {v[0]:k for k,v in b4.conf['g'].items()}
    b4.group_names = list(b4.conf['g'].keys())
    b4.groups = {group_name: {'pass':None, 'rooms':dict()} for group_name in b4.group_names}
    log.debug(f'{b4.conf["k"]} {b4.group_names}')

    # udp datagram_point cannot used in win32 protocor event loop
    # if sys.platform == 'win32': asyncio.set_event_loop(asyncio.ProactorEventLoop())

    b4.loop = asyncio.get_event_loop()
    b4.loop.run_until_complete(async_main())

    coro = asyncio.start_server(t_do_testee, None, b4.conf['tester']['port'], loop=b4.loop)
    server = b4.loop.run_until_complete(coro)
    print(f'listening {server.sockets[0].getsockname()}')
    b4.loop.run_in_executor(None, qt_main)
    b4.loop.run_forever()
    server.close()
    b4.loop.run_untile_complete(server.wait_closed())
