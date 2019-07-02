import argparse
import asyncio
import signal
import sys
import time
import traceback
import yaml

import logging
from colorlog import ColoredFormatter
log_fmt = logging.Formatter('%(lineno)-3d %(levelname)7s %(funcName)-16s %(message)s')
log_fmt = ColoredFormatter('%(log_color)s%(levelname)-8s %(lineno)4d %(funcName)-16s %(message)s',
    datefmt=None, reset=True,
    log_colors={'DEBUG':'cyan', 'INFO':'green', 'WARNING':'yellow', 'ERROR':'red', 'CRITICAL':'red'})
log_handler = logging.StreamHandler()
log_handler.setLevel(logging.DEBUG)
log_handler.setFormatter(log_fmt)
log = logging.getLogger(__file__)
log.addHandler(log_handler)
log.setLevel(logging.DEBUG)


class B4Error(Exception):
    pass


def dict_from_line(line):
    try:
        kv_list = line.split()
        kv_dict = dict()
        for kv in kv_list:
            k,v, = kv.split('=')
            kv_dict[k.strip()] = v.strip()
        return kv_dict
    except Exception as e:
        raise e


async def recv_line(r, *keys):
    try:
        data = await r.readuntil(b'\n')
       # data=str(data)
       
        data = data.decode('utf8').strip()
        ####
       # print('data= '+str(data))
        ####
        
        kv_list = data.split()
        kv_dict = dict()
        for kv in kv_list:
            k,v, = kv.split('=')
            kv_dict[k.strip()] = v.strip()
        if not keys:
            return kv_dict
        result_list = []
        for k in keys:
            if not k in kv_dict:
                raise B4Error(f'miss {k} in [{data}]')
            result_list.append(kv_dict.get(k, None))
        return result_list
    except Exception as e:
        raise e


def send_line(w, line):
    w.write((line + '\n').encode('utf8'))
    ###
    #print('line= '+line)
    ####
    

