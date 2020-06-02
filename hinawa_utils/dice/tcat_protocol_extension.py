# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2018 Takashi Sakamoto

from struct import unpack, pack
from time import sleep
from math import log10, pow

__all__ = ['ExtCtlSpace', 'ExtCapsSpace', 'ExtCmdSpace', 'ExtMixerSpace',
           'ExtNewRouterSpace', 'ExtPeakSpace', 'ExtNewStreamConfigSpace',
           'ExtCurrentConfigSpace', 'ExtStandaloneSpace', 'ExtAppSpace']

# '3.1 External control private space'


class ExtCtlSpace():
    _EXT_OFFSET = 0x00200000

    _SECTIONS = {
        'caps':                 0x00,
        'cmd':                  0x08,
        'mixer':                0x10,
        'peak':                 0x18,
        'new-router':           0x20,
        'new-stream-config':    0x28,
        'current-config':       0x30,
        'standalone-config':    0x38,
        'application':          0x40,
    }

    @classmethod
    def write_section(cls, protocol, req, section, offset, data):
        if section not in cls._SECTIONS:
            raise ValueError('Invalid name of section: {0}'.format(section))
        offset += cls._EXT_OFFSET + protocol._ext_layout[section]['offset']
        return protocol.write_transactions(req, offset, data)

    @classmethod
    def read_section(cls, protocol, req, section, offset, length):
        if section not in cls._SECTIONS:
            raise ValueError('Invalid name of section: {0}'.format(section))
        offset += cls._EXT_OFFSET + protocol._ext_layout[section]['offset']
        return protocol.read_transactions(req, offset, length)

    @classmethod
    def detect_layout(cls, protocol, req):
        layout = {}

        data = protocol.read_transactions(req, cls._EXT_OFFSET,
                                          len(cls._SECTIONS) * 8)
        for name, offset in cls._SECTIONS.items():
            layout[name] = {
                'offset': unpack('>I', data[offset: offset + 4])[0] * 4,
                'length': unpack('>I', data[offset + 4: offset + 8])[0] * 4,
            }

        protocol._ext_layout = layout
        return layout

# '3.2 Capability space'


class ExtCapsSpace():
    _OFFSET_ROUTER_CAPS = 0x00
    _OFFSET_MIXER_CAPS = 0x04
    _OFFSET_GENERAL_CAPS = 0x08
    _OFFSET_RESERVED_CAPS = 0x0c

    _ASIC_TYPES = {
        0x00: 'DICE-II',
        0x01: 'TCD-2210',
        0x02: 'TCD-2220',
        0x03: 'Unknown',
    }

    @classmethod
    def _parse_router_caps(cls, data):
        caps = {}

        data = data[cls._OFFSET_ROUTER_CAPS:]
        caps['is-exposed'] = bool(data[3] & 0x01)
        caps['is-readonly'] = bool(data[3] & 0x02)
        caps['is-storable'] = bool(data[3] & 0x04)
        caps['maximum-routes'] = unpack('>H', data[0:2])[0]

        return caps

    @classmethod
    def _parse_mixer_caps(cls, data):
        caps = {}

        data = data[cls._OFFSET_MIXER_CAPS:]
        caps['is-exposed'] = bool(data[3] & 0x01)
        caps['is-readonly'] = bool(data[3] & 0x02)
        caps['is-storable'] = bool(data[3] & 0x04)
        caps['input-device-id'] = (data[3] & 0xf0) >> 4
        caps['output-device-id'] = data[2] & 0x0f
        caps['input-channels'] = data[1]
        caps['output-channels'] = data[0]
        return caps

    @classmethod
    def _parse_general_caps(cls, data):
        caps = {}

        data = data[cls._OFFSET_GENERAL_CAPS:]
        caps['dynamic-stream-conf'] = bool(data[3] & 0x01)
        caps['storage-available'] = bool(data[3] & 0x02)
        caps['peak-available'] = bool(data[3] & 0x04)
        caps['maximum-tx-streams'] = (data[3] & 0xf0) >> 4
        caps['maximum-rx-streams'] = data[2] & 0x0f
        caps['storable-stream-conf'] = bool(data[2] & 0x10)
        asic_type = data[1]
        if asic_type < len(cls._ASIC_TYPES) - 1:
            caps['asic-type'] = cls._ASIC_TYPES[asic_type]
        else:
            caps['asic-type'] = cls._ASIC_TYPES[-1]
        return caps

    @classmethod
    def detect_caps(cls, protocol, req):
        caps = {}

        length = protocol._ext_layout['caps']['length']
        data = ExtCtlSpace.read_section(protocol, req, 'caps', 0, length)

        caps['router'] = cls._parse_router_caps(data)
        caps['mixer'] = cls._parse_mixer_caps(data)
        caps['general'] = cls._parse_general_caps(data)
        caps['reserved'] = data[cls._OFFSET_RESERVED_CAPS:]

        protocol._ext_caps = caps

        return caps

