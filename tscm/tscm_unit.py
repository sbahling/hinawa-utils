import gi
gi.require_version('Hinawa', '1.0')
from gi.repository import Hinawa

import re
from array import array

__all__ = ['TscmUnit']

class TscmUnit(Hinawa.SndUnit):
    supported_sampling_rates = (44100, 48000, 88200, 96000)
    supported_clock_sources = ('Internal', 'Word-clock', 'S/PDIF', 'ADAT')
    supported_coax_sources = ('S/PDIF-1/2', 'Analog-1/2')
    supported_led_status = ('off', 'on')

    _specs = {
        'FW-1884': {
            'opt-out-mode': {
                'stream-9/10/11/12/13/14/15/16':    0x000c0000,
                'stream-1/2/3/4/5/6/7/8':           0x00840800,
                'stream-11/12':                     0x00080400,
                'analog-1/2/3/4/5/6/7/8':           0x00048800,
            },
            'coax-out-mode': {
                'stream-17/18':                     0x00020000,
                'stream-1/2':                       0x00000200,
            },
            'stream-in-17/18-mode': {
                'coax-in-1/2':                      0x00000100,
                'opt-in-1/2':                       0x00010000,
            },
            'mixer-input-labels': {},
        },
        'FW-1804': {
            'opt-out-mode': {
                'stream-3/4/5/6/7/8/9/10' :         0x000c0000,
                # TODO: can do it?
                'stream-11/12':                     0x00080400,
                'analog-1/2/3/4/5/6/7/8':           0x00048800,
            },
            'coax-out-mode': {
                'stream-11/12':                     0x00020000,
                'stream-1/2':                       0x00000200,
            },
            'stream-in-17/18-mode': {
                'coax-in-1/2':                      0x00000100,
                'opt-in-1/2':                       0x00010000,
            },
            'mixer-input-labels': {
                'analog-1', 'analog-2', 'analog-3', 'analog-4',
                'analog-5', 'analog-6', 'analog-7', 'analog-8',
                'adat-1', 'adat-2', 'adat-3', 'adat-4',
                'adat-5', 'adat-6', 'adat-7', 'adat-8',
                'spdif-1', 'spdif-2',
            },
        },
        'FW-1082': {
            'opt-out-mode': {},
            'coax-out-mode': {
                'stream-9/10':                      0x00000200,
                'stream-1/2':                       0x00020000,
            },
            'stream-in-17/18-mode': {},
            'mixer-input-labels': {},
        },
    }

    def __init__(self, path):
        if re.match('/dev/snd/hwC[0-9]*D0', path):
            super().__init__()
            self.open(path)
            if self.get_property('type') != 6:
                raise ValueError('The character device is not for Tascam unit')
            self.listen()
        elif re.match('/dev/fw[0-9]*', path):
            # Just using parent class.
            super(Hinawa.FwUnit, self).__init__()
            Hinawa.FwUnit.open(self, path)
            Hinawa.FwUnit.listen(self)
        else:
            raise ValueError('Invalid argument for character device')
        self.name = self._parse_name()
        self.spec = self._specs[self.name]
        # For permanent cache.
        self._filepath = '/tmp/hinawa-{0:08x}'.format(self.get_property('guid'))

    def _parse_name(self):
        literal = bytearray()
        for i,q in enumerate(self.get_config_rom()[28:]):
            for j in range(4):
                c = (q >> (24 - 8 * j)) & 0xff
                if c == 0x00:
                    break
                literal.append(c)
        return literal.decode('utf-8').rstrip()

    def _read_transaction(self, addr, quads):
        req = Hinawa.FwReq()
        return req.read(self, addr, quads)

    def _write_transaction(self, addr, data):
        req = Hinawa.FwReq()
        return req.write(self, addr, data)

    def get_firmware_versions(self):
        info = {}
        data = self._read_transaction(0xffff00000000, 1)
        info['Register'] = data[0]
        data = self._read_transaction(0xffff00000004, 1)
        info['FPGA'] = data[0]
        data = self._read_transaction(0xffff00000008, 1)
        info['ARM'] = data[0]
        data = self._read_transaction(0xffff0000000c, 1)
        info['HW'] = data[0]
        return info

    def set_clock_source(self, source):
        if source not in self.supported_clock_sources:
            raise ValueError('Invalid argument for clock source.')
        src = self.supported_clock_sources.index(source) + 1
        data = self._read_transaction(0xffff00000228, 1)
        data[0] = (data[0] & 0x0000ff00) | src
        self._write_transaction(0xffff00000228, data)
    def get_clock_source(self):
        data = self._read_transaction(0xffff00000228, 1)
        print(data)
        print('{0:08x}'.format(data[0]))
        index = ((data[0] & 0x00ff0000) >> 16) - 1
        if index >= len(self.supported_clock_sources):
            raise OSError('Unexpected value for clock source.')
        return self.supported_clock_sources[index]

    def set_sampling_rate(self, rate):
        if rate not in self.supported_sampling_rates:
            raise ValueError('Invalid argument for sampling rate.')
        if rate == 44100:
            flag = 0x01
        elif rate == 48000:
            flag = 0x02
        elif rate == 88200:
            flag = 0x81
        elif rate == 96000:
            flag = 0x82
        data = self._read_transaction(0xffff00000228, 1)
        data[0] = (data[0] & 0x000000ff) | (flag << 8)
        self._write_transaction(0xffff00000228, data)
    def get_sampling_rate(self):
        data = self._read_transaction(0xffff00000228, 1)
        value = (data[0] & 0xff000000) >> 24
        if (value & 0x0f) == 0x01:
            rate = 44100
        elif (value & 0x0f) == 0x02:
            rate = 48000
        else:
            raise OSError('Unexpected value for sampling rate.')
        if (value & 0xf0) == 0x80:
            rate *= 2
        elif (value & 0xf0) != 0x00:
            print(value)
            raise OSError('Unexpected value for sampling rate.')
        return rate

    def set_master_fader(self, mode):
        data = array('I')
        if mode > 0:
            data.append(0x00004000)
        else:
            data.append(0x00400000)
        self._write_transaction(0xffff0000022c, data)
    def get_master_fader(self):
        data = self._read_transaction(0xffff0000022c, 1)
        if data[0] & 0x00000040:
            return True
        else:
            return False

    def set_coaxial_source(self, source):
        data = array('I')
        if source not in self.supported_coax_sources:
            raise ValueError('Invalid argument for coaxial source.')
        if self.supported_coax_sources.index(source) == 0:
            data.append(0x00020000)
        else:
            data.append(0x00000200)
        self._write_transaction(0xffff0000022c, data)
    def get_coaxial_source(self):
        data = self._read_transaction(0xffff0000022c, 1)
        index = data[0] & 0x00000002 > 0
        return self.supported_coax_sources[index]

    def bright_led(self, position, state):
        if state not in self.supported_led_status:
            raise ValueError('Invalid argument for LED state.')
        data = array('I')
        if self.supported_led_status.index(state) == 0:
            data.append(position)
        else:
            data.append(0x00010000 | position)
        self._write_transaction(0xffff00000404, data)

    def get_mixer_input_labels(self):
        return self.spec['mixer-input-labels']
    def set_mixer_input(self):
        return
    def get_mixer_input(self, op, input):
        ops = ('volume', 'mute', )
        return
    def get_mixer_input_volume(self, input):
        if input not in self.spec['mixer-input-labels']:
            raise ValueError('Invalid argument for mixer input pair.')
    def get_mixer_input_mute(self, input):
        if input not in self.spec['mixer-input-labels']:
            raise ValueError('Invalid argument for mixer input pair.')
    def get_mixer_input_pan(self, input):
        if input not in self.spec['mixer-input-labels']:
            raise ValueError('Invalid argument for mixer input pair.')
