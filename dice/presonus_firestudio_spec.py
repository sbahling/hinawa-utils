from dice.tcat_tcd22xx_spec import TcatTcd22xxSpec

__all__ = ['PresonusFirestudioSpec']

class PresonusFirestudioSpec(TcatTcd22xxSpec):
    MODELS = (
        (0x000a92, 0x000008),   # Firestudio 26x26
        (0x000a92, 0x00000b),   # Firestudio project
        (0x000a92, 0x00000c),   # Firestudio tube
        (0x000a92, 0x000011),   # Firestudio mobile
    )

    _INPUTS = (
        (),
        (),
        (),
        (
            ('Analog',  'ins0', 8),
            ('S/PDIF',  'aes',  2),
        ),
    )

    _OUTPUTS = (
        (),
        (),
        (),
        (
            ('Analog',  'ins0', 4),
            ('S/PDIF',  'aes',  2),
        ),
    )

    _FIXED = (
        {},
        {},
        {},
        {
            0: ('src', 'ins0', 0),
            1: ('src', 'ins0', 1),
        },
    )