# '3.3 Command space'


class ExtCmdSpace():
    _OFFSET_OPCODE = 0x0000
    _OFFSET_RETURN = 0x0004

    _EXECUTE_FLAG = 0x80

    _RETURN_SUCCESS = 0x00
    _RETURN_FAILURE = 0x01

    _OP_CODES = (
        'noop',
        'load-from-router',
        'load-from-stream-config',
        'load-from-router-stream-config',
        'load-from-storage',
        'load-to-storage',
    )

    _RATE_MODES = {
        'low':      0x01,
        'middle':   0x02,
        'high':     0x04,
    }

    @classmethod
    def initiate(cls, protocol, req, cmd, mode):
        if cmd not in cls._OP_CODES:
            raise ValueError('Invalid argument for command')
        if mode not in cls._RATE_MODES:
            raise ValueError('Invalid argument for rate mode')

        # Check feature capabilities.
        if ((cmd.find('router') > 0 and
                protocol._ext_caps['router']['is-readonly']) or
            (cmd.find('stream-config') > 0 and
                not protocol._ext_caps['general']['dynamic-stream-conf']) or
            (cmd in ('load-from-storage', 'load-to-storage') and
                not protocol._ext_caps['general']['storage-available'])):
            raise RuntimeError('This feature is not available.')

        data = bytearray(4)
        data[0] = cls._EXECUTE_FLAG
        data[1] = cls._RATE_MODES[mode]
        data[3] = cls._OP_CODES.index(cmd)

        ExtCtlSpace.write_section(
            protocol, req, 'cmd', cls._OFFSET_OPCODE, data)

        # Completion is notified as clearing of bit flags in the register.
        count = 10
        while count > 0:
            data = ExtCtlSpace.read_section(protocol, req, 'cmd',
                                            cls._OFFSET_OPCODE, 4)
            if not (data[0] & cls._EXECUTE_FLAG):
                break
            count -= 1
            sleep(0.2)
        else:
            raise IOError('Timeout of command initiation.')

        data = ExtCtlSpace.read_section(protocol, req, 'cmd',
                                        cls._OFFSET_RETURN, 4)
        if data[3] != cls._RETURN_SUCCESS:
            raise IOError('Fail to execute requested operation.')

# '3.4 Mixer space'


