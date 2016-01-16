from ta1394.general import AvcGeneral

class AvcStreamFormatInfo():
    plug_direction = ('input', 'output')
    hierarchy_roots = ('DVCR', 'Audio&Music', 'BT.601', 'invalid', 'reserved')

    am_hierarchy_level1s = ('am824', 'audio-pack', 'floating-point',
                            'am824-compound')

    sampling_rates = (22050, 24000, 32000, 44100, 48000, 96000, 176400,
                      192000, 0, 0, 88200, 0, 0, 0, 0, 0)
    rate_controls = ('clock-based', 'command-based', 'not-supported')
    types = ('IEC60958-3',      # 0x00
             'IEC61937-3',
             'IEC61937-4',
             'IEC61937-5',
             'IEC61937-6',
             'IEC61937-7',
             'multi-bit-linear-audio-raw',
             'multi-bit-linear-audio-DVD-audio',
             'one-bit-audio-plain-raw',
             'one-bit-audio-plain-SACD',
             'one-bit-audio-encoded-raw',
             'one-bit-audio-encoded-SACD',
             'high-precision-multi-bit-linear-audio',
             'MIDI-conformant',
             'SMPTE-time-code-comformant',
             'sample-count',    # 0x0f
             'ancillary-data',  # 0x10
             'sync-stream',     # 0x40
             'do-not-care',     # 0xff
             'reserved')        # the others

    def _parse_format(params):
        if params[0] != 0x90 or params[1] != 0x40:
            raise RuntimeError('Unsupported format')
        fmt = {}
        fmt['sampling-rate'] = AvcStreamFormatInfo.sampling_rates[params[2]]
        fmt['rate-control'] = AvcStreamFormatInfo.rate_controls[params[3] & 0x03]
        formation = []
        for i in range(params[4]):
            for c in range(params[5 + i * 2]):
                type = params[5 + i * 2 + 1]
                if type <= 0x0f:
                    formation.append(AvcStreamFormatInfo.types[type])
                elif type == 0x10:
                    formation.append('ancillary-data')
                elif type == 0x40:
                    formation.append('sync-stream')
                elif type == 0xff:
                    formation.append('do-not-care')
                else:
                    formation.append('reserved')
        fmt['formation'] = formation
        return fmt

    def _build_format(fmt):
        if AvcStreamFormatInfo.sampling_rates.count(fmt['sampling-rate']) == 0:
            raise ValueError('Invalid argument for sampling rate')
        if AvcStreamFormatInfo.rate_controls.count(fmt['rate-control']) == 0:
            raise ValueError('Invalid argument for rate control mode')
        args = bytearray()
        args.append(0x90)
        args.append(0x40)
        args.append(AvcStreamFormatInfo.sampling_rates.index(fmt['sampling-rate']))
        args.append(AvcStreamFormatInfo.rate_controls.index(fmt['rate-control']))
        args.append(0x00)     # Set it later.
        prev = ''
        num = -1
        for i, formation in enumerate(fmt['formation']):
            if AvcStreamFormatInfo.types.count(formation) == 0:
                raise ValueError('Invalid argument for stream formation type')
            if formation == 'ancillary-data':
                type = 0x10
            elif formation == 'sync-stream':
                type = 0x40
            elif formation == 'do-not-care':
                type = 0xff
            elif formation == 'reserved':
                # Use this value.
                type = 0xfe
            else:
                type = AvcStreamFormatInfo.types.index(formation)
            if type != prev or i == len(fmt['formation']) - 1:
                if num > 0:
                    args.append(num + 1)
                    args.append(type)
                    args[4] += 1
                num = 1
            else:
                num += 1
            prev = type
        return args

    @staticmethod
    def set_format(fcp, direction, plug, fmt):
        args = bytearray()
        args.append(0x00)   # Control
        args.append(0xff)   # Addressing to unit
        args.append(0xbf)   # Extended stream format information command
        args.append(0xc0)   # SINGLE subfunction
        args.append(AvcStreamFormatInfo.plug_direction.index(direction))
        args.append(0x00)
        args.append(0x00)
        args.append(plug)
        args.append(0xff)
        args.append(0xff)
        args.extend(AvcStreamFormatInfo._build_format(fmt))
        AvcGeneral.command_control(fcp, args)

    @staticmethod
    def get_format(fcp, direction, plug):
        if AvcStreamFormatInfo.plug_direction.count(direction) == 0:
            raise ValueError('Invalid argument for plug direction')
        if plug > 255:
            raise ValueError('Invalid argument for plug number')
        args = bytearray()
        args.append(0x01)
        args.append(0xff)
        args.append(0xbf)
        args.append(0xc0)
        args.append(AvcStreamFormatInfo.plug_direction.index(direction))
        args.append(0x00)
        args.append(0x00)
        args.append(plug)
        args.append(0xff)
        args.append(0xff)
        args.append(0xff)
        args.append(0xff)
        params = AvcGeneral.command_status(fcp, args)

        return AvcStreamFormatInfo._parse_format(params[10:len(params)])

    @staticmethod
    def get_formats(fcp, direction, plug):
        if AvcStreamFormatInfo.plug_direction.count(direction) == 0:
            raise ValueError('Invalid argument for plug direction')
        if plug > 255:
            raise ValueError('Invalid argument for plug number')
        fmts = []
        args = bytearray()
        args.append(0x01)
        args.append(0xff)
        args.append(0xbf)
        args.append(0xc1)
        args.append(AvcStreamFormatInfo.plug_direction.index(direction))
        args.append(0x00)
        args.append(0x00)
        args.append(plug)
        args.append(0xff)
        args.append(0xff)
        args.append(0x00)
        args.append(0xff)
        for i in range(255):
            args[10] = i
            try:
                params = AvcGeneral.command_status(fcp, args)
                fmt = AvcStreamFormatInfo._parse_format(params[11:])
                fmts.append(fmt)
            except:
                break
        return fmts
