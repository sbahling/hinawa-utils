# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2018 Takashi Sakamoto

from hinawa_utils.ta1394.general import AvcGeneral

__all__ = ['AvcCcm']


class AvcCcm():
    PLUG_MODE = ('unit', 'subunit')
    PLUG_UNIT_TYPE = ('isoc', 'external')

    @classmethod
    def get_unit_signal_addr(cls, type, plug):
        if type not in cls.PLUG_UNIT_TYPE:
            raise ValueError('Invalid argument for plug unit type')
        if plug >= 30:
            raise ValueError('Invalid argument for plug number')
        addr = bytearray()
        addr.append(0xff)
        if type == 'isoc':
            addr.append(plug)
        else:
            addr.append(0x80 + plug)
        return addr

    @classmethod
    def get_subunit_signal_addr(cls, type, id, plug):
        if type not in AvcGeneral.SUBUNIT_TYPES:
            raise ValueError('Invalid argument for subunit type')
        if plug >= 30:
            raise ValueError('Invalid argument for plug number')
        addr = bytearray()
        addr.append((AvcGeneral.SUBUNIT_TYPES.index(type) << 3) | id)
        addr.append(plug)
        return addr

    @classmethod
    def compare_addrs(cls, a, b):
        if a['mode'] == b['mode'] == 'unit':
            if a['data']['type'] == b['data']['type'] and \
               a['data']['plug'] == b['data']['plug']:
                return True
        elif a['mode'] == b['mode'] == 'subunit':
            if a['data']['type'] == b['data']['type'] and \
               a['data']['id'] == b['data']['id'] and \
               a['data']['plug'] == b['data']['plug']:
                return True
        return False

    @classmethod
    def parse_signal_addr(cls, addr):
        info = {}
        data = {}
        if addr[0] == 0xff:
            info['mode'] = 'unit'
            if addr[1] & 0x80:
                data['type'] = 'external'
                data['plug'] = addr[1] - 0x80
            else:
                data['type'] = 'isoc'
                data['plug'] = addr[1]
        else:
            info['mode'] = 'subunit'
            data['type'] = AvcGeneral.SUBUNIT_TYPES[addr[0] >> 3]
            data['id'] = addr[0] & 0x07
            data['plug'] = addr[1]
        info['data'] = data
        return info

    @classmethod
    def set_signal_source(cls, fcp, src, dst):
        args = bytearray()
        args.append(0x00)
        args.append(0xff)
        args.append(0x1a)
        args.append(0x0f)
        args.append(src[0])
        args.append(src[1])
        args.append(dst[0])
        args.append(dst[1])
        return AvcGeneral.command_control(fcp, args)

    @classmethod
    def get_signal_source(cls, fcp, dst):
        args = bytearray()
        args.append(0x01)
        args.append(0xff)
        args.append(0x1a)
        args.append(0xff)
        args.append(0xff)
        args.append(0xfe)
        args.append(dst[0])
        args.append(dst[1])
        params = AvcGeneral.command_status(fcp, args)
        src = params[4:6]
        return cls.parse_signal_addr(src)

    @classmethod
    def ask_signal_source(cls, fcp, src, dst):
        args = bytearray()
        args.append(0x02)
        args.append(0xff)
        args.append(0x1a)
        args.append(0xff)
        args.append(src[0])
        args.append(src[1])
        args.append(dst[0])
        args.append(dst[1])
        AvcGeneral.command_inquire(fcp, args)