class ExtMixerSpace():
    # These are TCD-2200/2210 specification.
    MIXER_IN_MAX_PORTS = {
        'mixer-tx0': 16,
        'mixer-tx1':  2,
    }
    MIXER_OUT_MAX_PORTS = {
        'low':      16,
        'middle':   16,
        'high':     8,
    }
    MAX_COEFF = 0x3fff

    # '5.11 Audio Mixer' in 'TCD22xx Users Guide'.
    @classmethod
    def parse_val_to_db(cls, val):
        if val == 0:
            return float('-inf')
        return 20 * log10(val / cls.MAX_COEFF)

    @classmethod
    def build_val_from_db(cls, db):
        if db > 4:
            raise ValueError('Invalid argument for dB value.')
        if db == float('-inf'):
            return 0
        return int(cls.MAX_COEFF * pow(10, db / 20))

    @classmethod
    def _calcurate_offset(cls, protocol, out_ch, in_ch):
        if out_ch >= protocol._ext_caps['mixer']['output-channels']:
            raise ValueError('Invalid value for output channel')
        if in_ch >= protocol._ext_caps['mixer']['input-channels']:
            raise ValueError('Invalid value for input channel')
        offset = (
            out_ch * protocol._ext_caps['mixer']['input-channels'] + in_ch) * 4
        if offset >= protocol._ext_layout['mixer']['length']:
            raise OSError('Inconsistency between channels and length of space')

        return 4 + offset

    @classmethod
    def read_saturation(cls, protocol, req, mode):
        if not protocol._ext_caps['mixer']['is-exposed']:
            raise IOError('This feature is not available.')

        data = ExtCtlSpace.read_section(protocol, req, 'mixer', 0, 4)
        bits = unpack('>I', data)[0]
        outputs = cls.MIXER_OUT_MAX_PORTS[mode]

        saturations = []
        for i in range(outputs):
            saturations.append(bool(bits & (1 << i)))
        return saturations

    @classmethod
    def write_gain(cls, protocol, req, out_ch, in_ch, val):
        if not protocol._ext_caps['mixer']['is-exposed']:
            raise IOError('This feature is not available.')

        offset = cls._calcurate_offset(protocol, out_ch, in_ch)

        data = bytearray()
        data.append(0x00)
        data.append(0x00)
        data.extend(pack('>H', val))

        return ExtCtlSpace.write_section(protocol, req, 'mixer', offset, data)

    @classmethod
    def read_gain(cls, protocol, req, out_ch, in_ch):
        if not protocol._ext_caps['mixer']['is-exposed']:
            raise IOError('This feature is not available.')

        offset = cls._calcurate_offset(protocol, out_ch, in_ch)

        data = ExtCtlSpace.read_section(protocol, req, 'mixer', offset, 4)

        return unpack('>H', data[2:4])[0]

# '3.6 New router space'


