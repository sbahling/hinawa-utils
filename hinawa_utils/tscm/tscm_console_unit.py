# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2018 Takashi Sakamoto

from hinawa_utils.tscm.tscm_unit import TscmUnit

__all__ = ['TscmConsoleUnit']


class Fader():
    def __init__(self, unit, strip):
        self.unit = unit
        self.frames = bytearray(4)
        offset = int(strip) - 1

        # Maximum of 9 faders
        # Master fader is on strip 0 but has offset of 9
        if offset > 8:
            offset = 8
        elif offset < 0:
            offset = 8
        self.frames[3] = offset

    def set_position(self, pos):
        '''Moves the fader to the given position.
           pos = int between 0 and 1023
        '''
        self.frames[0], self.frames[1] = int(pos).to_bytes(2, byteorder='big')
        self.unit.write_quadlet(0x0400, self.frames)


class LED():
    def __init__(self, unit, code):
        self.unit = unit
        self.frames = bytearray(4)
        self.code = code
        self.frames[3] = self.code

    def turn_on(self):
        self.frames[1] = 0x01
        self.unit.write_quadlet(0x0404, self.frames)

    def turn_off(self):
        self.frames[1] = 0x00
        self.unit.write_quadlet(0x0404, self.frames)


class FW1884LEDs():
    '''A container of all the LED indicators on the FW-1884 console unit.
       There is one attribute for each LED indicator. The attribute names equal
       the name on the Tascam control unit except "del" which is a reserved
       keyword in python - we use "delete" here. Spaces and other invalid
       characters are converted to underscore ('_').

       Initialize the LEDs in the unit instance:

           self.leds = FW1884LEDs(self)

       Driving an LED can be done by accessing the attribute directly by name:

           unit.leds.loop.turn_on()
           unit.leds.loop.turn_off()

       or by string reference:

           unit.leds.turn_on('loop')
           unit.leds.turn_off('loop')

       String reference allows using the exact string as printed on the console
       in upper or lower case.

    '''

    # aliases for indicator names
    led_alias = {'del': 'delete',
                 'f.fwd': 'f_fwd',
                 'ffwd': 'f_fwd',
                 'rewind': 'rew',
                 'hi-mid': 'hi_mid',
                 'low-mid': 'low_mid',
                 }

    def __init__(self, unit):
        self.unit = unit

        self._init_strips()

        self.aux8 = LED(unit, 0x06)
        self.revert = self.f2 = LED(unit, 0x07)
        self.clr_solo = self.f4 = LED(unit, 0x08)
        self.loop = self.f6 = LED(unit, 0x09)
        self.f7 = LED(unit, 0x0B)
        self.high = LED(unit, 0x0C)
        self.rew = LED(unit, 0x0D)
        self.play = LED(unit, 0x11)
        self.delete = LED(unit, 0x26)
        self.paste = LED(unit, 0x27)
        self.undo = LED(unit, 0x28)
        self.ctrl = LED(unit, 0x29)
        self.f8 = LED(unit, 0x2B)
        self.hi_mid = LED(unit, 0x2C)
        self.f_fwd = LED(unit, 0x2D)
        self.cut = LED(unit, 0x46)
        self.copy = LED(unit, 0x47)
        self.alt = self.cmd = LED(unit, 0x48)
        self.shift = LED(unit, 0x49)
        self.f9 = LED(unit, 0x4B)
        self.low_mid = LED(unit, 0x4C)
        self.shtl = LED(unit, 0x4D)
        self.aux2 = LED(unit, 0x66)
        self.pan = LED(unit, 0x67)
        self.aux4 = LED(unit, 0x68)
        self.aux6 = LED(unit, 0x69)
        self.f10 = LED(unit, 0x6B)
        self.low = LED(unit, 0x6C)
        self.save = self.f1 = LED(unit, 0x87)
        self.all_safe = self.f3 = LED(unit, 0x88)
        self.marker = self.f5 = LED(unit, 0x89)
        self.read = LED(unit, 0x8B)
        self.bank_1 = LED(unit, 0x8C)
        self.firewire = LED(unit, 0x8E)
        self.rec = LED(unit, 0x92)
        self.flip = LED(unit, 0xA7)
        self.aux1 = LED(unit, 0xA8)
        self.aux3 = LED(unit, 0xA9)
        self.wrt = LED(unit, 0xAB)
        self.bank_2 = LED(unit, 0xAC)
        self.aux7 = LED(unit, 0xC8)
        self.aux5 = LED(unit, 0xC9)
        self.tch = LED(unit, 0xCB)
        self.bank_3 = LED(unit, 0xCC)
        self.latch = LED(unit, 0xEB)
        self.bank_4 = LED(unit, 0xEC)
        self.stop = LED(unit, 0xF2)

    def _init_strips(self):
        # create the LED objects for each console strip
        unit = self.unit
        for strip_num in range(1, 9):
            offset = 0x20 * (strip_num - 1)
            setattr(self, 's%s_sel' % strip_num, LED(unit, 0x00 + offset))
            setattr(self, 's%s_solo' % strip_num, LED(unit, 0x01 + offset))
            setattr(self, 's%s_mute' % strip_num, LED(unit, 0x02 + offset))
            setattr(self, 's%s_ol' % strip_num, LED(unit, 0x03 + offset))
            setattr(self, 's%s_signal' % strip_num, LED(unit, 0x04 + offset))
            setattr(self, 's%s_rec' % strip_num, LED(unit, 0x05 + offset))

    def turn_on(self, led):
        led = self.led_alias.get(led.lower(), led.lower())
        try:
            getattr(self, led).turn_on()
        except AttributeError:
            raise ValueError('Invalid LED: {}'.format(led))

    def turn_off(self, led):
        led = self.led_alias.get(led.lower(), led.lower())
        try:
            getattr(self, led).turn_off()
        except AttributeError:
            raise ValueError('Invalid LED: {}'.format(led))


class Strip():
    def __init__(self, unit, strip_num):
        self.id = int(strip_num)
        self.fader = Fader(unit, self.id)
        if self.id > 0:
            self.mute_led = getattr(unit.leds, 's%s_mute' % self.id)
            self.sel_led = getattr(unit.leds, 's%s_sel' % self.id)
            self.solo_led = getattr(unit.leds, 's%s_solo' % self.id)
            self.rec_led = getattr(unit.leds, 's%s_rec' % self.id)
            self.signal_led = getattr(unit.leds, 's%s_signal' % self.id)


class TscmConsoleUnit(TscmUnit):
    def __init__(self, path):
        super().__init__(path)

        if self.model_name not in ('FW-1082', 'FW-1884'):
            raise ValueError('Unsupported model: {0}'.format(self.model_name))

        # only the FW-1884 is mapped out at this time
        if self.model_name == 'FW-1884':
            self.leds = FW1884LEDs(self)
            self.strips = []
            for strip in range(0, 9):
                self.strips.append(Strip(self, strip))

            self.master_fader = self.strips[0].fader

    def bright_led(self, position, state):
        if state not in self.supported_led_status:
            raise ValueError('Invalid argument for LED state.')
        frames = bytearray(4)
        frames[3] = position
        if self.supported_led_status.index(state) == 1:
            frames[1] = 0x01
        self.write_quadlet(0x0404, frames)

    def set_master_fader(self, mode):
        frames = bytearray(4)
        if mode:
            frames[2] = 0x40
        else:
            frames[1] = 0x40
        self.write_quadlet(0x022c, frames)

    def get_master_fader(self):
        frames = self.read_quadlet(0x022c)
        return bool(frames[3] & 0x40)