class ExtNewRouterSpace():
    _SRC_BLK_IDS = (
        'aes', 'adat', 'mixer', 'reserved0',
        'ins0', 'ins1', 'reserved1', 'reserved2',
        'reserved3', 'reserved4', 'arm-apr-audio', 'avs0',
        'avs1', 'reserved5', 'reserved6', 'mute',
    )
    _DST_BLK_IDS = (
        'aes', 'adat', 'mixer-tx0', 'mixer-tx1',
        'ins0', 'ins1', 'reserved0', 'reserved1',
        'reserved2', 'reserved3', 'arm-apb-audio', 'avs0',
        'avs1', 'reserved4', 'reserved5', 'reserved6',
    )

    # '5.1.3 ROUTERn_ENTRYm' in 'TCD22xx Users Guide'.
    @classmethod
    def parse_entry_data(cls, data):
        # '5.1.4 Source Block ID’s' in 'TCD22xx Users Guide'.
        entry = {}

        src_blk_id = data[0] >> 4
        if src_blk_id >= len(cls._SRC_BLK_IDS):
            raise IOError('Invalid id for source block in router entry')
        entry['src-blk'] = cls._SRC_BLK_IDS[src_blk_id]
        entry['src-ch'] = data[0] & 0x0f

        dst_blk_id = data[1] >> 4
        if dst_blk_id >= len(cls._DST_BLK_IDS):
            raise IOError('Invalid id for destination block in router entry')
        entry['dst-blk'] = cls._DST_BLK_IDS[dst_blk_id]
        entry['dst-ch'] = data[1] & 0x0f

        return entry

    @classmethod
    def parse_data(cls, protocol, req, section, offset, length):
        entries = []

        data = ExtCtlSpace.read_section(protocol, req, section, offset, 4)
        count = unpack('>I', data[0:4])[0]
        if count >= length // 4:
            count = length // 4

        offset += 4
        data = ExtCtlSpace.read_section(protocol, req, section, offset,
                                        count * 4)
        if count > 0:
            for i in range(0, 4 * count, 4):
                entry = cls.parse_entry_data(data[2:4])
                entry['peak'] = unpack('>H', data[0:2])[0]
                entries.append(entry)
                data = data[4:]

        return entries

    @classmethod
    def _build_entry_data(cls, entry):
        KEYS = ('peak', 'src-blk', 'src-ch', 'dst-blk', 'dst-ch')

        # Check keys.
        for key in KEYS:
            if key not in entry:
                raise ValueError('Invalid argument for entry data.')

        data = bytearray()
        data.extend(pack('>H', entry['peak']))

        src = (cls._SRC_BLK_IDS.index(entry['src-blk']) << 4) | entry['src-ch']
        data.append(src)

        dst = (cls._DST_BLK_IDS.index(entry['dst-blk']) << 4) | entry['dst-ch']
        data.append(dst)

        return data

    @classmethod
    def _build_data(cls, length, entries):
        data = bytearray()
        data.extend(pack('>I', len(entries)))
        for entry in entries:
            data.extend(cls._build_entry_data(entry))
        # Padding with zero byte.
        for i in range(len(data), length, 4):
            data.extend((0x00, 0x00, 0x00, 0x00))
        return data

    @classmethod
    def set_entries(cls, protocol, req, entries):
        if (not protocol._ext_caps['router']['is-exposed'] or
                protocol._ext_caps['router']['is-readonly']):
            raise IOError('This feature is not available.')
        length = protocol._ext_layout['new-router']['length']
        if (len(entries) >= protocol._ext_caps['router']['maximum-routes'] or
                len(entries) >= length // 4):
            raise ValueError('Too much entries.')
        data = cls._build_data(length, entries)
        ExtCtlSpace.write_section(protocol, req, 'new-router', 0, data)

    @classmethod
    def get_entries(cls, protocol, req):
        if not protocol._ext_caps['router']['is-exposed']:
            raise IOError('This feature is not available.')
        length = protocol._ext_layout['new-router']['length']
        return cls.parse_data(protocol, req, 'new-router', 0, length)

# '3.5 Peak space'


class ExtPeakSpace():
    @classmethod
    def get(cls, protocol, req):
        if not protocol._ext_caps['general']['peak-available']:
            raise IOError('This feature is not available.')

        entries = []
        length = protocol._ext_layout['peak']['length']
        data = ExtCtlSpace.read_section(protocol, req, 'peak', 0, length)
        for i in range(0, len(data), 4):
            entry = ExtNewRouterSpace.parse_entry_data(data[2:4])
            entry['peak'] = unpack('>H', data[0:2])[0]
            entries.append(entry)
            data = data[4:]
        return entries

# '3.7 New stream config space'


class ExtNewStreamConfigSpace():
    @classmethod
    def _parse_entry(cls, data):
        stream = {}

        stream['pcm'] = unpack('>I', data[0:4])[0]
        data = data[4:]

        stream['midi'] = unpack('>I', data[0:4])[0]
        data = data[4:]

        letters = bytearray()
        for i in range(0, 256, 4):
            letters.extend(list(reversed(data[0:4])))
            data = data[4:]
        stream['formation'] = letters.decode('utf-8').split('\\')[0:-2]

        stream['ac3'] = data[0]

        return stream

    @classmethod
    def parse_data(cls, protocol, req, section, offset, length):
        confs = {}

        data = ExtCtlSpace.read_section(protocol, req, section, offset, 8)
        tx_count = unpack('>I', data[0:4])[0]
        rx_count = unpack('>I', data[4:8])[0]

        offset += 8
        if tx_count > 0:
            confs['tx'] = []
        for i in range(tx_count):
            data = ExtCtlSpace.read_section(protocol, req, section,
                                            offset + 268 * i, 268)
            conf = cls._parse_entry(data)
            if conf['pcm'] > 0 or conf['midi'] > 0:
                confs['tx'].append(conf)

        offset += 268 * tx_count
        if rx_count > 0:
            confs['rx'] = []
        for i in range(rx_count):
            data = ExtCtlSpace.read_section(protocol, req, section,
                                            offset + 268 * i, 268)
            conf = cls._parse_entry(data)
            if conf['pcm'] > 0 or conf['midi'] > 0:
                confs['rx'].append(conf)

        return confs

    @classmethod
    def set_entries(cls, protocol, req, config):
        if not protocol._ext_caps['general']['dynamic-stream-conf']:
            raise IOError('This feature is not available.')

    @classmethod
    def get_entries(cls, protocol, req):
        offset = protocol._ext_layout['new-stream-config']['offset']
        length = protocol._ext_layout['new-stream-config']['length']
        return ExtNewStreamConfigSpace.parse_data(protocol, req,
                                                  'new-stream-config', offset, length)

# '3.8 Current config space'


class ExtCurrentConfigSpace():
    _RATE_MODES = {
        'low':      0x0000,
        'middle':   0x2000,
        'high':     0x4000,
    }

    @classmethod
    def read_router_config(cls, protocol, req, mode):
        if mode not in cls._RATE_MODES:
            raise ValueError('Invalid argument for rate mode.')

        offset = cls._RATE_MODES[mode]

        return ExtNewRouterSpace.parse_data(protocol, req, 'current-config',
                                            offset, 0x1000)

    @classmethod
    def read_stream_config(cls, protocol, req, mode):
        if mode not in cls._RATE_MODES:
            raise ValueError('Invalid argument for rate mode.')

        offset = cls._RATE_MODES[mode] + 0x1000

        return ExtNewStreamConfigSpace.parse_data(protocol, req,
                                                  'current-config', offset, 0x1000)

# '3.9 Stand alone config space'


class ExtStandaloneSpace():
    _AES_EXT_OPTIONS = {
        'high-rate': {
            'off':  0x00,
            'on':   0x01,
        },
    }
    _ADAT_EXT_OPTIONS = {
        'mode': {
            'normal':   0x00,
            'smux-ii':  0x01,
            'smux-iv':  0x02,
            'auto':     0x03,
        },
    }
    _WC_EXT_OPTIONS = {
        'mode': {
            'normal':   0x00,
            'low':      0x01,
            'middle':   0x02,
            'high':     0x03,
        },
        'mul': 0x3fff,
        'div': 0xffff,
    }
    _STANDALONE_SPACE_OFFSETS = {
        'aes1':         0x04,
        'aes2':         0x04,
        'aes3':         0x04,
        'aes4':         0x04,
        'aes-any':      0x04,
        'adat':         0x08,
        'tdif':         0x08,
        'word-clock':   0x0c,
        'internal':     0x10,
    }

    @classmethod
    def write_clock_source(cls, protocol, req, source):
        if source not in protocol._clock_sources:
            raise ValueError('Invalid argument for clock source.')
        val = {v: k for k, v in protocol.CLOCK_BITS.items()}[source]

        data = ExtCtlSpace.read_section(
            protocol, req, 'standalone-config', 0, 4)
        if val != data[3]:
            data[3] = val
            ExtCtlSpace.write_section(
                protocol, req, 'standalone-config', 0, data)

    @classmethod
    def read_clock_source(cls, protocol, req):
        data = ExtCtlSpace.read_section(
            protocol, req, 'standalone-config', 0, 4)
        val = data[3]
        if (val not in protocol.CLOCK_BITS or
                protocol._clock_source_labels[val] == 'Unused'):
            raise OSError('Unexpected return value for clock source.')

        return protocol.CLOCK_BITS[val]

    @classmethod
    def get_source_param_options(cls, protocol, source):
        OPTIONS = {
            'aes1':         ExtStandaloneSpace._AES_EXT_OPTIONS,
            'aes2':         ExtStandaloneSpace._AES_EXT_OPTIONS,
            'aes3':         ExtStandaloneSpace._AES_EXT_OPTIONS,
            'aes4':         ExtStandaloneSpace._AES_EXT_OPTIONS,
            'aes-any':      ExtStandaloneSpace._AES_EXT_OPTIONS,
            'adat':         ExtStandaloneSpace._ADAT_EXT_OPTIONS,
            'tdif':         ExtStandaloneSpace._ADAT_EXT_OPTIONS,
            'word-clock':   ExtStandaloneSpace._WC_EXT_OPTIONS,
            'arx1':         None,
            'arx2':         None,
            'arx3':         None,
            'arx4':         None,
            'internal':     {'rate': protocol._sampling_rates, }
        }
        if source not in protocol._clock_sources or source not in OPTIONS:
            raise ValueError('Invalid argument for clock source.')

        return OPTIONS[source]

    @classmethod
    def write_clock_source_params(cls, protocol, req, source, params):
        if source not in protocol._clock_sources:
            raise ValueError('Invalid argument for clock source.')
        param_options = cls.get_source_param_options(protocol, source)
        for name, param_option in param_options.items():
            if name not in params:
                raise ValueError('Required parameter not in param argument.')

        if source == 'word-clock':
            val = cls._WC_EXT_OPTIONS['mode'][params['mode']]
            val |= (params['mul'] - 1) << 2
            val |= (params['div'] - 1) << 16
        elif source == 'internal':
            val = {v: k for k, v in protocol.RATE_BITS.items()}[params['rate']]
        else:
            for name, param_option in param_options.items():
                for option, flag in param_option.items():
                    if params[name] == option:
                        val = flag
                        break

        data = pack('>I', val)

        offset = cls._STANDALONE_SPACE_OFFSETS[source]
        ExtCtlSpace.write_section(
            protocol, req, 'standalone-config', offset, data)

    @classmethod
    def read_clock_source_params(cls, protocol, req, source):
        if source not in protocol._clock_sources:
            raise ValueError('Invalid argument for clock source.')
        offset = cls._STANDALONE_SPACE_OFFSETS[source]

        data = ExtCtlSpace.read_section(protocol, req, 'standalone-config',
                                        offset, 4)
        val = unpack('>I', data)[0]

        params = {}
        param_options = cls.get_source_param_options(protocol, source)
        if source == 'word-clock':
            mode = {v: k for k, v in param_options['mode'].items()}[val & 0x03]
            params['mode'] = mode
            params['mul'] = ((val >> 2) & 0x3fff) + 1
            params['div'] = (val >> 16) + 1
        elif source == 'internal':
            index = val & 0x0f
            if index not in protocol.RATE_BITS:
                raise IOError('Unexpected state of internal clock rate.')
            params['rate'] = protocol.RATE_BITS[index]
        else:
            val &= 0x0f
            for name, param_option in param_options.items():
                for option, flag in param_option.items():
                    if val == flag:
                        params[name] = option

        return params

# '3.10 Application space'


class ExtAppSpace():
    @classmethod
    def set(cls, protocol, req, offset, data):
        if len(data) >= protocol._ext_layout['application']['length']:
            raise ValueError('Invalid argument for data.')
        ExtCtlSpace.write_section(protocol, req, 'application', offset, data)

    @classmethod
    def get(cls, protocol, req, offset, length):
        if length >= protocol._ext_layout['application']['length']:
            raise ValueError('Invalid argument for data.')
        return ExtCtlSpace.read_section(protocol, req, 'application', offset,
                                        length)
